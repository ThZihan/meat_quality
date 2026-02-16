"""
Multi-Modal Meat Quality Monitoring System Dashboard
Streamlit application combining Computer Vision (Custom CNN) and Gas Sensors
Supports both MQTT (real sensor data) and Mock (simulation) modes
"""

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
from datetime import datetime

# Import project modules
import config
from mqtt_client_simple import get_simple_mqtt_client as get_mqtt_client, map_quality_level, determine_gas_status
from db_manager import get_db_manager
from mock_data import get_time_elapsed, get_fusion_decision, get_readings
from camera import get_camera_image_bytes, list_available_cameras, check_pi_camera_v2_available

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
</style>
""", unsafe_allow_html=True)


# Initialize session state
if 'data_mode' not in st.session_state:
    st.session_state.data_mode = 'mock'  # 'mqtt' or 'mock'

if 'simulation_running' not in st.session_state:
    st.session_state.simulation_running = False
    
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=[
        'timestamp', 'h2s_ppm', 'nh3_ppm', 'co2_ppm', 'temp_c', 'humidity', 'quality_level'
    ])
    
if 'last_update' not in st.session_state:
    st.session_state.last_update = 0

if 'uploaded_image' not in st.session_state:
    st.session_state.uploaded_image = None

if 'uploaded_image_bytes' not in st.session_state:
    st.session_state.uploaded_image_bytes = None

if 'visual_prediction' not in st.session_state:
    st.session_state.visual_prediction = None


if 'mqtt_connected' not in st.session_state:
    st.session_state.mqtt_connected = False

if 'mqtt_started' not in st.session_state:
    st.session_state.mqtt_started = False

# Initialize MQTT client in session state
if '_mqtt_client' not in st.session_state:
    st.session_state._mqtt_client = None

if 'last_db_check' not in st.session_state:
    st.session_state.last_db_check = 0


# Sidebar controls
with st.sidebar:
    st.header("⚙️ Controls")
    
    # Data mode selection
    st.subheader("📡 Data Source")
    data_mode = st.radio(
        "Select Data Mode",
        options=['mqtt', 'mock'],
        format_func=lambda x: "MQTT (Real Sensors)" if x == 'mqtt' else "Mock (Simulation)",
        index=0 if st.session_state.data_mode == 'mqtt' else 1
    )
    
    if data_mode != st.session_state.data_mode:
        st.session_state.data_mode = data_mode
        st.session_state.history = pd.DataFrame(columns=[
            'timestamp', 'h2s_ppm', 'nh3_ppm', 'co2_ppm', 'temp_c', 'humidity', 'quality_level'
        ])
        st.rerun()
    
    # MQTT Connection Status
    if st.session_state.data_mode == 'mqtt':
        mqtt_client = get_mqtt_client(st.session_state)
        
        # Poll for MQTT messages (simplified client uses polling)
        mqtt_client.poll(timeout=0.5)
        
        st.session_state.mqtt_connected = mqtt_client.is_connected()
        
        if st.session_state.mqtt_connected:
            st.success("✅ MQTT Connected")
        else:
            st.warning("⚠️ MQTT Disconnected")
            if st.button("🔄 Reconnect MQTT"):
                if mqtt_client.connect():
                    st.success("Reconnected!")
                    st.rerun()
    
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
        room_temp = 25  # Default for MQTT mode
        humidity = 60
    
    st.divider()
    
    # Reset button
    if st.button("🔄 Reset Data"):
        if st.session_state.data_mode == 'mock':
            reset_simulation()
        st.session_state.history = pd.DataFrame(columns=[
            'timestamp', 'h2s_ppm', 'nh3_ppm', 'co2_ppm', 'temp_c', 'humidity', 'quality_level'
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
        # Show database stats for MQTT mode
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
                               mq135_co2, mq136_h2s, mq137_nh3, quality_level, wifi_rssi
                        FROM sensor_readings
                        ORDER BY timestamp ASC
                    ''')
                    
                    rows = cursor.fetchall()
                    
                    # Create CSV in memory
                    output = io.StringIO()
                    writer = csv.writer(output)
                    
                    # Write header
                    writer.writerow(['ID', 'Timestamp', 'Device ID', 'Temperature (°C)',
                                   'Humidity (%)', 'CO2 (ppm)', 'H2S (ppm)', 'NH3 (ppm)',
                                   'Quality Level', 'WiFi RSSI'])
                    
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
                            row['quality_level'],
                            row['wifi_rssi']
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
    
    **CO2 (MQ135):**
    - Fresh: < {config.CO2_FRESH_THRESHOLD} ppm
    - Warning: {config.CO2_FRESH_THRESHOLD}-{config.CO2_WARNING_THRESHOLD} ppm
    - Critical: > {config.CO2_WARNING_THRESHOLD} ppm
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


# Update data (Mock or MQTT)
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
            'co2_ppm': readings['methane_ppm'],  # Map methane to co2 for display
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

elif st.session_state.data_mode == 'mqtt':
    # Load data from database
    current_time = time.time()
    
    if current_time - st.session_state.last_db_check >= config.CHART_REFRESH_INTERVAL:
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
                    'co2_ppm': reading['mq135_co2'],
                    'temp_c': reading['temperature'],
                    'humidity': reading['humidity'],
                    'quality_level': reading['quality_level']
                })
            
            st.session_state.history = pd.DataFrame(df_data)
        
        st.session_state.last_db_check = current_time
        # Removed redundant st.rerun() - already handled at end of script


# Get current readings
if len(st.session_state.history) > 0:
    current = st.session_state.history.iloc[-1]
else:
    current = {
        'h2s_ppm': 0.0,
        'nh3_ppm': 0.0,
        'co2_ppm': 0.0,
        'temp_c': 0.0,
        'humidity': 0.0,
        'quality_level': 'UNKNOWN'
    }


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
    
    # Mock camera button
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📷 Capture Camera"):
            # Capture image from real camera
            with st.spinner("Capturing from camera..."):
                # Use Pi Camera V2 if available, otherwise try V4L2
                use_pi_v2 = check_pi_camera_v2_available()
                camera_image_bytes = get_camera_image_bytes(camera_index=0, use_pi_camera_v2=use_pi_v2)
                if camera_image_bytes is not None:
                    st.session_state.uploaded_image_bytes = camera_image_bytes
                    st.session_state.uploaded_image = None
                    st.success("Image captured successfully!")
                else:
                    st.error("Failed to capture image from camera. Please check camera connection.")
    
    with col_btn2:
        if st.button("🔄 Clear Image"):
            st.session_state.uploaded_image = None
            st.session_state.uploaded_image_bytes = None
            st.session_state.visual_prediction = None
    
    # Display image
    st.markdown("### Image Display")
    
    if st.session_state.uploaded_image_bytes is not None:
        # Display image from session state (persists across reruns)
        st.image(st.session_state.uploaded_image_bytes, width='stretch', caption="Captured from Camera")
    else:
        st.info("Upload an image or use Capture Camera to start visual analysis.")
    
    # CNN Prediction
    st.markdown("### CNN Prediction Results")
    
    if st.session_state.uploaded_image_bytes is not None:
        if st.session_state.simulation_running or st.button("🔍 Run CNN Prediction"):
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
        co2_color = get_color(current['co2_ppm'], config.CO2_FRESH_THRESHOLD, config.CO2_WARNING_THRESHOLD)
        st.metric(
            label="CO2 (MQ135)",
            value=f"{current['co2_ppm']:.2f} ppm",
            delta_color="normal"
        )
        st.markdown(f"<div style='height: 5px; background-color: {co2_color}; border-radius: 3px;'></div>",
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
    'ammonia_ppm': current['co2_ppm']  # Map CO2 to ammonia for fusion logic
}

# Get fusion decision from mock_data module
fusion_status, fusion_color = get_fusion_decision(visual_status, gas_readings)

# If using MQTT data, also consider the ESP quality level
if st.session_state.data_mode == 'mqtt' and current.get('quality_level') != 'UNKNOWN':
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
    gas_status = determine_gas_status(current['h2s_ppm'], current['nh3_ppm'], current['co2_ppm'])
    gas_color = config.QUALITY_COLORS.get(gas_status, "#FF9800")
    
    st.markdown(f"<div style='color: {gas_color}; font-size: 1.5rem; font-weight: bold;'>{gas_status}</div>", unsafe_allow_html=True)
    st.markdown(f"**H2S:** {current['h2s_ppm']:.2f} ppm")
    st.markdown(f"**NH3:** {current['nh3_ppm']:.2f} ppm")
    st.markdown(f"**CO2:** {current['co2_ppm']:.2f} ppm")


# ==================== CORRELATION HEATMAP ====================
st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🔥 Correlation Heatmap")
    if len(st.session_state.history) > 10:
        # Calculate correlation matrix
        corr_data = st.session_state.history[['h2s_ppm', 'nh3_ppm', 'co2_ppm', 'temp_c', 'humidity']].corr()
        
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
    
    st.markdown("### CO2 (MQ135)")
    co2_percent = min(100, (current['co2_ppm'] / config.CO2_WARNING_THRESHOLD) * 100)
    co2_bar_color = config.QUALITY_COLORS["SAFE"] if current['co2_ppm'] < config.CO2_FRESH_THRESHOLD else config.QUALITY_COLORS["WARNING"] if current['co2_ppm'] < config.CO2_WARNING_THRESHOLD else config.QUALITY_COLORS["SPOILED"]
    st.markdown(f"""
    <div style='background-color: #e0e0e0; border-radius: 10px; height: 25px; overflow: hidden;'>
        <div style='background-color: {co2_bar_color}; width: {co2_percent}%; height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;'>
            {current['co2_ppm']:.2f} ppm / {config.CO2_WARNING_THRESHOLD} ppm
        </div>
    </div>
    """, unsafe_allow_html=True)


# Footer
st.divider()
st.markdown(f"""
<div style='text-align: center; color: #666;'>
    <p>🥩 Multi-Modal Meat Quality Monitoring System | Computer Vision + Gas Sensors</p>
    <p>Sensors: MQ136 (H2S), MQ137 (NH3), MQ135 (CO2), AHT10 (Temp/Humidity)</p>
    <p>Data Mode: <strong>{'MQTT (Real Sensors)' if st.session_state.data_mode == 'mqtt' else 'Mock (Simulation)'}</strong></p>
</div>
""", unsafe_allow_html=True)


# Auto-refresh for mock mode
if st.session_state.data_mode == 'mock' and st.session_state.simulation_running:
    time.sleep(config.CHART_REFRESH_INTERVAL)
    st.rerun()
elif st.session_state.data_mode == 'mqtt' and config.AUTO_REFRESH_ENABLED:
    time.sleep(config.CHART_REFRESH_INTERVAL)
    st.rerun()
