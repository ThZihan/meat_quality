# ESP32 MQTT Integration Summary

## Overview

This document summarizes the modifications made to the ESP32 sensor node to enable MQTT communication with the Raspberry Pi meat quality monitoring system.

## Changes Made

### 1. ESP32 Firmware (`src/main.cpp`)

#### Added Libraries
- **WiFi.h**: For WiFi connectivity
- **PubSubClient.h**: For MQTT communication
- **ArduinoJson.h**: For JSON serialization

#### New Configuration Sections

**WiFi Configuration** (Lines 119-120):
```cpp
const char* ssid = "YOUR_WIFI_SSID";           // Your WiFi network name
const char* password = "YOUR_WIFI_PASSWORD";   // Your WiFi password
```

**MQTT Configuration** (Lines 123-128):
```cpp
const char* mqttBroker = "192.168.1.100";     // Raspberry Pi IP address
const int mqttPort = 1883;
const char* mqttTopic = "meat-quality/data";
const char* mqttClientId = "ESP32-MeatMonitor";
const char* mqttUser = "meat_monitor";
const char* mqttPassword = "meat_monitor";
```

#### New Global Variables
```cpp
WiFiClient espClient;
PubSubClient mqttClient(espClient);
bool wifiConnected = false;
bool mqttConnected = false;
```

#### New Functions

**setupWiFi()** (Lines 267-291):
- Connects to WiFi network
- Prints connection status and IP address
- Displays WiFi signal strength (RSSI)

**reconnectMQTT()** (Lines 296-311):
- Attempts to reconnect to MQTT broker
- Uses authentication credentials
- Implements retry logic with 5-second intervals

**sendSensorData()** (Lines 316-368):
- Creates JSON document with sensor readings
- Maps quality levels to Pi's expected format
- Sends data via MQTT to Raspberry Pi
- Includes timestamp, device ID, sensors, quality, and WiFi RSSI

#### Modified Functions

**setup()** (Lines 140-192):
- Added WiFi initialization
- Added MQTT client setup
- Prints MQTT configuration information

**loop()** (Lines 194-314):
- Added MQTT connection maintenance
- Added automatic reconnection logic
- Calls sendSensorData() to transmit readings

### 2. PlatformIO Configuration (`platformio.ini`)

#### Added Library Dependencies
```ini
lib_deps =
	; MQTT client for communication with Raspberry Pi
	paulstoffregen/PubSubClient@^2.8
	; JSON library for data serialization
	bblanchon/ArduinoJson@^6.21.0
```

### 3. Documentation (`README.md`)

Updated README with:
- MQTT version features
- WiFi and MQTT configuration instructions
- Raspberry Pi setup guide
- MQTT data format specification
- Integration testing procedures
- Troubleshooting section for MQTT issues

## Data Flow

### ESP32 → Raspberry Pi

```
ESP32 Sensor Node
    ↓
WiFi Connection
    ↓
MQTT Client (PubSubClient)
    ↓
JSON Serialization (ArduinoJson)
    ↓
MQTT Broker (Mosquitto on Raspberry Pi)
    ↓
Python MQTT Client (paho-mqtt)
    ↓
SQLite Database
    ↓
Streamlit Dashboard
```

### MQTT Message Format

**Topic**: `meat-quality/data`

**Payload**:
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "device_id": "ESP32-MeatMonitor",
  "sensors": {
    "temperature": 25.0,
    "humidity": 60.0,
    "mq135_co2": 450.50,
    "mq136_h2s": 3.20,
    "mq137_nh3": 35.60
  },
  "quality": {
    "level": "EXCELLENT"
  },
  "wifi_rssi": -65,
  "sensor_status": {}
}
```

### Quality Level Mapping

| ESP32 Assessment | MQTT Level | Pi Dashboard Status |
|-----------------|------------|-------------------|
| FRESH | EXCELLENT | SAFE |
| GOOD | GOOD | SAFE |
| MODERATE | FAIR | WARNING |
| SPOILED | SPOILED | SPOILED |

## Configuration Steps

### Step 1: Configure Raspberry Pi

1. **Install Mosquitto MQTT Broker**:
   ```bash
   sudo apt update
   sudo apt install mosquitto mosquitto-clients -y
   sudo systemctl enable mosquitto
   sudo systemctl start mosquitto
   ```

2. **Configure Authentication**:
   ```bash
   # Create password file
   sudo mosquitto_passwd -c /etc/mosquitto/passwd meat_monitor
   # Enter password: meat_monitor
   
   # Edit configuration
   sudo nano /etc/mosquitto/mosquitto.conf
   ```

   Add to `mosquitto.conf`:
   ```
   listener 1883
   allow_anonymous false
   password_file /etc/mosquitto/passwd
   ```

   Restart:
   ```bash
   sudo systemctl restart mosquitto
   ```

3. **Get Raspberry Pi IP Address**:
   ```bash
   hostname -I
   ```
   Note the IP address (e.g., `192.168.1.100`)

### Step 2: Configure ESP32

1. **Edit WiFi Credentials**:
   Open `meat_quality_Air_data_ESP_Node/ESP_sensor_node/src/main.cpp` and update lines 119-120:
   ```cpp
   const char* ssid = "YourWiFiNetworkName";
   const char* password = "YourWiFiPassword";
   ```

2. **Edit Raspberry Pi IP Address**:
   Update line 123 with your Raspberry Pi's IP address:
   ```cpp
   const char* mqttBroker = "192.168.1.100";  // Your Pi's IP
   ```

3. **Build and Upload**:
   ```bash
   cd meat_quality_Air_data_ESP_Node/ESP_sensor_node
   pio run --target upload
   ```

### Step 3: Start Raspberry Pi Dashboard

1. **Install Python Dependencies**:
   ```bash
   cd /path/to/meat-quality-monitoring
   pip install -r requirements.txt
   ```

2. **Run Dashboard**:
   ```bash
   streamlit run app.py --server.address 0.0.0.0 --server.port 8501
   ```

3. **Access Dashboard**:
   - Local: `http://localhost:8501`
   - Network: `http://<RASPBERRY_PI_IP>:8501`

