"""
Configuration file for Meat Quality Monitoring System
Contains all configurable parameters for API, database, and sensor thresholds
"""

import os

# ============================================================================
# Environment Variables
# ============================================================================

# Load .env file if present (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed; rely on system env vars
    pass

# ============================================================================
# Sensor API Configuration
# ============================================================================

# Remote API base URL (without endpoint path)
SENSOR_API_BASE = os.environ.get(
    "SENSOR_API_BASE",
    "https://meat-monitor.kalobiral.com.bd/api/meat-data"
)
SENSOR_API_KEY = os.environ.get("SENSOR_API_KEY", "")
SENSOR_API_TIMEOUT = int(os.environ.get("SENSOR_API_TIMEOUT", "5"))  # seconds (10s used to stall page reruns when the hotspot flaps)

# Device identifier used as a query parameter for /current, /latest, /history
SENSOR_API_DEVICE_ID = os.environ.get("SENSOR_API_DEVICE_ID", "ESP32-MeatMonitor")

# Polling & Recovery Settings
SENSOR_API_POLL_INTERVAL = int(os.environ.get("SENSOR_API_POLL_INTERVAL", "5"))  # seconds between /current polls
SENSOR_API_MAX_RETRIES = int(os.environ.get("SENSOR_API_MAX_RETRIES", "3"))  # retries per request
SENSOR_API_RETRY_BASE_DELAY = int(os.environ.get("SENSOR_API_RETRY_BASE_DELAY", "2"))  # seconds (doubles each retry)
SENSOR_API_HISTORY_LIMIT = int(os.environ.get("SENSOR_API_HISTORY_LIMIT", "5000"))  # max readings per /history call
SENSOR_API_CATCHUP_FAILURE_THRESHOLD = int(os.environ.get("SENSOR_API_CATCHUP_FAILURE_THRESHOLD", "5"))  # consecutive failures before re-catch-up
# Bound history queries to a recent window when a bookmark is missing or stale.
# This also recovers safely if the server database is restored and numeric IDs
# restart below the Pi's previous bookmark.
SENSOR_API_RECOVERY_LOOKBACK_HOURS = int(
    os.environ.get("SENSOR_API_RECOVERY_LOOKBACK_HOURS", "24")
)
SENSOR_API_DASHBOARD_HISTORY_LIMIT = int(
    os.environ.get("SENSOR_API_DASHBOARD_HISTORY_LIMIT", "100")
)

# Bookmark file — tracks last seen reading ID for recovery
BOOKMARK_FILE = os.path.expanduser(
    os.environ.get("BOOKMARK_FILE", "~/.meat_monitor_bookmark.json")
)

# ============================================================================
# MQTT Configuration (legacy - kept for reference)
# ============================================================================

# MQTT Broker Settings
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = "meat-quality/data"
MQTT_STATUS_TOPIC = "meat-quality/status"
MQTT_LWT_TOPIC = "meat-quality/lwt"
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")

# MQTT Connection Settings
MQTT_KEEPALIVE = 60  # Keep-alive interval in seconds
MQTT_RECONNECT_DELAY = 5  # Delay between reconnection attempts (seconds)
MQTT_QOS = 1  # Quality of Service: 0=at most once, 1=at least once, 2=exactly once

# ============================================================================
# Database Configuration
# ============================================================================

# SQLite Database Settings
DB_PATH = "data/meat_monitor.db"
DB_RETENTION_DAYS = 30  # Keep data for 30 days (0 = keep forever)
DB_BACKUP_ENABLED = True
DB_BACKUP_DIR = "data/backups"
DB_BACKUP_INTERVAL_HOURS = 24  # Backup every 24 hours

# ============================================================================
# Sensor Thresholds (based on research paper)
# ============================================================================

# H2S (MQ136) Thresholds in ppm
H2S_FRESH_THRESHOLD = 10.0      # Fresh: < 10 ppm
H2S_WARNING_THRESHOLD = 50.0    # Warning: 10-50 ppm
H2S_CRITICAL_THRESHOLD = 100.0  # Critical: > 50 ppm

# NH3 (MQ137) Thresholds in ppm
NH3_FRESH_THRESHOLD = 25.0      # Fresh: < 25 ppm
NH3_WARNING_THRESHOLD = 100.0   # Warning: 25-100 ppm
NH3_CRITICAL_THRESHOLD = 200.0  # Critical: > 100 ppm

# VOC (MQ135) Thresholds in ppm
VOC_FRESH_THRESHOLD = 600.0     # Fresh: < 600 ppm
VOC_WARNING_THRESHOLD = 1000.0   # Warning: 600-1000 ppm
VOC_CRITICAL_THRESHOLD = 1200.0  # Critical: > 1000 ppm

# Temperature thresholds (°C)
TEMP_OPTIMAL_MIN = 0.0    # Optimal storage temperature minimum
TEMP_OPTIMAL_MAX = 4.0    # Optimal storage temperature maximum
TEMP_WARNING_HIGH = 10.0   # Warning threshold for high temperature
TEMP_CRITICAL_HIGH = 15.0  # Critical threshold for high temperature

