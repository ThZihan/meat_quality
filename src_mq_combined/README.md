# MQ135 + MQ136 + MQ137 Combined Air Quality Sensor

ESP32 NodeMCU project for meat quality air data monitoring using three MQ gas sensors (MQ135, MQ136, MQ137) with SoftAP web calibration support.

## 🎯 Features

- **Three MQ Sensors Combined**: MQ135 (CO2/NH3), MQ136 (H2S/NH3/CO), MQ137 (NH3)
- **SoftAP Web Calibration**: No WiFi router needed - calibrate directly from your phone
- **48-Hour Fresh Air Calibration**: Ready for balcony placement with extended calibration
- **Real-time Web Interface**: Monitor all sensor readings via browser
- **Meat Quality Assessment**: Combined analysis from all three sensors
- **Multiple Calibration Options**: 48-hour (recommended), 1-hour, or 10-minute (demo)

## 📋 Hardware Requirements

### Components
- ESP32 NodeMCU board
- MQ135 Air Quality Sensor module
- MQ136 Gas Sensor module
- MQ137 Ammonia Sensor module
- 6x 10kΩ resistors (for voltage dividers)
- 5V power supply (external or from NodeMCU)
- Breadboard and jumper wires

### Important: Voltage Level Safety
⚠️ **CRITICAL**: All MQ sensors operate at 5V, but ESP32 GPIO pins are 3.3V only!
- You **MUST** use voltage dividers to protect ESP32 from 5V
- Never connect MQ sensor AOUT directly to ESP32 GPIO

## 🔌 Circuit Wiring

### Voltage Divider Circuit (for each sensor)
```
MQ Sensor AOUT ────[10kΩ]───┬───[10kΩ]─── GND
                             │
                             └─── ESP32 GPIO
```

### Complete Wiring Diagram

| MQ135 Sensor | ESP32 NodeMCU |
|--------------|---------------|
| VCC          | 5V            |
| GND          | GND           |
| AOUT         | Voltage Divider → GPIO 34 |

| MQ136 Sensor | ESP32 NodeMCU |
|--------------|---------------|
| VCC          | 5V            |
| GND          | GND           |
| AOUT         | Voltage Divider → GPIO 35 |

| MQ137 Sensor | ESP32 NodeMCU |
|--------------|---------------|
| VCC          | 5V            |
| GND          | GND           |
| AOUT         | Voltage Divider → GPIO 32 |

### Voltage Divider Details
- **Input**: 0-5V from MQ sensor
- **Output**: 0-3.33V to ESP32 (safe for 3.3V logic)
- **Formula**: Vout = Vin × (10k / 20k) = Vin × 0.5
- **Why 10k resistors?**: Creates 2:1 voltage divider, safe for ESP32

### ADC Pin Selection
- **GPIO 34 (ADC1_CH6)**: MQ135 - Safe with WiFi enabled
- **GPIO 35 (ADC1_CH7)**: MQ136 - Safe with WiFi enabled
- **GPIO 32 (ADC1_CH4)**: MQ137 - Safe with WiFi enabled

⚠️ **IMPORTANT**: Always use ADC1 pins (GPIO 34, 35, 36, 39) when using WiFi. ADC2 pins conflict with WiFi!

## 🚀 Getting Started

### 1. Install PlatformIO
If using VS Code:
1. Install PlatformIO extension
2. Open this project folder

### 2. Build and Upload
```bash
# Build the project
pio run

# Upload to ESP32
pio run --target upload

# Monitor serial output
pio device monitor
```

### 3. Connect to SoftAP
1. Power on the ESP32
2. On your phone, connect to WiFi network: **"MQ-Calibrator"** (no password)
3. Open browser and go to: **http://192.168.4.1**
4. You should see the calibration web interface

## 📊 Calibration Guide

### Why Calibrate?
MQ sensors need to be calibrated in clean air to establish the baseline resistance (R0). Without calibration, readings will be inaccurate.

### Recommended: 48-Hour Calibration
For best accuracy, calibrate for 48 hours in fresh air:

1. **Place the device** in a balcony or well-ventilated outdoor area
2. **Ensure fresh air circulation** around all three sensors
3. **Connect to SoftAP**: "MQ-Calibrator"
4. **Open browser**: http://192.168.4.1
5. **Click "Start 48-Hour Calibration"** button
6. **Leave undisturbed** for 48 hours
7. **Monitor progress** on the web interface
8. **After 48 hours**, copy the displayed R0 values
9. **Update R0 constants** in [`main.cpp`](src/main.cpp:85-87):
   ```cpp
   const float MQ135_R0 = [copied value];
   const float MQ136_R0 = [copied value];
   const float MQ137_R0 = [copied value];
   ```
10. **Re-upload** the code with new R0 values

### Quick Calibration Options
For testing purposes, you can use shorter calibration times:
- **1-Hour Calibration**: Quick test, less accurate
- **10-Minute Calibration**: Demo mode, for testing only

### Typical R0 Values
- MQ135: 10kΩ - 100kΩ (varies by sensor)
- MQ136: 10kΩ - 100kΩ (varies by sensor)
- MQ137: 10kΩ - 100kΩ (varies by sensor)

## 📈 Sensor Readings

### Web Interface
The web interface displays real-time readings from all three sensors:

**MQ135 (CO2/NH3)**
- ADC Value
- Voltage
- Rs (Sensor Resistance)
- CO2 (ppm)
- NH3 (ppm)

