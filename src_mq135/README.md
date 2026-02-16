# MQ135 Sensor - ESP32 NodeMCU

This is a standalone project for testing the MQ135 air quality sensor with ESP32 NodeMCU.

## 📁 Project Structure

```
src_mq135/
├── main.cpp              # MQ135 sensor code
├── platformio.ini        # PlatformIO configuration
└── README.md            # This file
```

## 🚀 Quick Start

### Build and Upload

**Option 1: Using the batch script (from project root)**
```batch
build_mq135.bat
```

**Option 2: Manual commands (from src_mq135 directory)**
```bash
# Build
pio run

# Upload
pio run --target upload

# Monitor serial output
pio device monitor -b 115200
```

### From VSCode

1. Open this folder in VSCode: `File > Open Folder > src_mq135`
2. Build: Press `Ctrl+Shift+B` or use the PlatformIO toolbar
3. Upload: Click the arrow icon in the PlatformIO toolbar
4. Monitor: Click the plug icon in the PlatformIO toolbar

## ⚡ Circuit Wiring

### Voltage Divider (CRITICAL!)

```
MQ135 MODULE:
VCC  → 5V (external power supply)
GND  → GND (common ground)
AOUT → Voltage Divider Input

VOLTAGE DIVIDER:
MQ135 AOUT ──[10kΩ R1]─┬─[10kΩ R2]─ GND
                      │
                      └─ ESP32 GPIO 34 (ADC1_CH6)

ESP32 NODEMCU:
GPIO 34 → Voltage Divider Output (0-2.5V safe)
GND     → Common Ground
3.3V    → Not used (MQ135 powered by 5V)
```

**⚠️ WARNING:** The voltage divider is MANDATORY! MQ135 outputs 0-5V, but ESP32 ADC pins only accept 0-3.3V. Direct connection will damage the ESP32.

### Components Needed

- MQ135 Sensor Module
- ESP32 NodeMCU
- 2 × 10kΩ resistors (1/4W)
- Breadboard
- Jumper wires
- 5V power supply (500mA minimum)

## 📊 Sensor Readings

The code outputs the following data every 2 seconds:

```
SENSOR READINGS:
  ADC Value: 2048
  Voltage: 2.50 V
  Rs: 10000.00 Ω
  Rs/R0: 0.50
  CO2: 450.00 ppm
  NH3: 450.00 ppm
  Uptime: 10 seconds

MEAT QUALITY ASSESSMENT:
  Status: FRESH
  CO2 Level: Normal
========================================
```

## 🔧 Calibration

1. Open [`main.cpp`](main.cpp)
2. Set calibration mode to `true`:
   ```cpp
   bool calibrationMode = true;
   ```
3. Upload code to ESP32
4. Place sensor in clean air (outdoor or well-ventilated area)
5. Wait 5 minutes for stabilization
6. Open Serial Monitor at 115200 baud
7. Note the R0 value printed during calibration
8. Update the R0 constant in code:
   ```cpp
   const float R0 = [YOUR_MEASURED_VALUE];  // Replace with actual value
   ```
9. Set calibration mode to `false`:
   ```cpp
   bool calibrationMode = false;
   ```
10. Re-upload code for normal operation

**Typical R0 values:** 10kΩ - 100kΩ (varies by sensor)

## 📈 Meat Quality Reference

| CO2 (ppm) | Status | Action |
|-----------|--------|--------|
| 400-600 | FRESH | Safe to consume |
| 600-800 | GOOD | Monitor closely |
| 800-1000 | MODERATE | Consume soon |
| >1000 | SPOILED | Do not consume |

## ⏱️ Preheating Requirements

For accurate readings, the MQ135 sensor requires preheating:

| Time | Accuracy | Notes |
|------|----------|-------|
| 5 minutes | ~60% | Quick readings, not accurate |
| 1 hour | ~80% | Acceptable for monitoring |
| 24 hours | ~95% | Recommended for accuracy |
| 48 hours | ~100% | Full accuracy achieved |

**Best Practice:** Preheat sensor for 24-48 hours before critical measurements.

## 🔌 Pin Selection

### Safe ADC1 Pins (Works with WiFi)

| GPIO | ADC Channel | Notes |
|------|------------|-------|
| 34 | ADC1_CH6 | **RECOMMENDED** (used in this code) |
| 35 | ADC1_CH7 | Input only |
| 36 | ADC1_CH0 | Input only |
| 39 | ADC1_CH3 | Input only |

**⚠️ AVOID:** GPIO 32, 33 (ADC2) - These conflict with WiFi!

## 🛡️ Safety Checklist

Before powering on, verify:

- [ ] Voltage divider installed (2x 10kΩ resistors)
- [ ] Using ADC1 pin (GPIO 34, 35, 36, or 39)
- [ ] Common ground established
- [ ] MQ135 powered by 5V
- [ ] NO direct 5V connection to ESP32 GPIO
- [ ] All connections secure
- [ ] Code uploaded and verified

## 🔍 Troubleshooting

### Problem: Readings always 0

**Possible Causes:**
- Loose connections
- Wrong GPIO pin used
- ADC2 pin used instead of ADC1
- MQ135 not powered (check 5V supply)

**Solution:**
- Verify all connections
- Use GPIO 34, 35, 36, or 39
- Check MQ135 VCC has 5V

### Problem: Erratic readings

**Possible Causes:**
- Sensor not preheated
- Voltage divider not connected properly
- Power supply noise
- Poor ground connection

**Solution:**
- Preheat sensor for 24 hours
- Check voltage divider connections
- Use stable power supply
- Ensure common ground

### Problem: Readings always maximum

**Possible Causes:**
- Voltage divider not installed
- Direct 5V connection to ESP32 (DAMAGE RISK!)
- Wrong resistor values

**Solution:**
- Install voltage divider immediately
- Check ESP32 not damaged
- Use 10kΩ resistors

### Problem: ESP32 gets hot

**Possible Causes:**
- 5V connected to GPIO pin directly
- Short circuit
- Overvoltage on ADC pin

**Solution:**
- Disconnect power immediately
- Check for short circuits
- Verify voltage divider is installed

## 📚 Additional Documentation

For more detailed information, see:
- [MQ135 Wiring Guide](../docs/MQ135_WIRING_GUIDE.md)
- [MQ135 Quick Reference](../docs/MQ135_QUICK_REFERENCE.txt)
- [MQ135 README](../docs/README_MQ135.md)

## 🔗 Integration with Main Project

To integrate MQ135 readings with the main MQTT project:

1. Copy the `readMQ135()` function from [`main.cpp`](main.cpp)
2. Add to your main project's [`src/main.cpp`](../src/main.cpp)
3. Ensure voltage divider is properly installed
4. Calibrate sensor before use
5. Add MQTT publishing in your main loop

## 📝 Code Structure

```cpp
// Main functions:
- setup()          // Initialize serial, ADC, calibration
- loop()           // Read sensor at intervals, print data
- readMQ135()      // Read sensor and calculate CO2 PPM
- calculateRS()    // Calculate sensor resistance
- calculatePPM()   // Convert resistance to PPM
- calibrateSensor() // Calibrate sensor in clean air
- printSensorData() // Print readings to Serial Monitor
```

## 📄 License

This code is part of the Meat Quality Air Data project.

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Platform:** ESP32 NodeMCU  
**Framework:** Arduino (PlatformIO)  
