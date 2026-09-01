"""
API Client for Meat Quality Monitoring System.

 Implements the Raspberry Pi Data Recovery Strategy:
  - Tracks the last seen reading timestamp and ID in a local bookmark file
  - On startup: catches up on missed readings via /history
  - During normal operation: polls /history every N seconds
  - Retries with exponential backoff on failures

 The remote server can restore/reset its numeric IDs, and its /current endpoint
 can consequently select an older high-ID row.  History polling therefore uses
 the reading timestamp as the primary cursor and the numeric ID only as a
 same-timestamp tie-breaker.

The data flow is:
  ESP32 → Remote API → This client → Local SQLite DB → Dashboard reads DB
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import requests

import config
from db_manager import get_db_manager

logger = logging.getLogger(__name__)


# ============================================================================
# Bookmark Management
# ============================================================================

def load_bookmark() -> Dict[str, Any]:
    """Load the last seen reading ID and timestamp from disk."""
    try:
        with open(config.BOOKMARK_FILE, "r") as f:
            bookmark = json.load(f)
        if isinstance(bookmark, dict):
            return {
                "last_id": _safe_int(bookmark.get("last_id")),
                "last_timestamp": bookmark.get("last_timestamp"),
            }
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    return {"last_id": 0, "last_timestamp": None}


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert an API value to int without letting malformed data abort a poll."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_api_timestamp(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 API timestamp and normalize it to aware UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_api_timestamp(value: datetime) -> str:
    """Format an aware datetime as the UTC ISO-8601 form expected by the API."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_source_id(data: Dict[str, Any], timestamp_field: str) -> str:
    """Return a stable deduplication key even when the API omits source_id."""
    explicit_source_id = data.get("source_id")
    if explicit_source_id:
        return str(explicit_source_id)

    device_id = data.get("device_id", "ESP32-MeatMonitor")
    reading_id = _safe_int(data.get("id"))
    reading_time = data.get(timestamp_field, "")
    return f"server:{device_id}:{reading_id}:{reading_time}"


def _bookmark_cursor(bookmark: Dict[str, Any]) -> Tuple[datetime, int, bool]:
    """Return the effective timestamp/ID cursor and whether it is recent."""
    now = datetime.now(timezone.utc)
    recent_floor = now - timedelta(hours=config.SENSOR_API_RECOVERY_LOOKBACK_HOURS)
    bookmark_time = _parse_api_timestamp(bookmark.get("last_timestamp"))
    is_recent = bool(
        bookmark_time
        and recent_floor <= bookmark_time <= now + timedelta(minutes=5)
    )

    if is_recent:
        return bookmark_time, _safe_int(bookmark.get("last_id")), True
    return recent_floor, -1, False


def _history_query_start(bookmark: Dict[str, Any]) -> str:
    """Choose a bounded history start, ignoring stale/future bookmarks."""
    cursor_time, _, is_recent = _bookmark_cursor(bookmark)
    if bookmark.get("last_timestamp") and not is_recent:
        logger.warning(
            "Bookmark timestamp %s is outside the %dh recovery window; "
            "recovering from %s",
            bookmark.get("last_timestamp"),
            config.SENSOR_API_RECOVERY_LOOKBACK_HOURS,
            _format_api_timestamp(cursor_time),
        )
    return _format_api_timestamp(cursor_time)


def _reading_sort_key(reading: Dict[str, Any]) -> Tuple[datetime, int]:
    """Sort readings by UTC timestamp, then ID only as a tie-breaker."""
    reading_time = _parse_api_timestamp(reading.get("reading_time"))
    if reading_time is None:
        reading_time = datetime.min.replace(tzinfo=timezone.utc)
    return reading_time, _safe_int(reading.get("id"))