**MQ136 (H2S/NH3/CO)**
- ADC Value
- Voltage
- Rs (Sensor Resistance)
- H2S (ppm)
- NH3 (ppm)
- CO (ppm)

**MQ137 (NH3)**
- ADC Value
- Voltage
- Rs (Sensor Resistance)
- NH3 (ppm)

### Serial Monitor
Open Serial Monitor at 115200 baud to see detailed readings:
```
SENSOR READINGS:
MQ135 (CO2/NH3):
  ADC: 1234, Voltage: 2.500 V, Rs: 150000.00 Ω
  CO2: 450.00 ppm
  NH3: 25.00 ppm
...
```

## 🥩 Meat Quality Assessment

The system provides combined meat quality assessment based on all three sensors:

| Status | CO2 | H2S | NH3 | Description |
|--------|-----|-----|-----|-------------|
| **FRESH** | < 600 ppm | < 5 ppm | < 50 ppm | All gas levels normal |
| **GOOD** | < 800 ppm | < 10 ppm | < 100 ppm | Slightly elevated |
| **MODERATE** | < 1000 ppm | < 20 ppm | < 200 ppm | Elevated - monitor closely |
| **SPOILED** | > 1000 ppm | > 20 ppm | > 200 ppm | High - meat may be spoiled |

### Gas Detection Ranges

**MQ135 (CO2/NH3)**
- CO2: 400-2000 ppm
- NH3: 10-300 ppm

**MQ136 (H2S/NH3/CO)**
- H2S: 1-200 ppm (primary for meat spoilage)
- NH3: 10-300 ppm
- CO: 1-1000 ppm

**MQ137 (NH3)**
- NH3: 10-500 ppm (specialized ammonia detection)

## ⚙️ Configuration

### Hardware Configuration
Edit these values in [`main.cpp`](src/main.cpp:64-67):
```cpp
const int MQ135_PIN = 34;  // ADC1_CH6
const int MQ136_PIN = 35;  // ADC1_CH7
const int MQ137_PIN = 32;  // ADC1_CH4
const float VOLTAGE_DIVIDER_RATIO = 1.5;  // 5V → 3.33V
```

### R0 Calibration Values
After calibration, update these values in [`main.cpp`](src/main.cpp:85-87):
```cpp
const float MQ135_R0 = 192843.78;  // Update with calibrated value
const float MQ136_R0 = 20000.0;    // Update with calibrated value
const float MQ137_R0 = 25000.0;    // Update with calibrated value
```

### WiFi Configuration
Edit SoftAP settings in [`main.cpp`](src/main.cpp:110-111):
```cpp
const char* SOFTAP_SSID = "MQ-Calibrator";
const char* SOFTAP_PASSWORD = "";  // Empty = open network
```

## 🔧 Troubleshooting

### Sensors Not Reading
- Check wiring connections
- Verify voltage dividers are correctly installed
- Ensure sensors are powered with 5V
- Check ADC pin assignments

### WiFi Not Starting
- Ensure using ADC1 pins (34, 35, 32) - ADC2 conflicts with WiFi
- Check SoftAP SSID doesn't conflict with existing networks
- Try resetting ESP32

### Inaccurate Readings
- Complete 48-hour calibration in fresh air
- Ensure sensors are preheated (24-48 hours)
- Check voltage divider ratios
- Verify R0 values are updated after calibration

### Web Interface Not Accessible
- Confirm connected to "MQ-Calibrator" WiFi
- Check browser URL: http://192.168.4.1
- Try refreshing the page
- Check Serial Monitor for errors

## 📚 Technical Details

### ADC Configuration
- **Resolution**: 12-bit (0-4095)
- **Attenuation**: 11dB (full range 0-3.3V)
- **Sampling**: Every 2 seconds during normal operation
- **Calibration Sampling**: Every 100ms

### Sensor Calculation Formula
```
Rs = ((Vcc - Vout) / Vout) × RL
ppm = ((Rs/R0) / a)^(1/b)
```

Where:
- Rs = Sensor resistance
- Vcc = 5V (sensor supply)
- Vout = Measured voltage
- RL = 10kΩ (load resistor)
- R0 = Sensor resistance in clean air (calibrated)
- a, b = Sensitivity curve parameters (from datasheet)

## 📝 Project Structure

```
src_mq_combined/
├── src/
│   └── main.cpp          # Main firmware code
├── platformio.ini        # PlatformIO configuration
└── README.md             # This file
```

## 🤝 Contributing

This is a standalone project for meat quality air data monitoring. Feel free to modify and adapt for your needs.

## 📄 License

This project is provided as-is for educational and research purposes.

## ⚠️ Safety Notes

1. **Voltage Safety**: Always use voltage dividers when connecting 5V MQ sensors to 3.3V ESP32
2. **Power Supply**: Ensure stable 5V power for all MQ sensors
3. **Ventilation**: Place sensors in well-ventilated areas for accurate readings
4. **Preheating**: Allow 24-48 hours for sensors to stabilize before use
5. **Calibration**: Always calibrate in clean air before deployment

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review Serial Monitor output
3. Verify wiring connections
4. Ensure proper calibration

---

**Version**: 1.0.0  
**Last Updated**: 2026-02-09  
**Platform**: ESP32 NodeMCU  
**Framework**: Arduino  
**Sensors**: MQ135, MQ136, MQ137
