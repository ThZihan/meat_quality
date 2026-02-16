# ESP32 Meat Quality Sensor Node (MQTT Version)

A production-ready ESP32 firmware for monitoring meat quality using MQ135, MQ136, and MQ137 gas sensors. This version sends sensor readings to a Raspberry Pi via MQTT protocol for real-time monitoring and data visualization.

## Features

- **Three MQ Sensors**: MQ135 (VOC), MQ136 (H2S/NH3/CO), MQ137 (NH3)
- **WiFi Connectivity**: Connects to local WiFi network
- **MQTT Protocol**: Sends data to Raspberry Pi Mosquitto broker
- **JSON Serialization**: ArduinoJson for structured data transmission
- **2-Second Interval**: Regular sensor readings every 2 seconds
- **Meat Quality Assessment**: Automatic quality classification (Excellent/Good/Fair/Spoiled)
- **Production Ready**: Hardcoded calibration values from 24-hour burn-in

## Hardware Requirements

### Components
- ESP32 NodeMCU or any ESP32 board
- MQ135 Gas Sensor Module
- MQ136 Gas Sensor Module
- MQ137 Gas Sensor Module
- Three voltage dividers (each: two 10kΩ resistors in parallel + one 10kΩ resistor)
- 5V power supply for MQ sensors
- Breadboard and jumper wires
- Raspberry Pi (running Mosquitto MQTT broker)

### Pin Connections

#### MQ135 (VOC Sensor)
- VCC → 5V
- GND → GND
- AOUT → Voltage Divider → ESP32 GPIO 34 (ADC1_CH6)

#### MQ136 (H2S/NH3/CO Sensor)
- VCC → 5V
- GND → GND
- AOUT → Voltage Divider → ESP32 GPIO 35 (ADC1_CH7)

#### MQ137 (NH3 Sensor)
- VCC → 5V
- GND → GND
- AOUT → Voltage Divider → ESP32 GPIO 32 (ADC1_CH4)

### Voltage Divider Circuit

For each sensor, build this voltage divider to protect ESP32 from 5V:

```
MQ AOUT ────[10k||10k = 5k]───┬───[10kΩ]─── GND
                            │
                            └─── ESP32 GPIO
```

**Calculation**: Vout = Vin × (10k / 15k) = Vin × 0.667
**Correction**: Multiply by 1.5 in code to get actual sensor voltage

## Software Requirements

### Required Libraries

Install these libraries via PlatformIO (automatically installed from `platformio.ini`):
- **PubSubClient** by Nick O'Leary (v2.8 or later) - MQTT client
- **ArduinoJson** by Benoit Blanchon (v6.21.0 or later) - JSON serialization

WiFi library is included in ESP32 Arduino framework.

### Raspberry Pi Setup

1. **Install Mosquitto MQTT Broker**:
   ```bash
   sudo apt install mosquitto mosquitto-clients -y
   sudo systemctl enable mosquitto
   sudo systemctl start mosquitto
   ```

2. **Configure Mosquitto**:
   ```bash
   # Create password file
   sudo mosquitto_passwd -c /etc/mosquitto/passwd meat_monitor
   # Enter password: meat_monitor
   
   # Edit configuration
   sudo nano /etc/mosquitto/mosquitto.conf
   ```
   
   Add:
   ```
   listener 1883
   allow_anonymous false
   password_file /etc/mosquitto/passwd
   ```
   
   Restart:
   ```bash
   sudo systemctl restart mosquitto
   ```

3. **Install Python Dashboard**:
   ```bash
   cd /path/to/meat-quality-monitoring
   pip install -r requirements.txt
   streamlit run app.py
   ```

## Configuration

### WiFi Configuration

Edit `src/main.cpp` and update these lines:

```cpp
// Line 119-120: Update with your WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";           // Your WiFi network name
const char* password = "YOUR_WIFI_PASSWORD";   // Your WiFi password
```

### MQTT Configuration

Edit `src/main.cpp` and update these lines:

```cpp
// Line 123-128: Update with your Raspberry Pi IP and MQTT settings
const char* mqttBroker = "192.168.1.100";     // Raspberry Pi IP address
const int mqttPort = 1883;
const char* mqttTopic = "meat-quality/data";
const char* mqttClientId = "ESP32-MeatMonitor";
const char* mqttUser = "meat_monitor";
const char* mqttPassword = "meat_monitor";
```

**Important**: The `mqttBroker` IP address must match your Raspberry Pi's IP address.

## Calibration Values

R0 values from 24-hour burn-in in fresh air:
- MQ135 R0: 193200.00 Ω
- MQ136 R0: 85102.55 Ω
- MQ137 R0: 51913.09 Ω

These values are hardcoded in firmware and should not need adjustment unless you replace sensors.

## Installation

### Build and Upload

