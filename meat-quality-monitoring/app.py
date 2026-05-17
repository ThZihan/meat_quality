"""
Multi-Modal Meat Quality Monitoring System Dashboard
Streamlit application combining Computer Vision (Custom CNN) and Gas Sensors
Supports both API (real sensor data) and Mock (simulation) modes
"""

from typing import Optional
from pathlib import Path
import sqlite3
import subprocess
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
from PIL import Image
import io
import time
import logging
from datetime import datetime

# Import project modules
import config
from api_client import get_api_client, load_bookmark, poll_current, catch_up
from mqtt_client_simple import map_quality_level, determine_gas_status
from db_manager import get_db_manager
from mock_data import get_time_elapsed, get_fusion_decision, get_readings
from camera import (
    get_camera_image_bytes,
    list_available_cameras,
    check_module3_available,
)
from camera_config import (
    CameraCaptureConfig,
    AutofocusMode,
    AutofocusRange,
    AutofocusSpeed
)
from image_capture import ImageCapture


logger = logging.getLogger(__name__)

CAPTURE_SERVICE_NAME = "pi-image-capture.service"
SYSTEMCTL_BIN = "/usr/bin/systemctl"
PYTHON_BIN = "/usr/bin/python3"
SUDO_BIN = "/usr/bin/sudo"
PENDING_SYNC_DIR = Path("/home/pi/pending_sync")
SYNC_LEDGER_PATH = Path("/home/pi/sync_state.db")
SYNC_SCRIPT_PATH = Path("/home/pi/meat-quality-monitoring/sync.py")



