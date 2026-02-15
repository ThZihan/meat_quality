# Deployment Guide - Meat Quality Monitoring System

This guide covers the complete deployment of the ESP32 + Raspberry Pi meat quality monitoring system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Raspberry Pi Setup](#raspberry-pi-setup)
3. [ESP32 Setup](#esp32-setup)
4. [MQTT Broker Configuration](#mqtt-broker-configuration)
5. [Dashboard Deployment](#dashboard-deployment)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Required

- **Raspberry Pi** (3B+, 4, or newer recommended)
- **ESP32 NodeMCU** development board
- **Sensors:**
  - AHT10 (Temperature/Humidity)
  - MQ135 (CO2/VOCs)
  - MQ136 (H2S)
  - MQ137 (NH3)
- **Power supply** for both devices
- **WiFi network** with internet access

### Software Required

- Raspberry Pi OS (Bullseye or Bookworm)
- Python 3.8+
- Arduino IDE (for ESP32 programming)

---

## Raspberry Pi Setup

### 1. System Update

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Python Dependencies

```bash
cd /home/zihan/projects/meat-quality-monitoring
pip install -r requirements.txt
```

### 3. Install Mosquitto MQTT Broker

```bash
# Install Mosquitto
sudo apt install mosquitto mosquitto-clients -y

# Enable and start the service
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Check status
sudo systemctl status mosquitto
```

### 4. Configure Mosquitto

#### 4.1 Create Password File

```bash
# Create password file
sudo mosquitto_passwd -c /etc/mosquitto/passwd meat_monitor
# Enter password when prompted (use a strong password)
```

#### 4.2 Configure Mosquitto

Edit the configuration file:

```bash
sudo nano /etc/mosquitto/mosquitto.conf
```

Add the following configuration:

```
# Allow connections from local network
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

# Optional: Enable persistence
persistence true
persistence_location /var/lib/mosquitto/
autosave_interval 1800
```

#### 4.3 Restart Mosquitto

```bash
sudo systemctl restart mosquitto
sudo systemctl status mosquitto
```

### 5. Find Raspberry Pi IP Address

```bash
hostname -I
```

Note the IP address (e.g., `192.168.1.100`) - you'll need this for the ESP32 configuration.

---

## ESP32 Setup

### 1. Install Arduino IDE

Download and install from: https://www.arduino.cc/en/software

### 2. Install ESP32 Board Support

1. Open Arduino IDE
2. Go to **File → Preferences**
3. Add this URL to "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to **Tools → Board → Boards Manager**
5. Search for "esp32" and install "ESP32 by Espressif Systems"

### 3. Install Required Libraries

Install these libraries via **Sketch → Include Library → Manage Libraries**:

- **Adafruit AHTX0** by Adafruit
- **PubSubClient** by Nick O'Leary
- **ArduinoJson** by Benoit Blanchon

### 4. Configure ESP32 Code

Open [`esp_code.cpp`](../esp_code.cpp) and update the following:

```cpp
// Line 26: Update with your Raspberry Pi IP
const char* mqttBroker = "192.168.1.XXX";  // CHANGE THIS!

// Line 29-30: Set MQTT credentials
const char* mqttUser = "meat_monitor";
const char* mqttPassword = "your_secure_password";  // CHANGE THIS!

// Line 21-22: WiFi credentials
const char* ssid = "YourWiFiName";      // CHANGE THIS!
const char* password = "YourWiFiPassword";  // CHANGE THIS!
```

### 5. Upload Code to ESP32

1. Connect ESP32 to computer via USB
2. Select correct board: **Tools → Board → ESP32 Arduino → ESP32 Dev Module**
3. Select correct port: **Tools → Port → /dev/ttyUSB0** (or similar)
4. Click **Upload** button

### 6. Monitor Serial Output

After upload, open Serial Monitor at **115200 baud** to verify:
- WiFi connection
- MQTT connection
- Sensor readings

---

## MQTT Broker Configuration

### Test MQTT Broker

On Raspberry Pi, test the broker:

```bash
# Subscribe to test
mosquitto_sub -h localhost -t "test/topic" -u meat_monitor -P your_password

# In another terminal, publish test
mosquitto_pub -h localhost -t "test/topic" -m "Hello MQTT" -u meat_monitor -P your_password
```

### Firewall Configuration (if needed)

```bash
# Allow MQTT port
sudo ufw allow 1883/tcp
sudo ufw reload
```

---

## Dashboard Deployment

### 1. Update Configuration

Edit [`config.py`](config.py) if needed:

```python
# MQTT Configuration
MQTT_BROKER = "localhost"  # Keep as localhost for Pi
MQTT_USERNAME = "meat_monitor"
MQTT_PASSWORD = "your_secure_password"  # Match Mosquitto password

# Sensor Thresholds (adjust based on your requirements)
H2S_FRESH_THRESHOLD = 10.0
NH3_FRESH_THRESHOLD = 25.0
CO2_FRESH_THRESHOLD = 400.0
```

### 2. Create Data Directory

```bash
cd /home/zihan/projects/meat-quality-monitoring
mkdir -p data/backups data/exports
```

### 3. Run Dashboard (Local Access)

```bash
cd /home/zihan/projects/meat-quality-monitoring
streamlit run app.py
```

Access at: `http://localhost:8501`

### 4. Run Dashboard (Network Access)

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Access from any device on network: `http://<RASPBERRY_PI_IP>:8501`

### 5. Run as Service (Auto-start)

Create service file:

```bash
sudo nano /etc/systemd/system/meat-monitor.service
```

Add the following:

```ini
[Unit]
Description=Meat Quality Monitor Dashboard
After=network.target

[Service]
User=pi
WorkingDirectory=/home/zihan/projects/meat-quality-monitoring
ExecStart=/usr/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable meat-monitor.service
sudo systemctl start meat-monitor.service
sudo systemctl status meat-monitor.service
```

---

## Testing

### 1. Test ESP32 Connection

Check Serial Monitor output should show:
```
========================================
ESP32 NodeMCU - Meat Quality Monitoring
========================================
I2C initialized on SDA=21, SCL=22
AHT10 sensor found successfully!
MQ135 detected! ADC: XXXX, Voltage: X.XXV
MQ136 detected! ADC: XXXX, Voltage: X.XXV
MQ137 detected! ADC: XXXX, Voltage: X.XXV
WiFi connected!
IP Address: 192.168.1.XXX
MQTT connected!
```

### 2. Test MQTT Data Flow

On Raspberry Pi, monitor MQTT messages:

```bash
mosquitto_sub -h localhost -t "meat-quality/#" -u meat_monitor -P your_password -v
```

You should see messages like:
```
meat-quality/data {"timestamp":"12345678","device_id":"ESP32-MeatMonitor","sensors":{...}}
meat-quality/status online
```

### 3. Test Dashboard

1. Open dashboard in browser
2. Select **MQTT (Real Sensors)** mode
3. Verify MQTT connection status shows "Connected"
4. Check sensor readings are updating
5. Verify gas levels display correctly (H2S, NH3, CO2)
6. Test fusion analysis with visual predictions

### 4. Test Database

Check if data is being stored:

```bash
cd /home/zihan/projects/meat-quality-monitoring
python3 -c "from db_manager import get_db_manager; db = get_db_manager(); print(f'Total readings: {db.get_reading_count()}')"
```

### 5. Test Historical Data

1. Let the system run for a few minutes
2. Check the trends chart displays data
3. Verify correlation heatmap appears (after 10+ readings)
4. Test data export functionality

---

## Troubleshooting

### ESP32 Issues

| Problem | Solution |
|---------|----------|
| ESP32 won't connect to WiFi | Check SSID/password, verify WiFi is 2.4GHz |
| MQTT connection fails | Verify Raspberry Pi IP, check Mosquitto is running |
| Sensors not detected | Check I2C wiring (SDA=21, SCL=22), verify power supply |
| ADC readings always 0 | Check sensor connections, verify ADC1 pins used |

### Mosquitto Issues

| Problem | Solution |
|---------|----------|
| Mosquitto won't start | Check configuration file syntax, verify password file exists |
| Authentication failed | Verify username/password in ESP32 matches Mosquitto |
| Connection refused | Check firewall, verify port 1883 is open |
| Can't connect from ESP32 | Check `listener 1883` is in config |

### Dashboard Issues

| Problem | Solution |
|---------|----------|
| Dashboard won't start | Check Python dependencies, verify Streamlit installed |
| MQTT shows disconnected | Check Mosquitto status, verify config.py settings |
| No data in charts | Check database has readings, verify data mode is set to MQTT |
| Charts not updating | Check `AUTO_REFRESH_ENABLED` in config.py |

### Database Issues

| Problem | Solution |
|---------|----------|
| Database file not created | Check data directory permissions |
| Old data not deleted | Verify `DB_RETENTION_DAYS` is set correctly |
| Queries are slow | Check indexes are created, consider reducing history size |

---

## Performance Optimization

### Reduce Database Size

Edit [`config.py`](config.py):

```python
DB_RETENTION_DAYS = 7  # Keep only 7 days of data
MAX_HISTORY_READINGS = 500  # Reduce memory usage
```

### Optimize MQTT Performance

```python
# In config.py
MQTT_KEEPALIVE = 30  # Reduce from 60
MQTT_QOS = 0  # Use QoS 0 for faster delivery (less reliable)
```

### Disable Auto-refresh

```python
# In config.py
AUTO_REFRESH_ENABLED = False  # Manual refresh only
```

---

## Security Recommendations

1. **Change default passwords** for MQTT and WiFi
2. **Enable TLS/SSL** for production (port 8883)
3. **Restrict network access** to local network only
4. **Use firewall rules** to limit MQTT access
5. **Regular updates** for OS and packages
6. **Backup database** regularly

---

## Maintenance

### Daily

- Check dashboard is running
- Verify MQTT connection status
- Monitor sensor readings for anomalies

### Weekly

- Check database size
- Review sensor calibration
- Test backup system

### Monthly

- Update system packages
- Review and rotate MQTT passwords
- Clean up old data
- Export historical data

---

## Next Steps

After successful deployment:

1. Calibrate sensors for accurate readings
2. Set up alerts for critical conditions
3. Integrate with external monitoring systems
4. Train custom CNN model for visual analysis
5. Add additional sensor nodes for multi-location monitoring

---

## Support

For issues or questions:
- Check the [Integration Plan](../plans/meat-quality-monitoring-integration.md)
- Review Mosquitto documentation: https://mosquitto.org/documentation/
- Check Streamlit documentation: https://docs.streamlit.io/
