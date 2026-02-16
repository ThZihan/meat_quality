"""
Configuration file for Meat Quality Monitoring System
Contains all configurable parameters for MQTT, database, and sensor thresholds
"""

# ============================================================================
# MQTT Configuration
# ============================================================================

# MQTT Broker Settings
MQTT_BROKER = "localhost"  # Mosquitto runs on the same Raspberry Pi
MQTT_PORT = 1883
MQTT_TOPIC = "meat-quality/data"
MQTT_STATUS_TOPIC = "meat-quality/status"
MQTT_LWT_TOPIC = "meat-quality/lwt"
MQTT_USERNAME = "meat_monitor"
MQTT_PASSWORD = "meat_monitor"

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

# CO2 (MQ135) Thresholds in ppm
CO2_FRESH_THRESHOLD = 400.0     # Fresh: < 400 ppm
CO2_WARNING_THRESHOLD = 800.0   # Warning: 400-800 ppm
CO2_CRITICAL_THRESHOLD = 1200.0  # Critical: > 800 ppm

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
CHART_REFRESH_INTERVAL = 1  # Dashboard refresh interval in seconds (reduced from 2 for faster updates)
AUTO_REFRESH_ENABLED = True  # Enable automatic dashboard refresh for real-time data updates

# Visualization Settings
HISTORY_DISPLAY_COUNT = 50  # Number of readings to display in charts (reduced from 100 for faster queries)
HEATMAP_MIN_READINGS = 10    # Minimum readings needed for correlation heatmap

# ============================================================================
# Quality Level Mapping (ESP32 5-level -> Pi 4-level)
# ============================================================================

# Mapping from ESP32 quality levels to Pi dashboard status
QUALITY_LEVEL_MAP = {
    "EXCELLENT": "SAFE",
    "GOOD": "SAFE",
    "FAIR": "WARNING",
    "POOR": "WARNING",
    "SPOILED": "SPOILED"
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
MOCK_CO2_DEFAULT = 450.0  # Default CO2 for mock data (ppm)

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