# Page configuration
st.set_page_config(
    page_title="Multi-Modal Meat Quality Monitoring",
    page_icon="🥩",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .metric-card {
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .status-safe {
        color: #00AA00;
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        padding: 1.5rem;
        background-color: #E8F5E9;
        border-radius: 15px;
        border: 3px solid #00AA00;
    }
    .status-warning {
        color: #FF9800;
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        padding: 1.5rem;
        background-color: #FFF3E0;
        border-radius: 15px;
        border: 3px solid #FF9800;
    }
    .status-spoiled {
        color: #FF0000;
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        padding: 1.5rem;
        background-color: #FFEBEE;
        border-radius: 15px;
        border: 3px solid #FF0000;
    }
    .status-critical {
        color: #8B0000;
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        padding: 1.5rem;
        background-color: #4A0404;
        color: #FFFFFF;
        border-radius: 15px;
        border: 3px solid #8B0000;
    }
    .visual-fresh {
        color: #00AA00;
        font-weight: bold;
    }
    .visual-rotten {
        color: #FF0000;
        font-weight: bold;
    }
    .fusion-card {
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Wider and more visible scrollbar */
    ::-webkit-scrollbar {
        width: 16px;
        height: 16px;
    }
    ::-webkit-scrollbar-track {
        background: #2d2d2d;
        border-radius: 8px;
    }
    ::-webkit-scrollbar-thumb {
        background: #6c757d;
        border-radius: 8px;
        border: 2px solid #2d2d2d;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #adb5bd;
    }
    ::-webkit-scrollbar-corner {
        background: #2d2d2d;
    }
    
    /* Firefox scrollbar */
    * {
        scrollbar-width: auto;
        scrollbar-color: #6c757d #2d2d2d;
    }
    
    /* Responsive tablet layout for 800x480 displays */
    @media screen and (max-width: 820px), screen and (max-height: 520px) {
        .stApp {
            padding-top: 1.75rem;
        }

        .block-container {
            padding-top: 0.65rem;
            padding-bottom: 0.75rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        section[data-testid="stSidebar"] {
            min-width: 210px !important;
            max-width: 210px !important;
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 0.75rem;
            padding-left: 0.65rem;
            padding-right: 0.65rem;
        }

        h1 {
            font-size: 1.45rem !important;
            line-height: 1.15 !important;
            margin-bottom: 0.25rem !important;
        }

        h2 {
            font-size: 1.05rem !important;
            line-height: 1.15 !important;
            margin-top: 0.3rem !important;
            margin-bottom: 0.25rem !important;
        }

        h3 {
            font-size: 0.95rem !important;
            line-height: 1.1 !important;
            margin-top: 0.2rem !important;
            margin-bottom: 0.2rem !important;
        }

        p,
        label,
        .stMarkdown,
        .stCaption {
            font-size: 0.9rem !important;
            line-height: 1.2 !important;
        }

        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.5rem !important;
        }

        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        div[data-testid="stMetric"] {
            padding: 0.25rem 0 !important;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.1rem !important;
            line-height: 1.1 !important;
        }

        .status-safe,
        .status-warning,
        .status-spoiled,
        .status-critical {
            font-size: 1.35rem;
            padding: 0.8rem;
            border-width: 2px;
            line-height: 1.15;
        }

        .metric-card,
        .fusion-card {
            padding: 0.75rem;
        }

        div[data-testid="stFileUploaderDropzone"] {
            padding: 0.6rem !important;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            width: 100%;
            min-height: 2.2rem;
            padding: 0.35rem 0.6rem;
            font-size: 0.88rem;
        }

        div[data-testid="stImage"] img {
            max-height: 220px !important;
            object-fit: contain;
        }

        div[data-testid="stPlotlyChart"] .js-plotly-plot,
        div[data-testid="stPlotlyChart"] .plot-container,
        div[data-testid="stPlotlyChart"] .svg-container {
            height: 220px !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# Initialize session state
if 'data_mode' not in st.session_state:
    st.session_state.data_mode = 'api'  # 'api' or 'mock'

if 'simulation_running' not in st.session_state:
    st.session_state.simulation_running = False
    
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=[
        'timestamp', 'h2s_ppm', 'nh3_ppm', 'voc_ppm', 'temp_c', 'humidity', 'quality_level'
    ])
    
if 'last_update' not in st.session_state:
    st.session_state.last_update = 0

if 'uploaded_image' not in st.session_state:
    st.session_state.uploaded_image = None

if 'uploaded_image_bytes' not in st.session_state:
    st.session_state.uploaded_image_bytes = None

if 'visual_prediction' not in st.session_state:
    st.session_state.visual_prediction = None

if 'capture_service_feedback' not in st.session_state:
    st.session_state.capture_service_feedback = None

if 'capture_service_feedback_level' not in st.session_state:
    st.session_state.capture_service_feedback_level = 'info'


if 'api_connected' not in st.session_state:
    st.session_state.api_connected = False

if 'last_db_check' not in st.session_state:
    st.session_state.last_db_check = 0

if 'last_api_poll' not in st.session_state:
    st.session_state.last_api_poll = 0

if 'api_catchup_done' not in st.session_state:
    st.session_state.api_catchup_done = False


# Sidebar controls
with st.sidebar:
    st.header("⚙️ Controls")
    
    # Data mode selection
    st.subheader("📡 Data Source")
    data_mode = st.radio(
        "Select Data Mode",
        options=['api', 'mock'],
        format_func=lambda x: "API (Real Sensors)" if x == 'api' else "Mock (Simulation)",
        index=0 if st.session_state.data_mode == 'api' else 1
    )
    
    if data_mode != st.session_state.data_mode:
        st.session_state.data_mode = data_mode
        st.session_state.history = pd.DataFrame(columns=[
            'timestamp', 'h2s_ppm', 'nh3_ppm', 'voc_ppm', 'temp_c', 'humidity', 'quality_level'
        ])
        st.rerun()
    
    # API Connection Status & Background Service Info
    if st.session_state.data_mode == 'api':
        api_client = get_api_client()
        
        # Show connection status based on bookmark AND database readings
        bookmark = api_client.get_bookmark_info()
        db = get_db_manager()
        reading_count = db.get_reading_count()
        
        if bookmark.get("last_id", 0) > 0:
            st.success("✅ Sensor Data Active")
            st.caption(f"Last reading ID: {bookmark['last_id']}")
        elif reading_count > 0:
            st.success("✅ Sensor Data Active")
            st.caption(f"Database has {reading_count} readings. Bookmark will update on next poll.")
        else:
            st.warning("⚠️ No data yet")
            st.caption("Start the background client to fetch data.")
        
        # Test connection button
        if st.button("🔄 Test API Connection"):
            raw = api_client.fetch_current()
            if raw is not None:
                st.session_state.api_connected = True
                st.success("Connection successful!")
                # Unwrap server response envelope
                readings = raw.get("readings", [])
                if readings:
                    r = readings[0]
                    st.json({
                        "id": r.get("id"),
                        "temperature": r.get("temperature"),
                        "humidity": r.get("humidity"),
                        "mq135_co2": r.get("mq135_co2"),
                        "mq136_h2s": r.get("mq136_h2s"),
                        "mq137_nh3": r.get("mq137_nh3"),
                        "quality_level": r.get("quality_level"),
                    })
                else:
                    st.warning("API reachable but no readings found on server.")
            else:
                st.error(f"Connection failed: {api_client.last_error}")
    
    st.divider()
    
    # Start/Stop simulation (only for mock mode)
    if st.session_state.data_mode == 'mock':
        if st.button("▶️ Start Simulation" if not st.session_state.simulation_running else "⏸️ Stop Simulation"):
            st.session_state.simulation_running = not st.session_state.simulation_running
            if st.session_state.simulation_running:
                st.success("Simulation started!")
            else:
                st.warning("Simulation paused.")
        
        # Room temperature slider
        room_temp = st.slider(
            "🌡️ Room Temperature (°C)",
            min_value=0,
            max_value=50,
            value=25,
            step=1,
            help="Adjust to test temperature correlation with gas levels"
        )
        
        # Humidity slider
        humidity = st.slider(
            "💧 Humidity (%)",
            min_value=0,
            max_value=100,
            value=60,
            step=5
        )
    else:
        room_temp = 25  # Default for API mode
        humidity = 60
    
    st.divider()
    
    # Reset button (only for mock mode)
    if st.session_state.data_mode == 'mock':
        if st.button("🔄 Reset Data"):
            reset_simulation()
            st.session_state.history = pd.DataFrame(columns=[
                'timestamp', 'h2s_ppm', 'nh3_ppm', 'voc_ppm', 'temp_c', 'humidity', 'quality_level'
            ])
            st.session_state.visual_prediction = None
            st.session_state.uploaded_image = None
            st.session_state.uploaded_image_bytes = None
            st.success("Data reset!")
    
    st.divider()
    
    # Display elapsed time (only for mock mode)
    if st.session_state.data_mode == 'mock':
        elapsed_time = get_time_elapsed()
        st.metric("⏱️ Time Elapsed", f"{elapsed_time:.1f} s")
    else:
        # Show database stats for API mode
        db = get_db_manager()
        reading_count = db.get_reading_count()
        st.metric("📊 Total Readings", f"{reading_count}")
        
        # Download CSV button
        if reading_count > 0:
            def get_all_readings_csv():
                """Get all readings from database as CSV string."""
                import sqlite3
                import csv
                import io
                
                with sqlite3.connect(config.DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, timestamp, device_id, temperature, humidity,
                               mq135_co2, mq136_h2s, mq137_nh3, quality_level
                        FROM sensor_readings
                        ORDER BY timestamp ASC
                    ''')
                    
                    rows = cursor.fetchall()
                    
                    # Create CSV in memory
                    output = io.StringIO()
                    writer = csv.writer(output)
                    
                    # Write header
                    writer.writerow(['ID', 'Timestamp', 'Device ID', 'Temperature (°C)',
                                   'Humidity (%)', 'VOC (ppm)', 'H2S (ppm)', 'NH3 (ppm)',
                                   'Quality Level'])
                    
                    # Write data rows
                    for row in rows:
                        writer.writerow([
                            row['id'],
                            row['timestamp'],
                            row['device_id'],
                            row['temperature'],
                            row['humidity'],
                            row['mq135_co2'],
                            row['mq136_h2s'],
                            row['mq137_nh3'],
                            row['quality_level']
                        ])
                    
                    return output.getvalue()
            
            csv_data = get_all_readings_csv()
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"meat_monitor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width='stretch'
            )
            
            # Delete all data button (only for API mode)
            if st.session_state.data_mode == 'api':
                if st.button("🗑️ Delete All Data", type="secondary"):
                    db = get_db_manager()
                    result = db.delete_all_data()
                    
                    if 'error' in result:
                        st.error(f"Error deleting data: {result['error']}")
                    else:
                        st.success(f"✅ Deleted {result['sensor_readings']} sensor readings, "
                                  f"{result['visual_predictions']} visual predictions, "
                                  f"{result['fusion_decisions']} fusion decisions")
                        # Clear session state history
                        st.session_state.history = pd.DataFrame(columns=[
                            'timestamp', 'h2s_ppm', 'nh3_ppm', 'voc_ppm', 'temp_c', 'humidity', 'quality_level'
                        ])
                        st.rerun()
    
    # Thresholds info
    st.subheader("📊 Gas Thresholds")
    st.info(f"""
    **H2S (MQ136):**
    - Fresh: < {config.H2S_FRESH_THRESHOLD} ppm
    - Warning: {config.H2S_FRESH_THRESHOLD}-{config.H2S_WARNING_THRESHOLD} ppm
    - Critical: > {config.H2S_WARNING_THRESHOLD} ppm
    
    **NH3 (MQ137):**
    - Fresh: < {config.NH3_FRESH_THRESHOLD} ppm
    - Warning: {config.NH3_FRESH_THRESHOLD}-{config.NH3_WARNING_THRESHOLD} ppm
    - Critical: > {config.NH3_WARNING_THRESHOLD} ppm
    
    **VOC (MQ135):**
    - Fresh: < {config.VOC_FRESH_THRESHOLD} ppm
    - Warning: {config.VOC_FRESH_THRESHOLD}-{config.VOC_WARNING_THRESHOLD} ppm
    - Critical: > {config.VOC_WARNING_THRESHOLD} ppm
    """)


# Main dashboard
st.title("🥩 Multi-Modal Meat Quality Monitoring System")
st.markdown("Real-time monitoring combining **Computer Vision (Custom CNN)** and **Gas Sensors**")


# Function to get color based on value and thresholds
def get_color(value, warning_threshold, critical_threshold):
    if value < warning_threshold:
        return "#00AA00"  # Green
    elif value < critical_threshold:
        return "#FF9800"  # Orange
    else:
        return "#FF0000"  # Red


def format_bytes(size_bytes: int) -> str:
    """Format bytes into a human-readable value."""
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size_bytes} B"


def run_privileged_command(command: list[str]) -> tuple[bool, str]:
    """Run a command, preferring sudo for system service control."""
    full_command = command
    if Path(SUDO_BIN).exists():
        full_command = [SUDO_BIN, *command]

    try:
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception as error:
        return False, str(error)

    output = (result.stdout or result.stderr or "Command completed.").strip()
    return result.returncode == 0, output


def get_capture_service_status() -> dict:
    """Return the current systemd state for the continuous capture service."""
    active_ok, active_output = run_privileged_command([SYSTEMCTL_BIN, "is-active", CAPTURE_SERVICE_NAME])
    enabled_ok, enabled_output = run_privileged_command([SYSTEMCTL_BIN, "is-enabled", CAPTURE_SERVICE_NAME])

    active_state = active_output.strip().splitlines()[-1] if active_output else "unknown"
    enabled_state = enabled_output.strip().splitlines()[-1] if enabled_output else "unknown"

    return {
        'is_active': active_ok and active_state == 'active',
        'active_state': active_state,
        'is_enabled': enabled_ok and enabled_state == 'enabled',
        'enabled_state': enabled_state,
    }


def control_capture_service(action: str) -> tuple[bool, str]:
    """Start or stop the background capture service from the dashboard."""
    if action == 'start':
        return run_privileged_command([SYSTEMCTL_BIN, 'enable', '--now', CAPTURE_SERVICE_NAME])
    if action == 'stop':
        return run_privileged_command([SYSTEMCTL_BIN, 'stop', CAPTURE_SERVICE_NAME])
    return False, f"Unsupported action: {action}"


def run_sync_now() -> tuple[bool, str]:
    """Trigger a foreground sync run from the dashboard."""
    return run_privileged_command([PYTHON_BIN, str(SYNC_SCRIPT_PATH)])


def get_sync_state_summary() -> dict:
    """Collect pending directory and SQLite ledger status for the UI."""
    pending_files = []
    if PENDING_SYNC_DIR.exists():
        pending_files = sorted(
            [file_path for file_path in PENDING_SYNC_DIR.iterdir() if file_path.is_file()],
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )

    pending_bytes = sum(file_path.stat().st_size for file_path in pending_files)
    status_counts = {}
    latest_row = None

    if SYNC_LEDGER_PATH.exists():
        try:
            with sqlite3.connect(SYNC_LEDGER_PATH) as connection:
                cursor = connection.cursor()
                for status, count in cursor.execute(
                    "SELECT status, COUNT(*) FROM images GROUP BY status ORDER BY status"
                ).fetchall():
                    status_counts[status] = count

                latest_row = cursor.execute(
                    """
                    SELECT filename, capture_time, upload_time, status
                    FROM images
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
        except sqlite3.Error:
            latest_row = None

    return {
        'pending_files': len(pending_files),
        'pending_bytes': pending_bytes,
        'latest_pending_path': pending_files[0] if pending_files else None,
        'status_counts': status_counts,
        'latest_row': latest_row,
    }


def load_latest_pending_capture() -> tuple[bool, str]:
    """Load the most recent pending image into the dashboard preview pane."""
    summary = get_sync_state_summary()
    latest_pending_path = summary['latest_pending_path']
    if latest_pending_path is None:
        return False, f"No image is waiting in {PENDING_SYNC_DIR}."

    try:
        st.session_state.uploaded_image_bytes = latest_pending_path.read_bytes()
        st.session_state.uploaded_image = None
        st.session_state.visual_prediction = None
        return True, f"Loaded latest pending capture: {latest_pending_path.name}"
    except OSError as error:
        return False, f"Failed to load latest pending capture: {error}"


def capture_dashboard_image() -> tuple[bool, str]:
    """Capture a fresh dashboard image through the LED-assisted high-res path."""
    try:
        capturer = ImageCapture()
        result = capturer.capture_with_led_assistance(
            timeout=20,
            custom_prefix="dashboard_capture",
        )

        if not result['success']:
            return False, result.get('error') or result.get('message') or 'Capture failed.'

        st.session_state.uploaded_image_bytes = result['image_bytes']
        st.session_state.uploaded_image = None
        st.session_state.visual_prediction = None
        return True, f"Captured image: {result['filename']}"
    except Exception as error:
        return False, f"Capture failed: {error}"


# Update data (Mock or API)
if st.session_state.data_mode == 'mock' and st.session_state.simulation_running:
    current_time = time.time()
    
    # Update every 2 seconds
    if current_time - st.session_state.last_update >= config.CHART_REFRESH_INTERVAL:
        readings = get_readings(room_temp, humidity)
        
        # Add to history
        new_row = pd.DataFrame([{
            'timestamp': pd.Timestamp.now(),
            'h2s_ppm': readings['h2s_ppm'],
            'nh3_ppm': readings['ammonia_ppm'],  # Map ammonia to nh3
            'voc_ppm': readings['methane_ppm'],  # Map methane to voc for display
            'temp_c': readings['temp_c'],
            'humidity': readings['humidity'],
            'quality_level': 'UNKNOWN'
        }])
        
        st.session_state.history = pd.concat([st.session_state.history, new_row], ignore_index=True)
        
        # Keep only last 1000 readings
        if len(st.session_state.history) > config.MAX_HISTORY_READINGS:
            st.session_state.history = st.session_state.history.tail(config.MAX_HISTORY_READINGS).reset_index(drop=True)
        
        st.session_state.last_update = current_time
        st.rerun()

elif st.session_state.data_mode == 'api':
    # Poll remote API for new data and load from local database
    current_time = time.time()
    
    if current_time - st.session_state.last_db_check >= config.CHART_REFRESH_INTERVAL:
        # Poll the remote API and store new readings in local DB
        if current_time - st.session_state.last_api_poll >= config.SENSOR_API_POLL_INTERVAL:
            try:
                bookmark = load_bookmark()
                
                # Run catch-up on first load to recover missed readings
                if not st.session_state.api_catchup_done:
                    logger.info("Running API catch-up for missed readings...")
                    bookmark = catch_up(bookmark)
                    st.session_state.api_catchup_done = True
                
                new_bookmark = poll_current(bookmark)
                if new_bookmark != bookmark:
                    logger.debug("New reading stored from API poll")
            except Exception as e:
                logger.warning(f"API poll failed: {e}")
            
            st.session_state.last_api_poll = current_time
        
        # Load data from local database
        db = get_db_manager()
        recent_readings = db.get_recent_readings(limit=config.HISTORY_DISPLAY_COUNT)
        
        if recent_readings:
            # Convert database readings to DataFrame format
            df_data = []
            for reading in reversed(recent_readings):
                df_data.append({
                    'timestamp': pd.to_datetime(reading['timestamp']),
                    'h2s_ppm': reading['mq136_h2s'],
                    'nh3_ppm': reading['mq137_nh3'],
                    'voc_ppm': reading['mq135_co2'],
                    'temp_c': reading['temperature'],
                    'humidity': reading['humidity'],
                    'quality_level': reading['quality_level']
                })
            
            st.session_state.history = pd.DataFrame(df_data)
        
        st.session_state.last_db_check = current_time


# Get current readings
if len(st.session_state.history) > 0:
    current = st.session_state.history.iloc[-1]
else:
    current = {
        'h2s_ppm': 0.0,
        'nh3_ppm': 0.0,
        'voc_ppm': 0.0,
        'temp_c': 0.0,
        'humidity': 0.0,
        'quality_level': 'UNKNOWN'
    }


capture_service_status = None
sync_state_summary = None
if st.session_state.data_mode == 'api':
    capture_service_status = get_capture_service_status()
    sync_state_summary = get_sync_state_summary()


# Main Content Area - Split into two columns
left_col, right_col = st.columns([1, 1])

# ==================== LEFT COLUMN: VISUAL INTELLIGENCE ====================
with left_col:
    st.subheader("👁️ Visual Intelligence (Custom CNN)")
    
    # Image upload area
    uploaded_file = st.file_uploader(
        "Upload Meat Image",
        type=['jpg', 'jpeg', 'png'],
        help="Upload an image of the meat for visual analysis",
        key="image_uploader"
    )
    
    # Store uploaded image in session state when a new file is uploaded
    if uploaded_file is not None:
        st.session_state.uploaded_image = uploaded_file
        st.session_state.uploaded_image_bytes = uploaded_file.read()
        # Reset file pointer
        uploaded_file.seek(0)
    
    if st.session_state.data_mode == 'mock':
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("📷 Load Dummy Capture"):
                try:
                    with open("images/dummyImg.png", "rb") as f:
                        st.session_state.uploaded_image_bytes = f.read()
                    st.session_state.uploaded_image = None
                    st.success("Dummy image loaded for simulation!")
                except FileNotFoundError:
                    st.error("Dummy image not found. Please ensure images/dummyImg.png exists.")

        with col_btn2:
            if st.button("🔄 Clear Image"):
                st.session_state.uploaded_image = None
                st.session_state.uploaded_image_bytes = None
                st.session_state.visual_prediction = None
    else:
        st.markdown("### 🎛️ Edge Capture Controls")

        if st.session_state.capture_service_feedback:
            feedback_writer = getattr(st, st.session_state.capture_service_feedback_level, st.info)
            feedback_writer(st.session_state.capture_service_feedback)

        if capture_service_status and capture_service_status['is_active']:
            st.success("Continuous capture service is running. Images are being captured every 30 seconds.")
        else:
            active_state = capture_service_status['active_state'] if capture_service_status else 'unknown'
            st.warning(f"Continuous capture service is not running right now. Current state: {active_state}")

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        with metric_col1:
            st.metric("Service", "Running" if capture_service_status and capture_service_status['is_active'] else "Stopped")
        with metric_col2:
            st.metric("Pending Files", sync_state_summary['pending_files'] if sync_state_summary else 0)
        with metric_col3:
            st.metric("Pending Pool", format_bytes(sync_state_summary['pending_bytes']) if sync_state_summary else "0 B")
        with metric_col4:
            uploaded_count = sync_state_summary['status_counts'].get('uploaded', 0) if sync_state_summary else 0
            st.metric("Uploaded", uploaded_count)

        latest_row = sync_state_summary['latest_row'] if sync_state_summary else None
        if latest_row:
            st.caption(
                f"Latest ledger row: {latest_row[0]} | captured at {latest_row[1]} | "
                f"status: {latest_row[3]}"
            )

        st.info(
            f"Images are stored first in {PENDING_SYNC_DIR}. They stay there until "
            f"[sync.py](meat-quality-monitoring/sync.py:1) uploads them successfully and removes the local file."
        )

        control_col1, control_col2, control_col3 = st.columns(3)
        with control_col1:
            if st.button("▶️ Start Capturing", disabled=capture_service_status and capture_service_status['is_active']):
                success, message = control_capture_service('start')
                if success:
                    st.session_state.capture_service_feedback = "Continuous edge capture started. Uploading will resume automatically after 10 MB is pooled."
                    st.session_state.capture_service_feedback_level = 'success'
                else:
                    st.session_state.capture_service_feedback = f"Failed to start capture service: {message}"
                    st.session_state.capture_service_feedback_level = 'error'
                st.rerun()

        with control_col2:
            if st.button("⏹️ Stop Capturing", disabled=not (capture_service_status and capture_service_status['is_active'])):
                success, message = control_capture_service('stop')
                if success:
                    st.session_state.capture_service_feedback = "Continuous edge capture stopped. Pending files remain on disk until capture is started again or sync is run manually."
                    st.session_state.capture_service_feedback_level = 'warning'
                else:
                    st.session_state.capture_service_feedback = f"Failed to stop capture service: {message}"
                    st.session_state.capture_service_feedback_level = 'error'
                st.rerun()

        with control_col3:
            if st.button("🖼️ Load Latest Capture"):
                success, message = load_latest_pending_capture()
                if success:
                    st.session_state.capture_service_feedback = message
                    st.session_state.capture_service_feedback_level = 'success'
                else:
                    st.session_state.capture_service_feedback = message
                    st.session_state.capture_service_feedback_level = 'warning'
                st.rerun()

        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("📸 Capture Now"):
                with st.spinner("Capturing image with automatic LED illumination..."):
                    success, message = capture_dashboard_image()

                if success:
                    st.session_state.capture_service_feedback = f"Manual capture completed: {message}"
                    st.session_state.capture_service_feedback_level = 'success'
                else:
                    st.session_state.capture_service_feedback = f"Manual capture failed: {message}"
                    st.session_state.capture_service_feedback_level = 'error'
                st.rerun()

        with action_col2:
            if st.button("☁️ Run Sync Now"):
                success, message = run_sync_now()
                if success:
                    st.session_state.capture_service_feedback = f"Manual sync completed: {message}"
                    st.session_state.capture_service_feedback_level = 'success'
                else:
                    st.session_state.capture_service_feedback = f"Manual sync stopped or failed: {message}"
                    st.session_state.capture_service_feedback_level = 'warning'
                st.rerun()

        if st.button("🔄 Clear Image"):
            st.session_state.uploaded_image = None
            st.session_state.uploaded_image_bytes = None
            st.session_state.visual_prediction = None
    
    # Display image
    st.markdown("### Image Display")
    
    if st.session_state.uploaded_image_bytes is not None:
        # Display image from session state (persists across reruns)
        st.image(st.session_state.uploaded_image_bytes, width='stretch', caption="Captured from Camera")
    elif st.session_state.data_mode == 'api' and sync_state_summary and sync_state_summary['latest_pending_path']:
        latest_pending = sync_state_summary['latest_pending_path']
        # Guard against 0-byte or corrupt image files that PIL cannot identify
        try:
            file_size = latest_pending.stat().st_size
            if file_size > 0:
                st.image(
                    str(latest_pending),
                    width='stretch',
                    caption=f"Latest pending capture: {latest_pending.name}"
                )
            else:
                st.warning(f"Latest pending capture is empty (0 bytes): {latest_pending.name}")
        except Exception as img_err:
            st.warning(f"Cannot display latest pending capture: {img_err}")
    else:
        if st.session_state.data_mode == 'api':
            st.info(
                "Use Start Capturing to run the background service, or Load Latest Capture to preview the newest image waiting in /home/pi/pending_sync."
            )
        else:
            st.info("Upload an image or load a dummy capture to start visual analysis.")
    
    # CNN Prediction
    st.markdown("### CNN Prediction Results")
    
    if st.session_state.uploaded_image_bytes is not None:
        if st.session_state.simulation_running or st.button("🔍 Run CNN Prediction"):
            if st.session_state.data_mode == 'mock':
                # Use dummy prediction for mock mode
                prediction = {
                    'species': 'Beef',
                    'visual_status': 'Fresh',
                    'confidence': '92.5%'
                }
                st.session_state.visual_prediction = prediction
                st.info("Showing dummy prediction for simulation mode.")
            else:
                # Use actual CNN prediction for API mode
                prediction = predict_image()
                st.session_state.visual_prediction = prediction
    
    if st.session_state.visual_prediction:
        pred = st.session_state.visual_prediction
        
        # Species
        st.metric("🐄 Species", pred['species'])
        
        # Visual Status with color
        status_class = "visual-fresh" if pred['visual_status'] == "Fresh" else "visual-rotten"
        st.markdown(f"**Visual Status:** <span class='{status_class}'>{pred['visual_status']}</span>", unsafe_allow_html=True)
        
        # Confidence Score
        st.metric("🎯 Confidence", pred['confidence'])
        
        # Warning if rotten
        if pred['visual_status'] == "Rotten":
            st.error("⚠️ Visual spoilage detected! Meat appears rotten.")
    else:
        st.info("Run CNN prediction to see results.")


# ==================== RIGHT COLUMN: OLFACTORY INTELLIGENCE ====================
with right_col:
    st.subheader("👃 Olfactory Intelligence (Gas Sensors)")
    
    # Gas Sensor Metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        h2s_color = get_color(current['h2s_ppm'], 10, 50)
        st.metric(
            label="H2S (MQ136)",
            value=f"{current['h2s_ppm']:.2f} ppm",
            delta_color="normal"
        )
        st.markdown(f"<div style='height: 5px; background-color: {h2s_color}; border-radius: 3px;'></div>", 
                    unsafe_allow_html=True)
    
    with col2:
        nh3_color = get_color(current['nh3_ppm'], config.NH3_FRESH_THRESHOLD, config.NH3_WARNING_THRESHOLD)
        st.metric(
            label="NH3 (MQ137)",
            value=f"{current['nh3_ppm']:.2f} ppm",
            delta_color="normal"
        )
        st.markdown(f"<div style='height: 5px; background-color: {nh3_color}; border-radius: 3px;'></div>",
                    unsafe_allow_html=True)
    
    with col3:
        voc_color = get_color(current['voc_ppm'], config.VOC_FRESH_THRESHOLD, config.VOC_WARNING_THRESHOLD)
        st.metric(
            label="VOC (MQ135)",
            value=f"{current['voc_ppm']:.2f} ppm",
            delta_color="normal"
        )
        st.markdown(f"<div style='height: 5px; background-color: {voc_color}; border-radius: 3px;'></div>",
                    unsafe_allow_html=True)
    
    # Environmental Metrics
    col4, col5 = st.columns(2)
    
    with col4:
        # Temperature color based on meat storage optimal range
        if config.TEMP_OPTIMAL_MIN <= current['temp_c'] <= config.TEMP_OPTIMAL_MAX:
            temp_color = "#00AA00"
        elif current['temp_c'] < config.TEMP_WARNING_HIGH:
            temp_color = "#FF9800"
        else:
            temp_color = "#FF0000"
        
        st.metric(
            label="Temperature",
            value=f"{current['temp_c']:.1f} °C",
            delta_color="normal"
        )
        st.markdown(f"<div style='height: 5px; background-color: {temp_color}; border-radius: 3px;'></div>",
                    unsafe_allow_html=True)
    
    with col5:
        # Humidity color based on optimal range
        if config.HUMIDITY_OPTIMAL_MIN <= current['humidity'] <= config.HUMIDITY_OPTIMAL_MAX:
            humidity_color = "#00AA00"
        elif config.HUMIDITY_WARNING_LOW <= current['humidity'] <= config.HUMIDITY_WARNING_HIGH:
            humidity_color = "#FF9800"
        else:
            humidity_color = "#FF0000"
        
        st.metric(
            label="Humidity",
            value=f"{current['humidity']:.1f} %",
            delta_color="normal"
        )
        st.markdown(f"<div style='height: 5px; background-color: {humidity_color}; border-radius: 3px;'></div>",
                    unsafe_allow_html=True)
    
    # Trends Chart
    st.markdown("### 📈 Gas Level Trends (Last 100 Readings)")
    if len(st.session_state.history) > 1:
        recent_history = st.session_state.history.tail(100)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=recent_history.index,
            y=recent_history['h2s_ppm'],
            mode='lines+markers',
            name='H2S (MQ136)',
            line=dict(color='#FF6B6B', width=2),
            marker=dict(size=4)
        ))
        
        fig.add_trace(go.Scatter(
            x=recent_history.index,
            y=recent_history['nh3_ppm'],
            mode='lines+markers',
            name='NH3 (MQ137)',
            line=dict(color='#4ECDC4', width=2),
            marker=dict(size=4)
        ))
        
        fig.add_hline(y=config.H2S_FRESH_THRESHOLD, line_dash="dash", line_color="orange",
                      annotation_text="H2S Warning", annotation_position="right")
        fig.add_hline(y=config.H2S_WARNING_THRESHOLD, line_dash="dash", line_color="red",
                      annotation_text="H2S Critical", annotation_position="right")
        fig.add_hline(y=config.NH3_FRESH_THRESHOLD, line_dash="dot", line_color="blue",
                      annotation_text="NH3 Warning", annotation_position="left")
        fig.add_hline(y=config.NH3_WARNING_THRESHOLD, line_dash="dot", line_color="darkred",
                      annotation_text="NH3 Critical", annotation_position="left")
        
        fig.update_layout(
            title="H2S and NH3 Levels Over Time",
            xaxis_title="Reading Number",
            yaxis_title="Concentration (ppm)",
            hovermode='x unified',
            template='plotly_white',
            height=300,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Start the simulation to see trend data.")


# ==================== FUSION ANALYSIS SECTION ====================
st.divider()
st.subheader("🔗 Fusion Analysis (Multi-Modal Decision)")

# Get fusion decision
visual_status = st.session_state.visual_prediction['visual_status'] if st.session_state.visual_prediction else "Unknown"

# Map gas readings for fusion decision
gas_readings = {
    'h2s_ppm': current['h2s_ppm'],
    'methane_ppm': current['nh3_ppm'],  # Map NH3 to methane for fusion logic
    'ammonia_ppm': current['voc_ppm']  # Map VOC to ammonia for fusion logic
}

# Get fusion decision from mock_data module
fusion_status, fusion_color = get_fusion_decision(visual_status, gas_readings)

# If using API data, also consider the ESP quality level
if st.session_state.data_mode == 'api' and current.get('quality_level') != 'UNKNOWN':
    esp_quality = map_quality_level(current['quality_level'])
    # Use the more conservative status
    if esp_quality == "CRITICAL" or fusion_status == "CRITICAL":
        fusion_status = "CRITICAL"
        fusion_color = config.QUALITY_COLORS["CRITICAL"]
    elif esp_quality == "SPOILED" or fusion_status == "SPOILED":
        fusion_status = "SPOILED"
        fusion_color = config.QUALITY_COLORS["SPOILED"]
    elif esp_quality == "WARNING" or fusion_status == "WARNING":
        fusion_status = "WARNING"
        fusion_color = config.QUALITY_COLORS["WARNING"]

# Display fusion results in columns
fusion_col1, fusion_col2, fusion_col3 = st.columns([1, 2, 1])

with fusion_col1:
    st.markdown("### Visual Result")
    if st.session_state.visual_prediction:
        pred = st.session_state.visual_prediction
        status_color = "#00AA00" if pred['visual_status'] == "Fresh" else "#FF0000"
        st.markdown(f"<div style='color: {status_color}; font-size: 1.5rem; font-weight: bold;'>{pred['visual_status']}</div>", unsafe_allow_html=True)
        st.markdown(f"**Species:** {pred['species']}")
        st.markdown(f"**Confidence:** {pred['confidence']}")
    else:
        st.info("No visual data")

with fusion_col2:
    st.markdown("### Final Decision")
    status_class_map = {
        "SAFE": "status-safe",
        "WARNING": "status-warning",
        "SPOILED": "status-spoiled",
        "CRITICAL": "status-critical"
    }
    status_class = status_class_map.get(fusion_status, "status-warning")
    st.markdown(f"<div class='{status_class}'>Status: {fusion_status}</div>", unsafe_allow_html=True)
    
    # Decision explanation
    st.markdown("### Decision Logic")
    if fusion_status == "SAFE":
        st.success("✅ Both visual and gas indicators show meat is fresh and safe for consumption.")
    elif fusion_status == "WARNING":
        st.warning("⚠️ Visual analysis shows fresh, but gas levels are elevated. Check sensors or investigate potential early spoilage.")
    elif fusion_status == "SPOILED":
        st.error("🚫 Visual analysis indicates spoilage. Meat should not be consumed.")
    elif fusion_status == "CRITICAL":
        st.error("🔥 CRITICAL: Either visual spoilage detected OR gas levels at critical levels. Immediate action required!")

with fusion_col3:
    st.markdown("### Gas Result")
    
    # Determine gas status using the new function
    gas_status = determine_gas_status(current['h2s_ppm'], current['nh3_ppm'], current['voc_ppm'])
    gas_color = config.QUALITY_COLORS.get(gas_status, "#FF9800")
    
    st.markdown(f"<div style='color: {gas_color}; font-size: 1.5rem; font-weight: bold;'>{gas_status}</div>", unsafe_allow_html=True)
    st.markdown(f"**H2S:** {current['h2s_ppm']:.2f} ppm")
    st.markdown(f"**NH3:** {current['nh3_ppm']:.2f} ppm")
    st.markdown(f"**VOC:** {current['voc_ppm']:.2f} ppm")


# ==================== CORRELATION HEATMAP ====================
st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🔥 Correlation Heatmap")
    if len(st.session_state.history) > 10:
        # Calculate correlation matrix
        corr_data = st.session_state.history[['h2s_ppm', 'nh3_ppm', 'voc_ppm', 'temp_c', 'humidity']].corr()
        
        # Create heatmap using seaborn
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(
            corr_data,
            annot=True,
            cmap='RdYlGn',
            center=0,
            fmt='.2f',
            linewidths=1,
            cbar_kws={"shrink": 0.8},
            ax=ax
        )
        ax.set_title("Correlation Between Temperature and Gas Levels")
        plt.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close()
    else:
        st.info("Need at least 10 readings to calculate correlations.")

with col_right:
    st.subheader("📊 Gas Levels vs Thresholds")
    
    # Progress bars for each gas
    st.markdown("### H2S (MQ136)")
    h2s_percent = min(100, (current['h2s_ppm'] / 50) * 100)
    h2s_bar_color = "#00AA00" if current['h2s_ppm'] < 10 else "#FF9800" if current['h2s_ppm'] < 50 else "#FF0000"
    st.markdown(f"""
    <div style='background-color: #e0e0e0; border-radius: 10px; height: 25px; overflow: hidden;'>
        <div style='background-color: {h2s_bar_color}; width: {h2s_percent}%; height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;'>
            {current['h2s_ppm']:.2f} ppm / 50 ppm
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### NH3 (MQ137)")
    nh3_percent = min(100, (current['nh3_ppm'] / config.NH3_WARNING_THRESHOLD) * 100)
    nh3_bar_color = config.QUALITY_COLORS["SAFE"] if current['nh3_ppm'] < config.NH3_FRESH_THRESHOLD else config.QUALITY_COLORS["WARNING"] if current['nh3_ppm'] < config.NH3_WARNING_THRESHOLD else config.QUALITY_COLORS["SPOILED"]
    st.markdown(f"""
    <div style='background-color: #e0e0e0; border-radius: 10px; height: 25px; overflow: hidden;'>
        <div style='background-color: {nh3_bar_color}; width: {nh3_percent}%; height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;'>
            {current['nh3_ppm']:.2f} ppm / {config.NH3_WARNING_THRESHOLD} ppm
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### VOC (MQ135)")
    voc_percent = min(100, (current['voc_ppm'] / config.VOC_WARNING_THRESHOLD) * 100)
    voc_bar_color = config.QUALITY_COLORS["SAFE"] if current['voc_ppm'] < config.VOC_FRESH_THRESHOLD else config.QUALITY_COLORS["WARNING"] if current['voc_ppm'] < config.VOC_WARNING_THRESHOLD else config.QUALITY_COLORS["SPOILED"]
    st.markdown(f"""
    <div style='background-color: #e0e0e0; border-radius: 10px; height: 25px; overflow: hidden;'>
        <div style='background-color: {voc_bar_color}; width: {voc_percent}%; height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;'>
            {current['voc_ppm']:.2f} ppm / {config.VOC_WARNING_THRESHOLD} ppm
        </div>
    </div>
    """, unsafe_allow_html=True)


# Footer
st.divider()
st.markdown(f"""
<div style='text-align: center; color: #666;'>
    <p>🥩 Multi-Modal Meat Quality Monitoring System | Computer Vision + Gas Sensors</p>
    <p>Sensors: MQ136 (H2S), MQ137 (NH3), MQ135 (VOC), AHT10 (Temp/Humidity)</p>
    <p>Data Mode: <strong>{'API (Real Sensors)' if st.session_state.data_mode == 'api' else 'Mock (Simulation)'}</strong></p>
    <p style='margin-top: 20px;'>
        © 2025 Tahfizul Hasan Zihan. All Rights Reserved.<br/>
        <a href='https://github.com/ThZihan/meat_quality/tree/master' target='_blank' style='color: #666; text-decoration: none;'>
            🔗 GitHub: https://github.com/ThZihan/meat_quality/tree/master
        </a>
    </p>
</div>
""", unsafe_allow_html=True)


# Auto-refresh for mock mode
if st.session_state.data_mode == 'mock' and st.session_state.simulation_running:
    time.sleep(config.CHART_REFRESH_INTERVAL)
    st.rerun()
elif st.session_state.data_mode == 'api' and config.AUTO_REFRESH_ENABLED:
    time.sleep(config.CHART_REFRESH_INTERVAL)
    st.rerun()
