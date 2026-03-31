# MQ135 Air Quality Sensor for ESP32 NodeMCU

## Overview

This implementation provides a complete solution for reading MQ135 air quality sensor data using ESP32 NodeMCU, with proper voltage divider circuitry to protect the ESP32 from the 5V sensor output.

## 📁 Files Included

| File | Description |
|------|-------------|
| [`src/mq135_sensor.cpp`](../src/mq135_sensor.cpp) | Main sensor reading code |
| [`docs/MQ135_WIRING_GUIDE.md`](./MQ135_WIRING_GUIDE.md) | Comprehensive wiring guide |
| [`docs/MQ135_QUICK_REFERENCE.txt`](./MQ135_QUICK_REFERENCE.txt) | Quick reference diagram |
| `build_mq135.bat` | Build and upload script |

## ⚡ Quick Start

### 1. Hardware Setup

**Components Required:**
- MQ135 Sensor Module
- ESP32 NodeMCU
- 2 × 10kΩ resistors (1/4W)
- Breadboard
- Jumper wires
- 5V power supply (500mA minimum)

**Circuit Connections:**
```
MQ135 VCC  → 5V
MQ135 GND  → GND
MQ135 AOUT → Voltage Divider (2x 10kΩ) → ESP32 GPIO 34
```

**Voltage Divider:**
```
MQ135 AOUT ──[10kΩ R1]─┬─[10kΩ R2]─ GND
                      │
                      └─ ESP32 GPIO 34 (ADC1_CH6)
```

**⚠️ CRITICAL:** The voltage divider is MANDATORY! MQ135 outputs 0-5V, but ESP32 ADC pins only accept 0-3.3V. Direct connection will damage the ESP32.

### 2. Build and Upload

**Option 1: Using the batch script (Windows)**
```batch
build_mq135.bat
```

**Option 2: Using PlatformIO commands**
```bash
# Build
pio run -e esp32dev

# Upload
pio run -e esp32dev --target upload

# Monitor serial output
pio device monitor -b 115200
```

### 3. Calibration

1. Open [`src/mq135_sensor.cpp`](../src/mq135_sensor.cpp)
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

## 📊 Sensor Readings

### Output Format

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

### Meat Quality Reference

| CO2 (ppm) | Meat Quality | Action |
|-----------|--------------|--------|
| 400-600 | Fresh | Safe to consume |
| 600-800 | Good | Monitor closely |
| 800-1000 | Moderate | Consume soon |
| >1000 | Spoiled | Do not consume |

## ⏱️ Preheating Requirements

For accurate readings, the MQ135 sensor requires preheating:

| Time | Accuracy | Notes |
|------|----------|-------|
| 5 minutes | ~60% | Quick readings, not accurate |
| 1 hour | ~80% | Acceptable for monitoring |
| 24 hours | ~95% | Recommended for accuracy |
| 48 hours | ~100% | Full accuracy achieved |

**Best Practice:** Preheat sensor for 24-48 hours before critical measurements.

## 🔧 Configuration

### Hardware Configuration

```cpp
const int MQ135_PIN = 34;  // ADC1_CH6 - Safe with WiFi enabled
const float VOLTAGE_DIVIDER_RATIO = 2.0;  // 5V → 2.5V (divide by 2)
const float ESP32_VREF = 3.3;  // ESP32 reference voltage
const int ADC_RESOLUTION = 4095;  // 12-bit ADC
```

### Sensor Parameters

```cpp
const float RL = 10000.0;  // Load resistor (10kΩ)
const float R0 = 20000.0;  // Sensor resistance in clean air (CALIBRATE!)
```

### Sensitivity Curve Parameters

```cpp
// CO2: Rs/R0 = 110.47 * (ppm)^-2.862
const float CO2_A = 110.47;
const float CO2_B = -2.862;

// NH3: Rs/R0 = 102.2 * (ppm)^-2.473
const float NH3_A = 102.2;
const float NH3_B = -2.473;
```

### Timing Configuration

```cpp
const unsigned long READ_INTERVAL = 2000;  // Read every 2 seconds
const unsigned long PREHEAT_TIME = 48000;  // 48 hours preheat
```

## 🔌 Pin Selection

### Safe ADC1 Pins (Works with WiFi)

| GPIO | ADC Channel | Notes |
|------|------------|-------|
| 34 | ADC1_CH6 | **RECOMMENDED** |
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

- [MQ135 Datasheet](https://www.olimex.com/Products/Components/Sensors/Sensors-MQ135/resources/MQ135.pdf)
- [ESP32 ADC Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/adc.html)
- [PlatformIO Documentation](https://docs.platformio.org/)

## 🔗 Integration with Main Project

To integrate MQ135 readings with your existing MQTT project:

1. Copy the `readMQ135()` function from [`mq135_sensor.cpp`](../src/mq135_sensor.cpp)
2. Add MQTT publishing in your main loop:
   ```cpp
   float co2PPM = readMQ135();
   publishMQTTData(co2PPM);
   ```
3. Ensure voltage divider is properly installed
4. Calibrate sensor before use

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

## 📈 Performance Characteristics

| Parameter | Value | Notes |
|-----------|-------|-------|
| Operating Voltage | 5V | MQ135 heater requirement |
| ADC Input Range | 0-2.5V | After voltage divider |
| ADC Resolution | 12-bit (0-4095) | ESP32 native resolution |
| Read Interval | 2 seconds | Configurable |
| Preheat Time | 24-48 hours | For full accuracy |
| Measurement Range | CO2: 400-5000 ppm | Approximate |

## 🎯 Use Cases

- Meat quality monitoring (freshness detection)
- Indoor air quality monitoring
- Gas leak detection (CO2, NH3, VOCs)
- Food storage monitoring
- Environmental monitoring

## 📞 Support

For issues or questions:
1. Check the [Wiring Guide](./MQ135_WIRING_GUIDE.md)
2. Review the [Quick Reference](./MQ135_QUICK_REFERENCE.txt)
3. Verify connections against the safety checklist
4. Check Serial Monitor for error messages

## 📄 License

This code is part of the Meat Quality Air Data project.

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Platform:** ESP32 NodeMCU  
**Framework:** Arduino (PlatformIO)  