def save_bookmark(last_id: int, last_timestamp: str) -> None:
    """Atomically persist the bookmark after a successful processing cycle."""
    temporary_path = f"{config.BOOKMARK_FILE}.tmp"
    try:
        with open(temporary_path, "w") as f:
            json.dump({"last_id": last_id, "last_timestamp": last_timestamp}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary_path, config.BOOKMARK_FILE)
    except OSError as e:
        logger.error("Failed to save bookmark: %s", e)
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


# ============================================================================
# HTTP Request with Retry
# ============================================================================

def api_get(endpoint: str, params: dict = None) -> Optional[Any]:
    """
    Make an authenticated GET request with retry + exponential backoff.

    Args:
        endpoint: API endpoint path (e.g. "/current" or "/history")
        params: Optional query parameters

    Returns:
        Parsed JSON response or None on failure
    """
    url = f"{config.SENSOR_API_BASE}{endpoint}"
    headers = {"x-api-key": config.SENSOR_API_KEY}

    for attempt in range(1, config.SENSOR_API_MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url, headers=headers, params=params,
                timeout=config.SENSOR_API_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json()

            logger.warning(
                "HTTP %d on %s (attempt %d/%d)",
                resp.status_code, endpoint, attempt, config.SENSOR_API_MAX_RETRIES,
            )
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Request error on %s: %s (attempt %d/%d)",
                endpoint, e, attempt, config.SENSOR_API_MAX_RETRIES,
            )

        if attempt < config.SENSOR_API_MAX_RETRIES:
            delay = config.SENSOR_API_RETRY_BASE_DELAY * attempt
            time.sleep(delay)

    logger.error("Failed to reach %s after %d attempts", endpoint, config.SENSOR_API_MAX_RETRIES)
    return None


# ============================================================================
# Reading Normalization & Storage
# ============================================================================