## Testing

### Test 1: WiFi Connection

Check ESP32 Serial Monitor at 115200 baud:
```
Connecting to WiFi...
SSID: YourWiFi
....
WiFi connected! IP address: 192.168.1.50
Signal strength (RSSI): -65 dBm
```

### Test 2: MQTT Connection

Check ESP32 Serial Monitor:
```
Attempting MQTT connection...
MQTT connected!
Connected to broker: 192.168.1.100
```

### Test 3: MQTT Data Flow

On Raspberry Pi, monitor MQTT messages:
```bash
mosquitto_sub -h localhost -t "meat-quality/data" -u meat_monitor -P meat_monitor -v
```

Expected output:
```
meat-quality/data {"timestamp":"2024-01-01T12:00:00Z","device_id":"ESP32-MeatMonitor","sensors":{"temperature":25.0,"humidity":60.0,"mq135_co2":450.5,"mq136_h2s":3.2,"mq137_nh3":35.6},"quality":{"level":"EXCELLENT"},"wifi_rssi":-65,"sensor_status":{}}
```

### Test 4: Dashboard Integration

1. Open dashboard in browser
2. Select **MQTT (Real Sensors)** mode
3. Verify MQTT connection status shows "Connected"
4. Check sensor readings are updating every 2 seconds
5. Verify gas levels display correctly (H2S, NH3, CO2)
6. Check trends chart shows historical data
7. Verify quality assessment matches ESP32 status

## Troubleshooting

### ESP32 Won't Connect to WiFi

**Symptoms**: Serial Monitor shows "WiFi connection failed!"

