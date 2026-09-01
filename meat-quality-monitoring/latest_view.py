#!/usr/bin/env python3
"""
Minimal "Latest View" web page for the Meat Quality Monitoring System.

Shows exactly two things on one auto-updating page:
  * LEFT  : the latest captured camera image (capture time underneath)
  * RIGHT : the latest sensor reading (reading time underneath)

Data sources
------------
Latest image  : capture.py writes images to PENDING_SYNC_DIR and records them
                in the SQLite ledger (SYNC_DB_PATH). sync.py deletes files
                after upload, so a background watcher thread caches a copy of
                the newest capture before it disappears.
Latest data   : sensor_readings table in the main dashboard database
                (data/meat_monitor.db), newest row by timestamp.

Run
---
    python3 latest_view.py            # serves on port 8600

Environment overrides
---------------------
    LATEST_VIEW_PORT   (default 8600)
    PENDING_SYNC_DIR   (default /home/zihan/pending_sync)
    SYNC_DB_PATH       (default /home/zihan/sync_state.db)
    SENSOR_DB_PATH     (default <script dir>/data/meat_monitor.db)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, Response, jsonify, render_template

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent

PORT = int(os.environ.get("LATEST_VIEW_PORT", "8600"))
HOST = os.environ.get("LATEST_VIEW_HOST", "0.0.0.0")

PENDING_SYNC_DIR = Path(
    os.environ.get("PENDING_SYNC_DIR", "/home/zihan/pending_sync")
)
SYNC_LEDGER_PATH = Path(
    os.environ.get("SYNC_DB_PATH", "/home/zihan/sync_state.db")
)
SENSOR_DB_PATH = Path(
    os.environ.get(
        "SENSOR_DB_PATH", str(SCRIPT_DIR / "data" / "meat_monitor.db")
    )
)

# Fallback folders scanned only until the first real capture is cached.
FALLBACK_IMAGE_DIRS = [SCRIPT_DIR / "captures", SCRIPT_DIR / "images"]

# Cache where the newest capture is kept safe from sync.py cleanup.
CACHE_DIR = SCRIPT_DIR / "data" / "latest_view"
CACHE_IMAGE_PATH = CACHE_DIR / "latest.jpg"
CACHE_META_PATH = CACHE_DIR / "meta.json"

# A file smaller than this is not a real JPEG (camera-unplugged placeholders).
MIN_VALID_IMAGE_BYTES = 1024
JPEG_SOI_MARKER = b"\xff\xd8"

# How often the watcher looks for a new capture (capture runs every 30 s,
# sync deletes files every 60 s -> 2 s polling never misses one for long).
WATCHER_INTERVAL_SECONDS = 2.0

TIME_DISPLAY_FORMAT = "%d %b %Y, %I:%M:%S %p"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("latest_view")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_local(dt: datetime) -> str:
    """Format a datetime in the machine's local timezone for display."""
    return dt.astimezone().strftime(TIME_DISPLAY_FORMAT)


def _parse_ledger_time(value: Optional[str]) -> Optional[datetime]:
    """Parse capture_time strings stored by capture.py (naive local time)."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _connect_readonly(db_path: Path) -> Optional[sqlite3.Connection]:
    """Open a SQLite database read-only; return None if unavailable."""
    if not db_path.exists():
        return None
    try:
        return sqlite3.connect(
            f"file:{db_path}?mode=ro", uri=True, timeout=2.0
        )
    except sqlite3.Error as error:
        logger.debug("Cannot open %s read-only: %s", db_path, error)
        return None


def _read_valid_jpeg(path: Path) -> Optional[bytes]:
    """Read a file fully and verify it looks like a real JPEG."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if (
        len(data) < MIN_VALID_IMAGE_BYTES
        or not data.startswith(JPEG_SOI_MARKER)
    ):
        return None
    return data


def _newest_in_dir(directory: Path) -> Optional[Path]:
    """Newest valid-looking .jpg file in a directory (by modification time)."""
    try:
        candidates = [
            entry
            for entry in directory.iterdir()
            if entry.is_file()
            and entry.suffix.lower() == ".jpg"
            and entry.stat().st_size >= MIN_VALID_IMAGE_BYTES
        ]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda entry: entry.stat().st_mtime)


def _ledger_latest_row() -> Optional[dict]:
    """Newest row from the capture ledger, or None."""
    conn = _connect_readonly(SYNC_LEDGER_PATH)
    if conn is None:
        return None
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, filename, filepath, capture_time, status
            FROM images
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as error:
        logger.debug("Ledger query failed: %s", error)
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Capture watcher thread
# ---------------------------------------------------------------------------

watch_state_lock = threading.Lock()
watch_state: dict = {"available": False, "capture_time": None, "epoch": 0.0}


