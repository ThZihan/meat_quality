"""
API Client for Meat Quality Monitoring System.

Implements the Raspberry Pi Data Recovery Strategy:
  - Tracks last seen reading ID in a local bookmark file
  - On startup: catches up on all missed readings via /history
  - During normal operation: polls /current every N seconds
  - Retries with exponential backoff on failures

The data flow is:
  ESP32 → Remote API → This client → Local SQLite DB → Dashboard reads DB
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests

import config
from db_manager import get_db_manager

logger = logging.getLogger(__name__)


# ============================================================================
# Bookmark Management
# ============================================================================

def load_bookmark() -> Dict[str, Any]:
    """Load last seen reading ID and timestamp from disk."""
    try:
        with open(config.BOOKMARK_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_id": 0, "last_timestamp": None}


def save_bookmark(last_id: int, last_timestamp: str) -> None:
    """Persist bookmark to disk after each successful processing cycle."""
    try:
        with open(config.BOOKMARK_FILE, "w") as f:
            json.dump({"last_id": last_id, "last_timestamp": last_timestamp}, f)
    except OSError as e:
        logger.error("Failed to save bookmark: %s", e)


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
        "id": int(data.get("id", 0)),
        "device_id": data.get("device_id", "ESP32-MeatMonitor"),
        "reading_time": data.get("timestamp", ""),
        "temperature": float(data.get("temperature", 0.0)),
        "humidity": float(data.get("humidity", 0.0)),
        "mq135_co2": float(data.get("co2_ppm", 0.0)),
        "mq136_h2s": float(data.get("h2s_ppm", 0.0)),
        "mq137_nh3": float(data.get("nh3_ppm", 0.0)),
        "quality_level": data.get("quality", "UNKNOWN"),
        "wifi_rssi": data.get("wifi_rssi"),
    }


def normalize_history(reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a /history reading into a common reading dict.

    /history fields: temperature, humidity, mq135_co2, mq136_h2s, mq137_nh3, quality_level
    """
    return {
        "id": int(reading.get("id", 0)),
        "device_id": reading.get("device_id", "ESP32-MeatMonitor"),
        "reading_time": reading.get("reading_time", ""),
        "temperature": float(reading.get("temperature", 0.0)),
        "humidity": float(reading.get("humidity", 0.0)),
        "mq135_co2": float(reading.get("mq135_co2", 0.0)),
        "mq136_h2s": float(reading.get("mq136_h2s", 0.0)),
        "mq137_nh3": float(reading.get("mq137_nh3", 0.0)),
        "quality_level": reading.get("quality_level", "UNKNOWN"),
        "wifi_rssi": reading.get("wifi_rssi"),
    }


def store_reading(reading: Dict[str, Any]) -> None:
    """Store a normalized reading in the local SQLite database."""
    db = get_db_manager()
    try:
        db.insert_sensor_reading({
            "timestamp": datetime.now(),
            "device_id": reading.get("device_id", "ESP32-MeatMonitor"),
            "temperature": reading["temperature"],
            "humidity": reading["humidity"],
            "mq135_co2": reading["mq135_co2"],
            "mq136_h2s": reading["mq136_h2s"],
            "mq137_nh3": reading["mq137_nh3"],
            "quality_level": reading["quality_level"],
        })
    except Exception as e:
        logger.error("Failed to store reading in DB: %s", e)


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
    last_ts = bookmark.get("last_timestamp")
    if not last_ts:
        logger.info("No bookmark found. Starting fresh — no recovery needed.")
        return bookmark

    logger.info("Catching up from bookmark: id=%s, ts=%s", bookmark.get("last_id"), last_ts)

    params = {
        "device_id": config.SENSOR_API_DEVICE_ID,
        "from": last_ts,
        "limit": config.SENSOR_API_HISTORY_LIMIT,
    }

    data = api_get("/history", params)
    if not data:
        logger.warning("Catch-up failed. Will retry on next cycle.")
        return bookmark

    readings = data.get("readings", [])
    if not readings:
        logger.info("No missed readings. Up to date!")
        return bookmark

    # Filter: only process readings NEWER than our bookmark
    last_id = bookmark.get("last_id", 0)
    new_readings = [r for r in readings if int(r.get("id", 0)) > last_id]

    # Sort ascending (oldest first) so we process in order
    new_readings.sort(key=lambda r: r.get("reading_time", ""))

    logger.info("Recovering %d missed readings...", len(new_readings))

    for raw in new_readings:
        reading = normalize_history(raw)
        store_reading(reading)
        last_id = reading["id"]
        last_ts = reading["reading_time"]

    # Update bookmark after catch-up
    new_bookmark = {"last_id": last_id, "last_timestamp": last_ts}
    save_bookmark(last_id, last_ts)
    logger.info("Catch-up complete. New bookmark: id=%s", last_id)

    return new_bookmark


# ============================================================================
# Normal Operation: Poll Current
# ============================================================================

def poll_current(bookmark: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch the current reading from the API. If it's newer than our bookmark,
    store it and update the bookmark.

    Returns:
        Updated bookmark dict
    """
    data = api_get("/current", params={"device_id": config.SENSOR_API_DEVICE_ID})
    if data is None:
        return bookmark

    reading = normalize_current(data)
    reading_id = reading["id"]
    last_id = bookmark.get("last_id", 0)

    if reading_id > last_id:
        store_reading(reading)
        new_bookmark = {
            "last_id": reading_id,
            "last_timestamp": reading["reading_time"],
        }
        save_bookmark(reading_id, reading["reading_time"])
        return new_bookmark

    # Same reading as last poll — skip
    return bookmark


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
        """Fetch the current reading from the API (for display only)."""
        headers = {"x-api-key": config.SENSOR_API_KEY}
        try:
            resp = requests.get(
                f"{config.SENSOR_API_BASE}/current",
                headers=headers,
                params={"device_id": config.SENSOR_API_DEVICE_ID},
                timeout=config.SENSOR_API_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.last_fetch_time = time.time()
                self.last_error = None
                self.connected = True
                return data
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