**Solutions**:
1. Verify WiFi credentials are correct
2. Ensure WiFi network is 2.4GHz (ESP32 doesn't support 5GHz)
3. Check ESP32 is within WiFi range
4. Restart ESP32
5. Try different WiFi network

### ESP32 Won't Connect to MQTT

**Symptoms**: Serial Monitor shows "MQTT connection failed, rc=..."

**Solutions**:
1. Verify Raspberry Pi IP address is correct
2. Check Mosquitto is running: `sudo systemctl status mosquitto`
3. Verify MQTT username/password match Mosquitto configuration
4. Check firewall settings on Raspberry Pi: `sudo ufw allow 1883/tcp`
5. Test MQTT broker manually:
   ```bash
   mosquitto_sub -h localhost -t "test" -v
   mosquitto_pub -h localhost -t "test" -m "Hello"
   ```

### Dashboard Shows "MQTT Disconnected"

**Symptoms**: Dashboard shows MQTT status as disconnected

**Solutions**:
1. Check Mosquitto is running on Raspberry Pi
2. Verify `config.py` MQTT settings match Mosquitto configuration
3. Check MQTT credentials in `config.py`:
   ```python
   MQTT_BROKER = "localhost"
   MQTT_USERNAME = "meat_monitor"
   MQTT_PASSWORD = "meat_monitor"
   ```
4. Restart dashboard
5. Check Python logs for errors

### No Data in Dashboard

**Symptoms**: Dashboard connects but shows no sensor readings

**Solutions**:
1. Verify ESP32 is sending data (check Serial Monitor)
2. Monitor MQTT topic on Raspberry Pi:
   ```bash
   mosquitto_sub -h localhost -t "meat-quality/data" -u meat_monitor -P meat_monitor -v
   ```
3. Check database has readings:
   ```python
   from db_manager import get_db_manager
   db = get_db_manager()
   print(f"Total readings: {db.get_reading_count()}")
   ```
4. Verify data mode is set to "MQTT" in dashboard

### Inaccurate Sensor Readings

**Symptoms**: Gas readings seem incorrect or unstable

**Solutions**:
1. Ensure sensors have been preheated for 24-48 hours
2. Verify R0 values match your specific sensors
3. Check voltage divider resistor values (10kΩ)
4. Ensure sensors are in clean air for baseline
5. Check for gas leaks or contamination
6. Verify sensor connections are secure

## Important Notes

### Sensor Preheating
- MQ sensors require 24-48 hours of preheating in fresh air
- During preheating, readings may be unstable
- Best results achieved after 48-hour burn-in

### Voltage Dividers
- **MANDATORY**: Voltage dividers required to protect ESP32 from 5V
- Without dividers, ESP32 GPIO pins may be damaged
- Use exact resistor values specified (10kΩ)

### ADC Pin Selection
- Use ADC1 pins (GPIO 34, 35, 36, 39) for sensor readings
- ADC2 pins conflict with WiFi if WiFi is enabled
- Current configuration uses ADC1_CH6, ADC1_CH7, ADC1_CH4

### Temperature/Humidity Sensors
- Current version uses placeholder values (25.0°C, 60.0%)
- TODO: Add DHT11/DHT22/AHT10 sensor for real readings
- See code comments in `sendSensorData()` for integration points

## Security Considerations

1. **Change Default Passwords**:
   - Update MQTT password in both ESP32 and Mosquitto configuration
   - Use strong, unique passwords

2. **Network Security**:
   - Use WPA2/WPA3 WiFi encryption
   - Consider setting up a separate IoT network

3. **MQTT Security**:
   - Current implementation uses username/password authentication
   - For production, consider TLS/SSL encryption (port 8883)
   - Restrict MQTT access to local network only

4. **Firewall**:
   - Only open port 1883 for local network
   - Use firewall rules to limit access

## Performance Optimization

### Reduce MQTT Message Size
Current JSON size: ~400 bytes
- Consider using shorter field names if needed
- Remove unused fields (sensor_status)
- Compress data if bandwidth is limited

### Adjust Transmission Interval
Current interval: 2 seconds
- Increase to 5-10 seconds for battery-powered operation
- Decrease to 1 second for real-time monitoring
- Balance between responsiveness and power consumption

### Optimize JSON Buffer Size
Current buffer: 512 bytes
- Adjust based on actual message size
- Monitor memory usage with `ESP.getFreeHeap()`
- Reduce if memory is constrained

## Future Enhancements

1. **Real Temperature/Humidity Sensor**:
   - Add DHT11/DHT22/AHT10 sensor
   - Update `sendSensorData()` to read real values
   - Remove placeholder values

2. **OTA Updates**:
   - Enable Over-The-Air firmware updates
   - Use ArduinoOTA library
   - Secure with authentication

3. **EEPROM Storage**:
   - Store WiFi credentials in EEPROM
   - Store MQTT broker address in EEPROM
   - Store calibration values in EEPROM
   - Add configuration mode via web interface

4. **Multiple MQTT Topics**:
   - Separate topics for different data types
   - `meat-quality/sensors` for sensor readings
   - `meat-quality/status` for device status
   - `meat-quality/config` for configuration

5. **Sensor Status Reporting**:
   - Report sensor health
   - Report calibration status
   - Report preheating status
   - Report sensor errors

6. **LED Indicators**:
   - Add LED for WiFi connection status
   - Add LED for MQTT connection status
   - Add LED for sensor readings

7. **Deep Sleep Mode**:
   - Implement deep sleep for battery-powered operation
   - Wake up periodically to read sensors
   - Send data and go back to sleep

## Files Modified

1. **meat_quality_Air_data_ESP_Node/ESP_sensor_node/src/main.cpp**
   - Added WiFi and MQTT functionality
   - Added JSON serialization
   - Added data transmission logic

2. **meat_quality_Air_data_ESP_Node/ESP_sensor_node/platformio.ini**
   - Added PubSubClient library dependency
   - Added ArduinoJson library dependency

3. **meat_quality_Air_data_ESP_Node/ESP_sensor_node/README.md**
   - Updated with MQTT version documentation
   - Added configuration instructions
   - Added troubleshooting section

## Raspberry Pi Files (Reference)

The ESP32 firmware is designed to work with these Raspberry Pi files:

1. **meat-quality-monitoring/mqtt_client.py**
   - MQTT client implementation
   - Expects data in the format sent by ESP32
   - Stores data in SQLite database

2. **meat-quality-monitoring/config.py**
   - MQTT configuration settings
   - Sensor thresholds
   - Quality level mapping

3. **meat-quality-monitoring/app.py**
   - Streamlit dashboard
   - Displays MQTT data
   - Visualizes sensor readings

## Conclusion

The ESP32 sensor node has been successfully modified to send sensor data to the Raspberry Pi via MQTT protocol. The system now provides real-time monitoring with automatic data transmission, storage, and visualization.

For complete deployment instructions, refer to:
- `meat-quality-monitoring/DEPLOYMENT.md` - Raspberry Pi setup guide
- `meat_quality_Air_data_ESP_Node/ESP_sensor_node/README.md` - ESP32 setup guide

## Support

For issues or questions:
1. Check troubleshooting section in this document
2. Check ESP_sensor_node/README.md troubleshooting section
3. Check meat-quality-monitoring/DEPLOYMENT.md troubleshooting section
4. Verify all hardware connections
5. Ensure sensors are properly preheated
6. Review configuration settings
