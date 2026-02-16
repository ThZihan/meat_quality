# Meat Quality Monitoring - MQTT Integration

This document provides a quick start guide for integrating MQTT communication between the ESP32 meat quality monitor and Raspberry Pi.

---

## Quick Overview

```
ESP32 (Sensors) → MQTT (WiFi) → Raspberry Pi (Mosquitto) → SQLite Database → Web Dashboard
```

---

## Prerequisites

### Hardware
- ESP32 NodeMCU with meat quality sensors (AHT10, MQ135, MQ136, MQ137)
- Raspberry Pi with Raspberry Pi OS
- Both devices on the same WiFi network

### Software
- PlatformIO for ESP32 development
- Python 3 on Raspberry Pi

---

## Quick Start Guide

### Step 1: Configure ESP32

1. **Update MQTT Broker IP** in [`src/main.cpp`](src/main.cpp:26):
```cpp
const char* mqttBroker = "192.168.1.100";  // Your Raspberry Pi IP
```

2. **Update MQTT credentials** (optional, but recommended):
```cpp
const char* mqttUser = "meat_monitor";
const char* mqttPassword = "your_secure_password";
```

3. **Build and upload** to ESP32:
```bash
pio run --target upload
```

### Step 2: Set Up Raspberry Pi

1. **Find your Raspberry Pi IP**:
```bash
hostname -I
```

2. **Install Mosquitto MQTT broker**:
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
```

3. **Create MQTT user**:
```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd meat_monitor
# Enter your password when prompted
```

4. **Configure Mosquitto** - Edit `/etc/mosquitto/mosquitto.conf`:
```conf
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log
```

5. **Start Mosquitto**:
```bash
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

6. **Test Mosquitto**:
```bash
# Terminal 1 - Subscribe
mosquitto_sub -h localhost -t "meat-quality/#" -u meat_monitor -P your_password -v

# Terminal 2 - Publish test
mosquitto_pub -h localhost -t "meat-quality/test" -m "Hello" -u meat_monitor -P your_password
```

### Step 3: Set Up Database and Subscriber

1. **Create project directory**:
```bash
mkdir -p ~/meat-quality-system/{data,logs,mqtt_subscriber,api,dashboard}
cd ~/meat-quality-system
```

2. **Install Python dependencies**:
```bash
pip3 install paho-mqtt flask flask-cors
```

3. **Create database initialization script** (`init_db.py`):
```python
import sqlite3

conn = sqlite3.connect('data/meat_quality.db')
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

conn.commit()
conn.close()
print("Database initialized!")
```

4. **Initialize database**:
```bash
python3 init_db.py
```

### Step 4: Run the System

**Terminal 1 - MQTT Subscriber**:
```bash
cd ~/meat-quality-system
python3 mqtt_subscriber/subscriber.py
```

**Terminal 2 - Flask API**:
```bash
cd ~/meat-quality-system
python3 api/app.py
```

**Access Dashboard**:
Open browser to `http://localhost:5000/dashboard/index.html`

---

## MQTT Topics

| Topic | Purpose | Direction |
|-------|---------|-----------|
| `meat-quality/data` | Sensor readings | ESP32 → Pi |
| `meat-quality/status` | Device status | ESP32 → Pi |
| `meat-quality/lwt` | Last Will Testament | ESP32 → Pi |

---

## JSON Payload Format

```json
{
  "timestamp": "1234567890",
  "device_id": "ESP32-MeatMonitor",
  "sensors": {
    "temperature": 3.5,
    "humidity": 75.0,
    "mq135_co2": 450.0,
    "mq136_h2s": 15.0,
    "mq137_nh3": 25.0
  },
  "quality": {
    "level": "EXCELLENT"
  },
  "wifi_rssi": -45,
  "sensor_status": {
    "aht10": true,
    "mq135": true,
    "mq136": false,
    "mq137": true
  }
}
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/latest` | GET | Get most recent sensor reading |
| `/api/readings` | GET | Get historical readings (params: `limit`, `hours`) |
| `/api/status` | GET | Get current device status |
| `/api/quality-summary` | GET | Get quality level distribution |
| `/api/health` | GET | Health check |

---

## Important Notes

### WiFi Network
- **YES**, ESP32 and Raspberry Pi must be on the same WiFi network for local MQTT broker
- If they're on different networks, use a cloud MQTT broker (HiveMQ Cloud, Mosquitto Cloud)

### Static IP (Recommended)
Configure a static IP for your Raspberry Pi so the ESP32 can always find the broker:
```bash
sudo nano /etc/dhcpcd.conf
```
Add:
```conf
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

### Security
- Change default MQTT password
- Consider using TLS/SSL (port 8883) for production
- Use firewall rules to restrict access

---

## Troubleshooting

### ESP32 won't connect to MQTT
- Check WiFi connection in Serial Monitor
- Verify Raspberry Pi IP is correct
- Ensure both devices are on the same network
- Check Mosquitto logs: `sudo journalctl -u mosquitto -n 50`

### No data in database
- Check MQTT subscriber is running
- Verify MQTT topic matches
- Check subscriber logs: `tail -f ~/meat-quality-system/logs/subscriber.log`

### Dashboard not updating
- Ensure Flask API is running
- Check browser console for errors
- Verify API endpoint works: `curl http://localhost:5000/api/latest`

---

## Full Documentation

- **MQTT Integration Plan**: [`plans/mqtt-integration-plan.md`](plans/mqtt-integration-plan.md)
- **Raspberry Pi Setup**: [`plans/raspberry-pi-setup.md`](plans/raspberry-pi-setup.md)

---

## File Structure

### ESP32 Project
```
meat_quality_Air_data/
├── platformio.ini          # Updated with MQTT libraries
├── src/
│   └── main.cpp            # Updated with MQTT client
└── README-MQTT.md          # This file
```

### Raspberry Pi Project
```
~/meat-quality-system/
├── data/
│   └── meat_quality.db     # SQLite database
├── logs/
│   └── subscriber.log      # MQTT subscriber logs
├── mqtt_subscriber/
│   └── subscriber.py      # MQTT to database script
├── api/
│   └── app.py              # Flask REST API
├── dashboard/
│   └── index.html          # Web dashboard
└── init_db.py              # Database initialization
```

---

## Next Steps

1. **Test the system** - Verify data flows from ESP32 to Pi
2. **Set up auto-start** - Create systemd services for automatic startup
3. **Add alerts** - Implement email/SMS notifications for quality thresholds
4. **Data retention** - Set up cleanup of old database records
5. **Security hardening** - Enable TLS, add authentication for dashboard

---

## Support

For detailed setup instructions and troubleshooting, see:
- [`plans/mqtt-integration-plan.md`](plans/mqtt-integration-plan.md) - Architecture and planning
- [`plans/raspberry-pi-setup.md`](plans/raspberry-pi-setup.md) - Complete Raspberry Pi setup guide