def normalize_current(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a /current API response into a common reading dict.

    /current fields: temperature, humidity, co2_ppm, h2s_ppm, nh3_ppm, quality
    """
    return {
        "id": _safe_int(data.get("id")),
        "source_id": _make_source_id(data, "timestamp"),
        "device_id": data.get("device_id", "ESP32-MeatMonitor"),
        "reading_time": data.get("timestamp", ""),
        "received_at": data.get("received_at"),
        "temperature": float(data.get("temperature", 0.0)),
        "humidity": float(data.get("humidity", 0.0)),
        "mq135_co2": float(data.get("co2_ppm", 0.0)),
        "mq136_h2s": float(data.get("h2s_ppm", 0.0)),
        "mq137_nh3": float(data.get("nh3_ppm", 0.0)),
        "quality_level": data.get("quality", "UNKNOWN"),
        "wifi_rssi": data.get("wifi_rssi"),
        "sensor_status": data.get("sensor_status", {}),
    }


def normalize_history(reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a /history reading into a common reading dict.

    /history fields: temperature, humidity, mq135_co2, mq136_h2s, mq137_nh3, quality_level
    """
    return {
        "id": _safe_int(reading.get("id")),
        "source_id": _make_source_id(reading, "reading_time"),
        "device_id": reading.get("device_id", "ESP32-MeatMonitor"),
        "reading_time": reading.get("reading_time", ""),
        "received_at": reading.get("received_at"),
        "temperature": float(reading.get("temperature", 0.0)),
        "humidity": float(reading.get("humidity", 0.0)),
        "mq135_co2": float(reading.get("mq135_co2", 0.0)),
        "mq136_h2s": float(reading.get("mq136_h2s", 0.0)),
        "mq137_nh3": float(reading.get("mq137_nh3", 0.0)),
        "quality_level": reading.get("quality_level", "UNKNOWN"),
        "wifi_rssi": reading.get("wifi_rssi"),
        "sensor_status": reading.get("sensor_status", {}),
    }


def store_reading(reading: Dict[str, Any]) -> bool:
    """Store a normalized reading in the local SQLite database.

    Uses the ORIGINAL reading timestamp from the device (not local Pi time)
    and passes source_id for deduplication via a UNIQUE constraint.
    """
    timestamp = _parse_api_timestamp(reading.get("reading_time"))
    if timestamp is None:
        raise ValueError(
            f"Reading {reading.get('id', 'unknown')} has no valid reading_time"
        )

    db = get_db_manager()
    row_id = db.insert_sensor_reading({
        "timestamp": timestamp,
        "received_at": reading.get("received_at"),
        "device_id": reading.get("device_id", "ESP32-MeatMonitor"),
        "source_id": reading.get("source_id") or None,
        "temperature": reading["temperature"],
        "humidity": reading["humidity"],
        "mq135_co2": reading["mq135_co2"],
        "mq136_h2s": reading["mq136_h2s"],
        "mq137_nh3": reading["mq137_nh3"],
        "quality_level": reading["quality_level"],
        "wifi_rssi": reading.get("wifi_rssi"),
        "sensor_status": reading.get("sensor_status", {}),
    })
    return row_id > 0


# ============================================================================
# Recovery: Catch Up on Missed Readings
# ============================================================================

def catch_up(bookmark: Dict[str, Any]) -> Dict[str, Any]:
    """
    Called on startup. Fetches all readings since the bookmark
    using the /history endpoint and stores them in the DB.

    Returns:
        Updated bookmark dict
    """
    logger.info(
        "Catching up from bookmark: id=%s, ts=%s",
        bookmark.get("last_id"),
        bookmark.get("last_timestamp"),
    )
    return _poll_history(bookmark, operation="catch-up")


# ============================================================================
# Normal Operation: Poll Current
# ============================================================================

def poll_current(bookmark: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch recent history from the API and advance the timestamp bookmark.

    The function name is retained for compatibility with the systemd client,
    but /current is deliberately not used because that server endpoint can be
    pinned to an older high-ID record after a server ID reset.

    Returns:
        Updated bookmark dict
    """
    return _poll_history(bookmark, operation="poll")


def _poll_history(
    bookmark: Dict[str, Any], operation: str = "poll"
) -> Dict[str, Any]:
    """Fetch, deduplicate, store, and bookmark timestamp-ordered history."""
    params = {
        "device_id": config.SENSOR_API_DEVICE_ID,
        "from": _history_query_start(bookmark),
        "limit": config.SENSOR_API_HISTORY_LIMIT,
    }
    data = api_get("/history", params=params)
    if data is None:
        raise ConnectionError("Sensor API /history request failed")
    if not isinstance(data, dict):
        raise ValueError("Sensor API /history response is not an object")

    raw_readings = data.get("readings", [])
    if not isinstance(raw_readings, list):
        raise ValueError("Sensor API /history readings field is not a list")
    if not raw_readings:
        logger.info("History %s found no readings from %s", operation, params["from"])
        return bookmark

    cursor_time, cursor_id, cursor_is_recent = _bookmark_cursor(bookmark)
    cursor_key = (cursor_time, cursor_id)
    normalized: List[Dict[str, Any]] = []
    invalid_count = 0

    for raw in raw_readings:
        if not isinstance(raw, dict) or _parse_api_timestamp(raw.get("reading_time")) is None:
            invalid_count += 1
            continue
        reading = normalize_history(raw)
        # Include the cursor record itself because /history may be inclusive;
        # SQLite source_id deduplication makes replay safe.
        if not cursor_is_recent or _reading_sort_key(reading) >= cursor_key:
            normalized.append(reading)

    normalized.sort(key=_reading_sort_key)
    if invalid_count:
        logger.warning("Ignored %d history readings with invalid timestamps", invalid_count)
    if not normalized:
        return bookmark

    inserted_count = 0
    duplicate_count = 0
    for reading in normalized:
        if store_reading(reading):
            inserted_count += 1
        else:
            duplicate_count += 1

    newest = max(normalized, key=_reading_sort_key)
    newest_key = _reading_sort_key(newest)
    if cursor_is_recent and newest_key <= cursor_key:
        logger.debug(
            "History %s replayed %d already-processed reading(s)",
            operation,
            duplicate_count,
        )
        return bookmark

    new_bookmark = {
        "last_id": newest["id"],
        "last_timestamp": newest["reading_time"],
    }
    save_bookmark(new_bookmark["last_id"], new_bookmark["last_timestamp"])
    logger.info(
        "History %s complete: inserted=%d, duplicates=%d, bookmark id=%s ts=%s",
        operation,
        inserted_count,
        duplicate_count,
        new_bookmark["last_id"],
        new_bookmark["last_timestamp"],
    )
    return new_bookmark


# ============================================================================
# Dashboard Helper — Lightweight API Client for Streamlit
# ============================================================================

class SensorAPIClient:
    """
    Lightweight client used by the Streamlit dashboard to check API status
    and fetch the current reading for display. The heavy lifting (catch-up,
    bookmarking, bulk storage) is done by the background service.
    """

    def __init__(self):
        self.last_fetch_time: Optional[float] = None
        self.last_error: Optional[str] = None
        self.connected: bool = False

    def fetch_current(self) -> Optional[Dict[str, Any]]:
        """Fetch the newest recent history reading for dashboard display."""
        headers = {"x-api-key": config.SENSOR_API_KEY}
        try:
            history_start = _format_api_timestamp(
                datetime.now(timezone.utc)
                - timedelta(hours=config.SENSOR_API_RECOVERY_LOOKBACK_HOURS)
            )
            resp = requests.get(
                f"{config.SENSOR_API_BASE}/history",
                headers=headers,
                params={
                    "device_id": config.SENSOR_API_DEVICE_ID,
                    "from": history_start,
                    "limit": config.SENSOR_API_DASHBOARD_HISTORY_LIMIT,
                },
                timeout=config.SENSOR_API_TIMEOUT,
            )
            if resp.status_code == 200:
                payload = resp.json()
                readings = payload.get("readings", [])
                self.last_fetch_time = time.time()
                self.connected = True
                if not readings:
                    self.last_error = "Server reachable, but no recent sensor readings"
                    return None

                valid_readings = [
                    reading for reading in readings
                    if isinstance(reading, dict)
                    and _parse_api_timestamp(reading.get("reading_time")) is not None
                ]
                if not valid_readings:
                    self.last_error = "Server returned no valid timestamped readings"
                    return None

                newest = max(valid_readings, key=_reading_sort_key)
                self.last_error = None
                return {
                    "id": newest.get("id"),
                    "device_id": newest.get("device_id"),
                    "timestamp": newest.get("reading_time"),
                    "received_at": newest.get("received_at"),
                    "temperature": newest.get("temperature"),
                    "humidity": newest.get("humidity"),
                    "co2_ppm": newest.get("mq135_co2"),
                    "h2s_ppm": newest.get("mq136_h2s"),
                    "nh3_ppm": newest.get("mq137_nh3"),
                    "quality": newest.get("quality_level"),
                    "wifi_rssi": newest.get("wifi_rssi"),
                    "sensor_status": newest.get("sensor_status", {}),
                }
            else:
                self.last_error = f"HTTP {resp.status_code}"
                self.connected = False
                return None
        except Exception as e:
            self.last_error = str(e)
            self.connected = False
            return None

    def is_connected(self) -> bool:
        """Check if the API is reachable (based on last successful fetch)."""
        if self.last_fetch_time is None:
            return False
        return (time.time() - self.last_fetch_time) < 30

    def get_bookmark_info(self) -> Dict[str, Any]:
        """Get current bookmark info for status display."""
        return load_bookmark()


# Singleton for dashboard use
_client: Optional[SensorAPIClient] = None


def get_api_client() -> SensorAPIClient:
    """Get or create the singleton API client for the dashboard."""
    global _client
    if _client is None:
        _client = SensorAPIClient()
    return _client