# Humidity thresholds (%)
HUMIDITY_OPTIMAL_MIN = 60.0  # Optimal humidity minimum
HUMIDITY_OPTIMAL_MAX = 80.0  # Optimal humidity maximum
HUMIDITY_WARNING_LOW = 50.0  # Warning threshold for low humidity
HUMIDITY_WARNING_HIGH = 90.0  # Warning threshold for high humidity

# ============================================================================
# Dashboard Configuration
# ============================================================================

# Data Display Settings
MAX_HISTORY_READINGS = 1000  # Maximum number of readings to keep in memory
CHART_REFRESH_INTERVAL = 5  # Dashboard refresh interval in seconds (1s full-script reruns overloaded the Pi and made page loads crawl)
AUTO_REFRESH_ENABLED = True  # Enable automatic dashboard refresh for real-time data updates

# Visualization Settings
HISTORY_DISPLAY_COUNT = 50  # Number of readings to display in charts (reduced from 100 for faster queries)
HEATMAP_MIN_READINGS = 10    # Minimum readings needed for correlation heatmap

# ============================================================================
# Quality Level Mapping (ESP32 5-level -> Pi 4-level)
# ============================================================================

# Mapping from ESP32 quality levels to Pi dashboard status.
# NOTE: The ESP32 firmware now sends EXCELLENT/GOOD/MODERATE/POOR/CRITICAL
# (the previous FAIR/SPOILED values were rejected by the server with HTTP 400).
QUALITY_LEVEL_MAP = {
    "EXCELLENT": "SAFE",
    "GOOD": "SAFE",
    "MODERATE": "WARNING",
    "POOR": "SPOILED",
    "CRITICAL": "CRITICAL",
}

# Quality level colors for dashboard
QUALITY_COLORS = {
    "SAFE": "#00AA00",      # Green
    "WARNING": "#FF9800",   # Orange
    "SPOILED": "#FF0000",   # Red
    "CRITICAL": "#8B0000"   # Dark Red
}

# ============================================================================
# Data Export Configuration
# ============================================================================

EXPORT_DIR = "data/exports"
EXPORT_FORMATS = ["csv", "json"]  # Supported export formats

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "data/meat_monitor.log"
LOG_MAX_SIZE_MB = 10
LOG_BACKUP_COUNT = 5

# ============================================================================
# Mock Data Configuration (for testing)
# ============================================================================

# Mock data simulation settings
MOCK_ENABLED = False  # Enable mock data mode (for testing)
MOCK_TEMP_DEFAULT = 3.5  # Default temperature for mock data (°C)
MOCK_HUMIDITY_DEFAULT = 75.0  # Default humidity for mock data (%)
MOCK_H2S_DEFAULT = 5.0  # Default H2S for mock data (ppm)
MOCK_NH3_DEFAULT = 15.0  # Default NH3 for mock data (ppm)
MOCK_VOC_DEFAULT = 450.0  # Default VOC for mock data (ppm)

# ============================================================================
# Advanced Settings
# ============================================================================

# Enable/disable features
ENABLE_DATABASE = True  # Enable SQLite database storage
ENABLE_MQTT = True  # Enable MQTT client
ENABLE_HISTORICAL_ANALYSIS = True  # Enable historical data analysis
ENABLE_DATA_EXPORT = True  # Enable data export functionality

# Performance settings
DB_CONNECTION_POOL_SIZE = 5  # Number of database connections in pool
MQTT_MESSAGE_QUEUE_SIZE = 100  # Maximum number of MQTT messages to queue


# ============================================================================
# BLE Ingest (ESP32 -> Pi)
# ============================================================================
# The ESP32 no longer has WiFi. It is a BLE peripheral and this Pi is the only
# consumer of its readings, so the Pi -- not the cloud -- is now the point at
# which a reading becomes durable.

# Advertised name of the sensor node. The receiver matches on the service UUID
# from ble_protocol.py first and only falls back to this name.
BLE_DEVICE_NAME = os.environ.get("BLE_DEVICE_NAME", "MeatNode")

# Optional hard MAC pin. Set this once the node's address is known to stop the
# Pi from ever attaching to a look-alike advertiser.
BLE_DEVICE_ADDRESS = os.environ.get("BLE_DEVICE_ADDRESS", "").strip()

# device_id recorded against BLE readings. Matches the firmware constant and
# the existing rows, so history stays continuous across the cutover.
BLE_DEVICE_ID = os.environ.get("BLE_DEVICE_ID", "ESP32-MeatMonitor")

BLE_SCAN_TIMEOUT = float(os.environ.get("BLE_SCAN_TIMEOUT", "10"))
BLE_CONNECT_TIMEOUT = float(os.environ.get("BLE_CONNECT_TIMEOUT", "20"))