def _update_cache(jpeg_bytes: bytes, capture_time: Optional[datetime],
                  filename: str, source_key: str) -> None:
    """Atomically store the newest image + metadata in the cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = CACHE_IMAGE_PATH.with_suffix(".tmp")
    tmp_path.write_bytes(jpeg_bytes)
    tmp_path.replace(CACHE_IMAGE_PATH)

    epoch = time.time()
    meta = {
        "filename": filename,
        "source_key": source_key,
        "capture_time": (
            capture_time.strftime(TIME_DISPLAY_FORMAT)
            if capture_time
            else datetime.fromtimestamp(epoch).strftime(TIME_DISPLAY_FORMAT)
        ),
        "epoch": epoch,
    }
    meta_tmp = CACHE_META_PATH.with_suffix(".tmp")
    meta_tmp.write_text(json.dumps(meta))
    meta_tmp.replace(CACHE_META_PATH)

    with watch_state_lock:
        watch_state.update(
            available=True,
            capture_time=meta["capture_time"],
            epoch=epoch,
        )
    logger.info("Cached latest capture %s (captured %s)", filename,
                meta["capture_time"])


def _load_cached_meta() -> None:
    """Restore cached image metadata after a restart (if the file exists)."""
    if not (CACHE_IMAGE_PATH.exists() and CACHE_META_PATH.exists()):
        return
    try:
        meta = json.loads(CACHE_META_PATH.read_text())
        with watch_state_lock:
            watch_state.update(
                available=True,
                capture_time=meta.get("capture_time"),
                epoch=CACHE_IMAGE_PATH.stat().st_mtime,
            )
    except (OSError, ValueError, KeyError):
        pass


def watcher_tick() -> None:
    """One poll cycle: find the newest capture and cache it if it is new."""
    # 1) Best source: newest ledger row (accurate capture_time).
    ledger_row = _ledger_latest_row()
    candidates = []
    if ledger_row:
        ledger_path = Path(ledger_row["filepath"])
        if ledger_path.exists():
            candidates.append(
                (ledger_path, _parse_ledger_time(ledger_row["capture_time"]),
                 f"ledger:{ledger_row['id']}")
            )
    # 2) Fallback: newest valid file sitting in the pending directory.
    newest_pending = _newest_in_dir(PENDING_SYNC_DIR)
    if newest_pending is not None:
        candidates.append(
            (newest_pending,
             datetime.fromtimestamp(newest_pending.stat().st_mtime),
             f"pending:{newest_pending.name}")
        )
    # 3) Last resort (dev machines): newest file in captures/ or images/.
    for directory in FALLBACK_IMAGE_DIRS:
        fallback = _newest_in_dir(directory)
        if fallback is not None:
            candidates.append(
                (fallback,
                 datetime.fromtimestamp(fallback.stat().st_mtime),
                 f"fallback:{directory.name}:{fallback.name}")
            )

    # Skip if we already cached this exact capture.
    try:
        cached_meta = json.loads(CACHE_META_PATH.read_text())
    except (OSError, ValueError):
        cached_meta = {}
    cached_key = cached_meta.get("source_key")

    for path, captured_at, source_key in candidates:
        if source_key == cached_key and CACHE_IMAGE_PATH.exists():
            return
        jpeg_bytes = _read_valid_jpeg(path)
        if jpeg_bytes is None:
            continue
        _update_cache(jpeg_bytes, captured_at, path.name, source_key)
        return


def watcher_loop() -> None:
    """Background thread entry point."""
    while True:
        try:
            watcher_tick()
        except Exception as error:  # never let the watcher die
            logger.error("Watcher error: %s", error)
        time.sleep(WATCHER_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Latest sensor reading
# ---------------------------------------------------------------------------


def get_latest_reading() -> Optional[dict]:
    """Newest row from sensor_readings, or None if unavailable."""
    conn = _connect_readonly(SENSOR_DB_PATH)
    if conn is None:
        return None
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT timestamp, device_id, temperature, humidity,
                   mq135_co2, mq136_h2s, mq137_nh3, quality_level, wifi_rssi
            FROM sensor_readings
            ORDER BY timestamp DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as error:
        logger.error("Sensor query failed: %s", error)
        return None
    finally:
        conn.close()


def _reading_timestamp_display(row: dict) -> Optional[str]:
    """Convert the stored UTC timestamp string to local display time."""
    raw = row.get("timestamp")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return str(raw)
    if parsed.tzinfo is None:  # legacy rows stored without timezone
        from datetime import timezone

        parsed = parsed.replace(tzinfo=timezone.utc)
    return _fmt_local(parsed)


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """The minimal two-panel page."""
    return render_template("latest_view.html")


@app.route("/api/latest")
def api_latest():
    """JSON snapshot of the latest capture + latest sensor reading."""
    with watch_state_lock:
        image_state = dict(watch_state)

    reading = get_latest_reading()
    reading_payload = {"available": False}
    if reading:
        reading_payload = {
            "available": True,
            "time": _reading_timestamp_display(reading),
            "temperature": round(reading["temperature"], 2),
            "humidity": round(reading["humidity"], 2),
            "voc": round(reading["mq135_co2"], 2),
            "h2s": round(reading["mq136_h2s"], 2),
            "nh3": round(reading["mq137_nh3"], 2),
            "quality": reading.get("quality_level") or "UNKNOWN",
        }

    return jsonify(
        {
            "image": {
                "available": image_state.get("available", False),
                "capture_time": image_state.get("capture_time"),
                "epoch": image_state.get("epoch", 0.0),
            },
            "reading": reading_payload,
        }
    )


@app.route("/latest_image")
def latest_image():
    """Serve the cached newest capture (never cached by the browser)."""
    if not CACHE_IMAGE_PATH.exists():
        return Response("No capture cached yet", status=503)
    jpeg_bytes = _read_valid_jpeg(CACHE_IMAGE_PATH)
    if jpeg_bytes is None:
        return Response("Cached capture unreadable", status=503)
    return Response(
        jpeg_bytes,
        mimetype="image/jpeg",
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    _load_cached_meta()
    try:
        watcher_tick()  # seed the cache immediately
    except Exception as error:
        logger.error("Initial watcher tick failed: %s", error)

    thread = threading.Thread(target=watcher_loop, daemon=True,
                              name="capture-watcher")
    thread.start()

    logger.info(
        "Latest view starting on http://0.0.0.0:%d (pending dir: %s)",
        PORT, PENDING_SYNC_DIR,
    )
    app.run(host=HOST, port=PORT, threaded=True)


if __name__ == "__main__":
    main()
