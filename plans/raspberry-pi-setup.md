# Raspberry Pi Setup Guide - Meat Quality Monitoring System

This guide covers setting up the Raspberry Pi to receive MQTT data from the ESP32, store it in a database, and display it on a web dashboard.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Network Configuration](#network-configuration)
3. [Mosquitto MQTT Broker Setup](#mosquitto-mqtt-broker-setup)
4. [SQLite Database Setup](#sqlite-database-setup)
5. [Python MQTT Subscriber](#python-mqtt-subscriber)
6. [Web Dashboard Setup](#web-dashboard-setup)
7. [Testing the System](#testing-the-system)

---

## System Requirements

- Raspberry Pi with Raspberry Pi OS (Bullseye or Bookworm)
- Internet connection
- SSH access or direct monitor/keyboard
- Minimum 2GB RAM recommended
- 8GB+ storage space

---

## Network Configuration

### 1. Set Static IP Address (Optional but Recommended)

Edit the DHCP configuration:
```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end of the file:
```conf
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

Or for WiFi:
```conf
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

Replace `192.168.1.100` with your desired IP address.

Reboot:
```bash
sudo reboot
```

### 2. Find Your Raspberry Pi IP

If not using static IP, find the current IP:
```bash
hostname -I
```

**Note:** Update this IP address in your ESP32 `main.cpp` file:
```cpp
const char* mqttBroker = "192.168.1.100";  // CHANGE THIS!
```

---

## Mosquitto MQTT Broker Setup

### 1. Install Mosquitto

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
```

### 2. Create MQTT User and Password

```bash
# Create a password file (replace 'meat_monitor' with your username)
sudo mosquitto_passwd -c /etc/mosquitto/passwd meat_monitor

# You'll be prompted to enter a password
# Enter: your_secure_password (or your chosen password)
```

### 3. Configure Mosquitto

Create/edit the configuration file:
```bash
sudo nano /etc/mosquitto/mosquitto.conf
```

Add the following configuration:
```conf
# Basic Configuration
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

# Persistence (retain messages across restarts)
persistence true
persistence_location /var/lib/mosquitto/

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_dest stdout
log_type all
log_timestamp true

# Connection Settings
max_connections -1
max_queued_messages 1000

# Security (optional - add for production)
# listener 8883
# certfile /etc/mosquitto/certs/server.crt
# keyfile /etc/mosquitto/certs/server.key
# cafile /etc/mosquitto/certs/ca.crt
```

### 4. Start and Enable Mosquitto Service

```bash
# Start the service
sudo systemctl start mosquitto

# Enable auto-start on boot
sudo systemctl enable mosquitto

# Check status
sudo systemctl status mosquitto
```

### 5. Configure Firewall (if using UFW)

```bash
# Allow MQTT port
sudo ufw allow 1883/tcp

# Check firewall status
sudo ufw status
```

### 6. Test Mosquitto Broker

**Terminal 1 - Subscribe to topic:**
```bash
mosquitto_sub -h localhost -t "meat-quality/#" -u meat_monitor -P your_secure_password -v
```

**Terminal 2 - Publish test message:**
```bash
mosquitto_pub -h localhost -t "meat-quality/test" -m "Hello from Pi!" -u meat_monitor -P your_secure_password
```

You should see the message in Terminal 1.

---

## SQLite Database Setup

### 1. Create Project Directory

```bash
mkdir -p ~/meat-quality-system
cd ~/meat-quality-system
mkdir -p data logs
```

### 2. Create Database Schema

Create the database initialization script:
```bash
nano ~/meat-quality-system/init_db.py
```

Add the following content:
```python
#!/usr/bin/env python3
"""
Initialize SQLite database for meat quality monitoring system
"""
import sqlite3
from datetime import datetime

DB_PATH = "data/meat_quality.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create sensor_readings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            device_id TEXT,
            temperature REAL,
            humidity REAL,
            mq135_co2 REAL,
            mq136_h2s REAL,
            mq137_nh3 REAL,
            quality_score INTEGER,
            quality_level TEXT,
            wifi_rssi INTEGER
        )
    ''')
    
    # Create device_status table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            device_id TEXT,
            status TEXT,
            last_seen DATETIME
        )
    ''')
    
    # Create indexes for better query performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON sensor_readings(timestamp DESC)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_device 
        ON sensor_readings(device_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_quality 
        ON sensor_readings(quality_level)
    ''')
    
    conn.commit()
    print(f"Database initialized successfully at: {DB_PATH}")
    print("Tables created:")
    print("  - sensor_readings")
    print("  - device_status")
    
    conn.close()

if __name__ == "__main__":
    init_database()
```

Run the initialization:
```bash
python3 ~/meat-quality-system/init_db.py
```

---

## Python MQTT Subscriber

### 1. Install Python Dependencies

```bash
cd ~/meat-quality-system
pip3 install paho-mqtt flask flask-cors
```

Or create a requirements.txt:
```bash
cat > ~/meat-quality-system/requirements.txt << EOF
paho-mqtt>=1.6.1
flask>=2.3.0
flask-cors>=4.0.0
EOF

pip3 install -r requirements.txt
```

### 2. Create MQTT Subscriber Script

```bash
nano ~/meat-quality-system/mqtt_subscriber/subscriber.py
```

Add the following content:
```python
#!/usr/bin/env python3
"""
MQTT Subscriber for Meat Quality Monitoring System
Receives sensor data from ESP32 and stores in SQLite database
"""
import paho.mqtt.client as mqtt
import sqlite3
import json
import logging
from datetime import datetime
import os

# Configuration
BROKER = "localhost"
PORT = 1883
USER = "meat_monitor"
PASSWORD = "your_secure_password"
TOPIC_DATA = "meat-quality/data"
TOPIC_STATUS = "meat-quality/status"
TOPIC_LWT = "meat-quality/lwt"
DB_PATH = "data/meat_quality.db"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/subscriber.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Quality score mapping
QUALITY_SCORES = {
    "EXCELLENT": 100,
    "GOOD": 80,
    "FAIR": 60,
    "POOR": 40,
    "SPOILED": 20
}

def get_db_connection():
    """Create and return database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Ensure database and tables exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            device_id TEXT,
            temperature REAL,
            humidity REAL,
            mq135_co2 REAL,
            mq136_h2s REAL,
            mq137_nh3 REAL,
            quality_score INTEGER,
            quality_level TEXT,
            wifi_rssi INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            device_id TEXT,
            status TEXT,
            last_seen DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def store_sensor_reading(data):
    """Store sensor reading in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Extract data from JSON
        sensors = data.get('sensors', {})
        quality = data.get('quality', {})
        
        cursor.execute('''
            INSERT INTO sensor_readings 
            (device_id, temperature, humidity, mq135_co2, mq136_h2s, mq137_nh3, 
             quality_score, quality_level, wifi_rssi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('device_id'),
            sensors.get('temperature'),
            sensors.get('humidity'),
            sensors.get('mq135_co2'),
            sensors.get('mq136_h2s'),
            sensors.get('mq137_nh3'),
            QUALITY_SCORES.get(quality.get('level'), 0),
            quality.get('level'),
            data.get('wifi_rssi')
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Stored sensor reading from {data.get('device_id')}")
        return True
    except Exception as e:
        logger.error(f"Error storing sensor reading: {e}")
        return False

def update_device_status(device_id, status):
    """Update device status in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO device_status (device_id, status, last_seen)
            VALUES (?, ?, ?)
        ''', (device_id, status, now))
        
        conn.commit()
        conn.close()
        logger.info(f"Updated device status: {device_id} -> {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating device status: {e}")
        return False

def on_connect(client, userdata, flags, rc):
    """Callback when connected to MQTT broker"""
    if rc == 0:
        logger.info(f"Connected to MQTT broker at {BROKER}:{PORT}")
        # Subscribe to topics
        client.subscribe(TOPIC_DATA)
        client.subscribe(TOPIC_STATUS)
        client.subscribe(TOPIC_LWT)
        logger.info(f"Subscribed to topics: {TOPIC_DATA}, {TOPIC_STATUS}, {TOPIC_LWT}")
    else:
        logger.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    """Callback when message is received"""
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    
    logger.info(f"Message received on {topic}")
    
    try:
        if topic == TOPIC_DATA:
            data = json.loads(payload)
            store_sensor_reading(data)
        elif topic in [TOPIC_STATUS, TOPIC_LWT]:
            # Parse device_id from payload or use default
            device_id = "ESP32-MeatMonitor"
            update_device_status(device_id, payload)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def main():
    """Main function"""
    # Ensure database exists
    init_database()
    
    # Create MQTT client
    client = mqtt.Client(client_id="Pi-Subscriber")
    client.username_pw_set(USER, PASSWORD)
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect to broker
    try:
        logger.info(f"Connecting to MQTT broker {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, 60)
        
        # Start loop (non-blocking)
        client.loop_start()
        
        logger.info("MQTT subscriber running. Press Ctrl+C to stop.")
        
        # Keep script running
        while True:
            pass
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        logger.error(f"Error: {e}")
        client.loop_stop()

if __name__ == "__main__":
    main()
```

### 3. Make Script Executable

```bash
chmod +x ~/meat-quality-system/mqtt_subscriber/subscriber.py
```

### 4. Test the Subscriber

```bash
cd ~/meat-quality-system
python3 mqtt_subscriber/subscriber.py
```

In another terminal, publish a test message:
```bash
mosquitto_pub -h localhost -t "meat-quality/data" -m '{"device_id":"test","sensors":{"temperature":3.5,"humidity":75.0},"quality":{"level":"GOOD"}}' -u meat_monitor -P your_secure_password
```

---

## Web Dashboard Setup

### 1. Create Flask API

```bash
nano ~/meat-quality-system/api/app.py
```

Add the following content:
```python
#!/usr/bin/env python3
"""
Flask API for Meat Quality Monitoring Dashboard
Provides REST endpoints for accessing sensor data
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

DB_PATH = "data/meat_quality.db"

def get_db_connection():
    """Create database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/latest', methods=['GET'])
def get_latest_reading():
    """Get the most recent sensor reading"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM sensor_readings 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"error": "No data available"}), 404

@app.route('/api/readings', methods=['GET'])
def get_readings():
    """Get sensor readings with optional time range and limit"""
    limit = request.args.get('limit', 100, type=int)
    hours = request.args.get('hours', 24, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    since = datetime.now() - timedelta(hours=hours)
    
    cursor.execute('''
        SELECT * FROM sensor_readings 
        WHERE timestamp >= ?
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (since.isoformat(), limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])

@app.route('/api/status', methods=['GET'])
def get_device_status():
    """Get current device status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM device_status 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    else:
        return jsonify({"error": "No status data available"}), 404

@app.route('/api/quality-summary', methods=['GET'])
def get_quality_summary():
    """Get quality level distribution"""
    hours = request.args.get('hours', 24, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    since = datetime.now() - timedelta(hours=hours)
    
    cursor.execute('''
        SELECT quality_level, COUNT(*) as count
        FROM sensor_readings 
        WHERE timestamp >= ?
        GROUP BY quality_level
    ''', (since.isoformat(),))
    
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### 2. Create Web Dashboard

```bash
nano ~/meat-quality-system/dashboard/index.html
```

Add the following content:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meat Quality Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .status-bar {
            background: rgba(255,255,255,0.95);
            padding: 15px 25px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #ccc;
        }
        .status-indicator.online {
            background: #4CAF50;
            box-shadow: 0 0 10px #4CAF50;
        }
        .status-indicator.offline {
            background: #f44336;
            box-shadow: 0 0 10px #f44336;
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: rgba(255,255,255,0.95);
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .card h3 {
            color: #1e3c72;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        .card .value {
            font-size: 2em;
            font-weight: bold;
            color: #2a5298;
        }
        .card .unit {
            font-size: 0.5em;
            color: #666;
        }
        .quality-badge {
            display: inline-block;
            padding: 10px 20px;
            border-radius: 20px;
            color: white;
            font-weight: bold;
            font-size: 1.2em;
        }
        .quality-EXCELLENT { background: #4CAF50; }
        .quality-GOOD { background: #8BC34A; }
        .quality-FAIR { background: #FFC107; color: #333; }
        .quality-POOR { background: #FF9800; }
        .quality-SPOILED { background: #f44336; }
        .charts {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .chart-container {
            background: rgba(255,255,255,0.95);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .chart-container h3 {
            color: #1e3c72;
            margin-bottom: 15px;
        }
        .last-updated {
            text-align: center;
            color: white;
            margin-top: 20px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🥩 Meat Quality Monitor</h1>
        
        <div class="status-bar">
            <div class="status-item">
                <div class="status-indicator" id="deviceStatus"></div>
                <span id="deviceStatusText">Checking...</span>
            </div>
            <div class="status-item">
                <span>📡 WiFi RSSI: </span>
                <strong id="wifiRssi">-- dBm</strong>
            </div>
        </div>
        
        <div class="cards">
            <div class="card">
                <h3>🌡️ Temperature</h3>
                <div class="value" id="temperature">--<span class="unit">°C</span></div>
            </div>
            <div class="card">
                <h3>💧 Humidity</h3>
                <div class="value" id="humidity">--<span class="unit">%</span></div>
            </div>
            <div class="card">
                <h3>🏷️ Quality</h3>
                <div class="quality-badge" id="qualityBadge">--</div>
            </div>
        </div>
        
        <div class="cards">
            <div class="card">
                <h3>💨 CO₂/VOCs (MQ135)</h3>
                <div class="value" id="mq135">--<span class="unit">ppm</span></div>
            </div>
            <div class="card">
                <h3>🧪 H₂S (MQ136)</h3>
                <div class="value" id="mq136">--<span class="unit">ppm</span></div>
            </div>
            <div class="card">
                <h3>🔬 NH₃ (MQ137)</h3>
                <div class="value" id="mq137">--<span class="unit">ppm</span></div>
            </div>
        </div>
        
        <div class="charts">
            <div class="chart-container">
                <h3>📈 Temperature History</h3>
                <canvas id="tempChart"></canvas>
            </div>
            <div class="chart-container">
                <h3>📊 Gas Levels History</h3>
                <canvas id="gasChart"></canvas>
            </div>
        </div>
        
        <div class="last-updated">
            Last updated: <span id="lastUpdated">--</span>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:5000/api';
        
        // Initialize charts
        const tempChart = new Chart(document.getElementById('tempChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Humidity (%)',
                    data: [],
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: { display: false },
                    y: { beginAtZero: false }
                }
            }
        });
        
        const gasChart = new Chart(document.getElementById('gasChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CO₂/VOCs',
                    data: [],
                    borderColor: '#9b59b6',
                    tension: 0.4
                }, {
                    label: 'H₂S',
                    data: [],
                    borderColor: '#1abc9c',
                    tension: 0.4
                }, {
                    label: 'NH₃',
                    data: [],
                    borderColor: '#f39c12',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: { display: false }
                }
            }
        });
        
        // Fetch latest data
        async function fetchLatest() {
            try {
                const response = await fetch(`${API_BASE}/latest`);
                const data = await response.json();
                
                if (data.error) return;
                
                // Update sensor values
                document.getElementById('temperature').innerHTML = 
                    `${data.temperature.toFixed(1)}<span class="unit">°C</span>`;
                document.getElementById('humidity').innerHTML = 
                    `${data.humidity.toFixed(1)}<span class="unit">%</span>`;
                document.getElementById('mq135').innerHTML = 
                    `${data.mq135_co2.toFixed(1)}<span class="unit">ppm</span>`;
                document.getElementById('mq136').innerHTML = 
                    `${data.mq136_h2s.toFixed(1)}<span class="unit">ppm</span>`;
                document.getElementById('mq137').innerHTML = 
                    `${data.mq137_nh3.toFixed(1)}<span class="unit">ppm</span>`;
                
                // Update quality badge
                const qualityBadge = document.getElementById('qualityBadge');
                qualityBadge.textContent = data.quality_level;
                qualityBadge.className = 'quality-badge quality-' + data.quality_level;
                
                // Update WiFi RSSI
                document.getElementById('wifiRssi').textContent = `${data.wifi_rssi} dBm`;
                
                // Update timestamp
                document.getElementById('lastUpdated').textContent = 
                    new Date(data.timestamp).toLocaleString();
                
            } catch (error) {
                console.error('Error fetching latest data:', error);
            }
        }
        
        // Fetch history
        async function fetchHistory() {
            try {
                const response = await fetch(`${API_BASE}/readings?hours=2&limit=50`);
                const data = await response.json();
                
                // Reverse data for chronological order
                data.reverse();
                
                const labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
                const temps = data.map(d => d.temperature);
                const humidities = data.map(d => d.humidity);
                const co2 = data.map(d => d.mq135_co2);
                const h2s = data.map(d => d.mq136_h2s);
                const nh3 = data.map(d => d.mq137_nh3);
                
                // Update temperature chart
                tempChart.data.labels = labels;
                tempChart.data.datasets[0].data = temps;
                tempChart.data.datasets[1].data = humidities;
                tempChart.update();
                
                // Update gas chart
                gasChart.data.labels = labels;
                gasChart.data.datasets[0].data = co2;
                gasChart.data.datasets[1].data = h2s;
                gasChart.data.datasets[2].data = nh3;
                gasChart.update();
                
            } catch (error) {
                console.error('Error fetching history:', error);
            }
        }
        
        // Fetch device status
        async function fetchStatus() {
            try {
                const response = await fetch(`${API_BASE}/status`);
                const data = await response.json();
                
                const indicator = document.getElementById('deviceStatus');
                const text = document.getElementById('deviceStatusText');
                
                if (data.status === 'online') {
                    indicator.className = 'status-indicator online';
                    text.textContent = 'Device Online';
                } else {
                    indicator.className = 'status-indicator offline';
                    text.textContent = 'Device Offline';
                }
                
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }
        
        // Initial load
        fetchLatest();
        fetchHistory();
        fetchStatus();
        
        // Auto-refresh every 2 seconds
        setInterval(fetchLatest, 2000);
        setInterval(fetchHistory, 10000);
        setInterval(fetchStatus, 5000);
    </script>
</body>
</html>
```

### 3. Run the API and Dashboard

**Terminal 1 - Run MQTT Subscriber:**
```bash
cd ~/meat-quality-system
python3 mqtt_subscriber/subscriber.py
```

**Terminal 2 - Run Flask API:**
```bash
cd ~/meat-quality-system
python3 api/app.py
```

**Access Dashboard:**
Open a web browser and navigate to:
```
http://localhost:5000/dashboard/index.html
```
Or from another device on the network:
```
http://192.168.1.100:5000/dashboard/index.html
```

---

## Testing the System

### 1. Test ESP32 Connection

1. Update the ESP32 `main.cpp` with your Raspberry Pi IP:
```cpp
const char* mqttBroker = "192.168.1.100";  // Your Pi IP
```

2. Upload the ESP32 firmware

3. Open Serial Monitor (115200 baud)

4. Verify:
   - WiFi connection successful
   - MQTT connection successful
   - JSON payload published

### 2. Verify Data Flow

Check the MQTT subscriber terminal for incoming messages.

Check the database:
```bash
sqlite3 ~/meat-quality-system/data/meat_quality.db "SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 5;"
```

### 3. Test API Endpoints

```bash
# Get latest reading
curl http://localhost:5000/api/latest

# Get readings
curl http://localhost:5000/api/readings?hours=1&limit=10

# Get status
curl http://localhost:5000/api/status

# Health check
curl http://localhost:5000/api/health
```

---

## System Startup Scripts

### Create systemd service for MQTT Subscriber

```bash
sudo nano /etc/systemd/system/meat-quality-subscriber.service
```

Add:
```ini
[Unit]
Description=Meat Quality MQTT Subscriber
After=network.target mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/meat-quality-system
ExecStart=/usr/bin/python3 /home/pi/meat-quality-system/mqtt_subscriber/subscriber.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable meat-quality-subscriber
sudo systemctl start meat-quality-subscriber
sudo systemctl status meat-quality-subscriber
```

### Create systemd service for Flask API

```bash
sudo nano /etc/systemd/system/meat-quality-api.service
```

Add:
```ini
[Unit]
Description=Meat Quality API
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/meat-quality-system
ExecStart=/usr/bin/python3 /home/pi/meat-quality-system/api/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable meat-quality-api
sudo systemctl start meat-quality-api
sudo systemctl status meat-quality-api
```

---

## Troubleshooting

### Mosquitto Issues

**Connection refused:**
```bash
sudo systemctl status mosquitto
sudo journalctl -u mosquitto -n 50
```

**Authentication errors:**
- Check password file: `sudo cat /etc/mosquitto/passwd`
- Verify username/password in ESP32 code

### Database Issues

**Permission denied:**
```bash
chmod 644 ~/meat-quality-system/data/meat_quality.db
chmod 755 ~/meat-quality-system/data
```

### API Issues

**Port 5000 already in use:**
```bash
sudo lsof -i :5000
# Kill the process or change port in app.py
```

---

## Security Recommendations

1. **Change default passwords** - Use strong passwords for MQTT
2. **Enable TLS/SSL** - Use port 8883 with certificates for production
3. **Network isolation** - Consider a separate IoT VLAN
4. **Regular updates** - Keep system and packages updated
5. **Firewall rules** - Only allow necessary ports
6. **Database backups** - Set up regular backups

---

## Next Steps

1. Set up NTP on ESP32 for accurate timestamps
2. Add email/SMS alerts for quality threshold breaches
3. Implement data retention policy (cleanup old records)
4. Add user authentication for dashboard
5. Deploy to production environment