# Backoff between reconnect attempts, in seconds. At ~10 inches a disconnect
# means the node rebooted or the link glitched, so retry quickly at first.
BLE_RECONNECT_MIN_DELAY = float(os.environ.get("BLE_RECONNECT_MIN_DELAY", "2"))
BLE_RECONNECT_MAX_DELAY = float(os.environ.get("BLE_RECONNECT_MAX_DELAY", "30"))

# Re-push the wall clock to the node this often while connected. The ESP has no
# RTC and no NTP, so this is the only thing keeping its timestamps honest.
BLE_TIME_SYNC_INTERVAL = float(os.environ.get("BLE_TIME_SYNC_INTERVAL", "300"))

# Treat the link as dead if no notification arrives in this long. The node sends
# every 3 s, so silence well past that means the connection is a zombie.
BLE_IDLE_TIMEOUT = float(os.environ.get("BLE_IDLE_TIMEOUT", "60"))


# ============================================================================
# Cloud Uploader (Pi -> server)
# ============================================================================
# Readings are written to SQLite first and queued in pending_sync. The uploader
# drains that queue independently, so a server outage costs nothing but delay.

CLOUD_UPLOAD_INTERVAL = float(os.environ.get("CLOUD_UPLOAD_INTERVAL", "15"))
CLOUD_UPLOAD_BATCH = int(os.environ.get("CLOUD_UPLOAD_BATCH", "50"))
CLOUD_UPLOAD_TIMEOUT = int(os.environ.get("CLOUD_UPLOAD_TIMEOUT", "15"))
CLOUD_UPLOAD_MAX_RETRIES = int(os.environ.get("CLOUD_UPLOAD_MAX_RETRIES", "3"))
# Rows that keep failing are parked rather than retried forever; they stay in
# the table (and in sensor_readings) so nothing is silently discarded.
CLOUD_UPLOAD_MAX_ATTEMPTS = int(os.environ.get("CLOUD_UPLOAD_MAX_ATTEMPTS", "20"))


# ============================================================================
# Storage Guard
# ============================================================================
# The Pi holds the only copy of a reading between capture and upload, so it must
# never run out of room. The guard keeps a floor of free space by reclaiming the
# OLDEST already-uploaded data first -- the server keeps the long-term archive.

STORAGE_MIN_FREE_BYTES = int(
    os.environ.get("STORAGE_MIN_FREE_BYTES", str(5 * 1024 * 1024 * 1024))  # 5 GiB
)
# Reclaim past the floor so the guard is not re-triggered on every cycle.
STORAGE_TARGET_FREE_BYTES = int(
    os.environ.get("STORAGE_TARGET_FREE_BYTES", str(6 * 1024 * 1024 * 1024))  # 6 GiB
)
STORAGE_CHECK_INTERVAL = float(os.environ.get("STORAGE_CHECK_INTERVAL", "300"))

# Uploaded images are moved here instead of being deleted, so the Pi keeps its
# own copy until space actually runs short.
IMAGE_ARCHIVE_DIR = os.path.expanduser(
    os.environ.get("IMAGE_ARCHIVE_DIR", "~/image_archive")
)

# How many rows to delete per pass when trimming the database.
STORAGE_DB_PRUNE_BATCH = int(os.environ.get("STORAGE_DB_PRUNE_BATCH", "5000"))
# Never prune below this many readings, however tight space gets.
STORAGE_DB_MIN_ROWS = int(os.environ.get("STORAGE_DB_MIN_ROWS", "10000"))

# How often the Pi tells the node what it has durably stored. ACKs are
# cumulative (one write clears every reading up to that sequence number), so
# this is a batching interval, not a per-reading cost. GATT writes are the
# fragile half of the BLE link, so writing rarely is deliberate.
BLE_ACK_INTERVAL = float(os.environ.get("BLE_ACK_INTERVAL", "1.0"))

# Push the Pi's wall clock to the node so its readings carry real epochs.
#
# OFF by default, from measurement: with the clock push enabled this link drops
# roughly 2.4 s after every write, yielding one reading per connection. With it
# disabled the same hardware holds a single connection indefinitely and streams
# continuously (80 s, 50+ readings, no disconnects).
#
# Turning it off costs nothing in accuracy. Every reading carries the age in ms
# since it was captured, and the receiver subtracts that from the Pi's own
# clock; only sensor_status.time_source changes, from "esp_clock" to
# "pi_clock_minus_age". Set BLE_PUSH_CLOCK=1 to re-enable and re-measure.
BLE_PUSH_CLOCK = os.environ.get("BLE_PUSH_CLOCK", "0") not in ("0", "false", "False")

# Pause between individual uploads. The server rate-limits (HTTP 429) when a
# backlog is pushed at full speed; the uploader treats 429 as retryable, but
# pacing avoids provoking it in the first place.
CLOUD_UPLOAD_THROTTLE = float(os.environ.get("CLOUD_UPLOAD_THROTTLE", "0.4"))