Using PlatformIO:
```bash
cd ESP_sensor_node
pio run --target upload
```

Using Arduino IDE:
1. Open `src/main.cpp`
2. Select Board: "NodeMCU-32S"
3. Select Port: Your ESP32 COM port
4. Click Upload

### Serial Monitor

Open Serial Monitor at 115200 baud to view sensor readings:
```bash
pio device monitor
```

Or in Arduino IDE: Tools → Serial Monitor → 115200 baud

## MQTT Data Format

The ESP32 sends JSON data to the Raspberry Pi in this format:

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

### Data Mapping

- **timestamp**: ISO 8601 format timestamp
- **device_id**: Unique identifier for this ESP32 node
- **sensors.temperature**: Temperature in °C (placeholder: 25.0)
- **sensors.humidity**: Humidity in % (placeholder: 60.0)
- **sensors.mq135_co2**: VOC/CO2 reading in ppm
- **sensors.mq136_h2s**: H2S reading in ppm
- **sensors.mq137_nh3**: NH3 reading in ppm
- **quality.level**: Quality assessment (EXCELLENT/GOOD/FAIR/SPOILED)
- **wifi_rssi**: WiFi signal strength in dBm
- **sensor_status**: Additional sensor status (empty for now)

## Output Format

### Serial Monitor Output

The Serial Monitor displays:
1. **Raw ADC Values**: 0-4095 from ESP32 ADC
2. **Corrected Voltage**: Actual sensor voltage (0-5V)
3. **Sensor Resistance (Rs)**: Calculated from voltage
4. **Gas Concentrations**: PPM values for each detected gas
5. **Meat Quality Assessment**: Overall status based on thresholds

### Example Output

```
========================================
MQ135 + MQ136 + MQ137 Combined Sensors
ESP32 NodeMCU - MQTT Version
========================================

Connecting to WiFi...
SSID: YourWiFi
....
WiFi connected! IP address: 192.168.1.50
Signal strength (RSSI): -65 dBm

MQTT CONFIGURATION:
  Broker: 192.168.1.100
  Port: 1883
  Topic: meat-quality/data

Attempting MQTT connection...
MQTT connected!
Connected to broker: 192.168.1.100

========================================
SENSOR READINGS:
----------------------------------------
MQ135 (VOC/NH3):
  ADC: 1234, Voltage: 1.500 V, Rs: 23333.33 Ω
  VOC (Spoilage Index): 450.50 ppm
  NH3: 25.30 ppm

MQ136 (H2S/NH3/CO):
  ADC: 2345, Voltage: 2.850 V, Rs: 7543.86 Ω
  H2S: 3.20 ppm
  NH3: 15.40 ppm
  CO: 8.70 ppm

MQ137 (NH3):
  ADC: 3456, Voltage: 4.200 V, Rs: 1904.76 Ω
  NH3: 35.60 ppm

----------------------------------------
MEAT QUALITY ASSESSMENT:
----------------------------------------
  VOC: 450.50 ppm (Threshold: < 600)
  H2S: 3.20 ppm (Threshold: < 5)
  NH3: 35.60 ppm (Threshold: < 50)

  Status: EXCELLENT (Fresh)
  → All gas levels are normal
========================================

Data sent via MQTT successfully
```

## Meat Quality Thresholds

| Status | VOC | H2S | NH3 |
|--------|-----|-----|-----|
| **EXCELLENT** | < 600 ppm | < 5 ppm | < 50 ppm |
| **GOOD** | < 800 ppm | < 10 ppm | < 100 ppm |
| **FAIR** | < 1000 ppm | < 20 ppm | < 200 ppm |
| **SPOILED** | > 1000 ppm | > 20 ppm | > 200 ppm |

## Important Notes

### Sensor Preheating
- MQ sensors require 24-48 hours of preheating in fresh air for accurate readings
- During preheating, readings may be unstable
- Best results achieved after 48-hour burn-in

### Power Requirements
- **MQ Sensors**: Must be powered by 5V (NOT 3.3V)
- **ESP32**: Can be powered by USB or 5V supply
- **Common Ground**: All devices must share common ground

### Voltage Dividers
- **MANDATORY**: Voltage dividers are required to protect ESP32 from 5V
- Without dividers, ESP32 GPIO pins may be damaged
- Use exact resistor values specified (10kΩ)

### ADC Pins
- Use ADC1 pins (GPIO 34, 35, 36, 39) for sensor readings
- ADC2 pins conflict with WiFi if WiFi is enabled
- Current configuration uses ADC1_CH6, ADC1_CH7, ADC1_CH4

### Temperature/Humidity Sensors
- Current version uses placeholder values (25.0°C, 60.0%)
- TODO: Add DHT11/DHT22/AHT10 sensor for real temperature/humidity readings
- See code comments for integration points

## Troubleshooting

### WiFi Connection Issues
- Check SSID and password in `src/main.cpp`
- Ensure WiFi network is 2.4GHz (ESP32 doesn't support 5GHz)
- Verify ESP32 is within WiFi range
- Check Serial Monitor for connection status

### MQTT Connection Issues
- Verify Raspberry Pi IP address is correct
- Check Mosquitto is running on Raspberry Pi: `sudo systemctl status mosquitto`
- Verify MQTT username/password match Mosquitto configuration
- Check firewall settings on Raspberry Pi (port 1883)
- Test MQTT broker: `mosquitto_sub -h localhost -t "meat-quality/#" -v`

### No Readings
- Check Serial Monitor baud rate (must be 115200)
- Verify all connections
- Ensure sensors are powered by 5V
- Check voltage divider connections

### Inaccurate Readings
- Ensure sensors have been preheated for 24-48 hours
- Verify R0 values match your specific sensors
- Check voltage divider resistor values
- Ensure good air circulation around sensors

### High Readings Always
- Sensors may not be preheated yet
- Check for gas leaks or contamination
- Verify R0 calibration values
- Ensure sensors are in clean air for baseline

## Testing

### 1. Test WiFi Connection
Check Serial Monitor output should show:
```
Connecting to WiFi...
SSID: YourWiFi
....
WiFi connected! IP address: 192.168.1.50
Signal strength (RSSI): -65 dBm
```

### 2. Test MQTT Connection
Check Serial Monitor output should show:
```
Attempting MQTT connection...
MQTT connected!
Connected to broker: 192.168.1.100
```

### 3. Test MQTT Data Flow

On Raspberry Pi, monitor MQTT messages:
```bash
mosquitto_sub -h localhost -t "meat-quality/data" -u meat_monitor -P meat_monitor -v
```

You should see messages like:
```
meat-quality/data {"timestamp":"2024-01-01T12:00:00Z","device_id":"ESP32-MeatMonitor","sensors":{...},"quality":{"level":"EXCELLENT"},"wifi_rssi":-65,"sensor_status":{}}
```

### 4. Test Dashboard
1. Open Raspberry Pi dashboard in browser
2. Select **MQTT (Real Sensors)** mode
3. Verify MQTT connection status shows "Connected"
4. Check sensor readings are updating
5. Verify gas levels display correctly (H2S, NH3, CO2)

## Technical Details

### Gas Detection
- **MQ135**: VOC (Volatile Organic Compounds) - General spoilage indicator
- **MQ136**: H2S (Hydrogen Sulfide), NH3 (Ammonia), CO (Carbon Monoxide)
- **MQ137**: NH3 (Ammonia) - Specialized ammonia detection

### PPM Calculation
Uses standard MQ sensor formula:
```
Rs/R0 = a × (ppm)^b
ppm = ((Rs/R0) / a)^(1/b)
```

Where:
- Rs = Sensor resistance (calculated from voltage)
- R0 = Sensor resistance in clean air (calibrated)
- a, b = Sensitivity curve parameters (from datasheet)

### Voltage Correction
The code corrects for voltage divider:
```cpp
voltage = (adc / 4095.0) * 3.3 * 1.5;  // Multiply by 1.5 to correct divider
```

### Quality Level Mapping
- **FRESH** → **EXCELLENT** (Pi dashboard: SAFE)
- **GOOD** → **GOOD** (Pi dashboard: SAFE)
- **MODERATE** → **FAIR** (Pi dashboard: WARNING)
- **SPOILED** → **SPOILED** (Pi dashboard: SPOILED)

## Future Enhancements

- [ ] Add DHT11/DHT22/AHT10 for real temperature/humidity readings
- [ ] Add OTA (Over-The-Air) update capability
- [ ] Add EEPROM storage for calibration values
- [ ] Add multiple MQTT topics for different data types
- [ ] Add sensor status reporting (sensor health, calibration status)
- [ ] Add LED indicators for WiFi and MQTT connection status
- [ ] Add deep sleep mode for battery-powered operation

## Integration with Raspberry Pi Dashboard

This ESP32 firmware is designed to work seamlessly with the Raspberry Pi dashboard in the `meat-quality-monitoring/` directory. The dashboard expects MQTT messages in the exact format sent by this firmware.

For complete integration instructions, see `meat-quality-monitoring/DEPLOYMENT.md`.

## License

This project is provided as-is for educational and research purposes.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Verify all hardware connections
3. Ensure sensors are properly preheated
4. Review calibration values
5. Check Raspberry Pi Mosquitto configuration
6. Verify WiFi and MQTT credentials

## Version History

- **v2.0** (MQTT Version) - Added WiFi and MQTT connectivity for Raspberry Pi integration
- **v1.0** (Production Ready) - Initial release with clean serial output
