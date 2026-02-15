# MQ137 Ammonia Sensor - ESP32 NodeMCU

This is a standalone project for testing the MQ137 ammonia sensor with ESP32 NodeMCU.

## 📁 Files Included

| File | Description |
|------|-------------|
| [`src/main.cpp`](src/main.cpp) | MQ137 sensor code |
| [`platformio.ini`](platformio.ini) | PlatformIO configuration |
| [`README.md`](README.md) | This file |

## 🌟 What is MQ137?

The **MQ137** is a gas sensor specifically designed for **ammonia (NH3)** detection. It's particularly useful for meat quality monitoring because:

- **Ammonia increases** when meat spoils (protein breakdown)
- **NH3 detection range:** 10-500 ppm
- **Fresh meat:** NH3 10-50 ppm
- **Spoiling meat:** NH3 > 100 ppm

### MQ137 vs MQ135

| Sensor | Primary Gas | Best For |
|--------|--------------|-----------|
| **MQ135** | CO2, VOCs | General air quality, CO2 monitoring |
| **MQ137** | NH3 (Ammonia) | Meat spoilage detection, protein breakdown |

**Using both sensors provides comprehensive air quality monitoring!**

## 🚀 Quick Start

### Build and Upload

**Option 1: Using VSCode PlatformIO (Recommended)**
1. Open [`src/main.cpp`](src/main.cpp) in VSCode
2. Click the ⬇ Upload button in PlatformIO toolbar
3. Click the 🔌 Monitor button (set baud rate to 115200)

**Option 2: Using Command Line**
```bash
cd src_mq137
pio run                    # Build
pio run --target upload    # Upload
pio device monitor -b 115200  # Monitor
```

## ⚡ Circuit Wiring

### Voltage Divider (CRITICAL!)

```
MQ137 MODULE:
VCC  → 5V (external power supply)
GND  → GND (common ground)
AOUT → Voltage Divider Input

VOLTAGE DIVIDER:
MQ137 AOUT ──[10kΩ R1]─┬─[10kΩ R2]─ GND
                      │
                      └─ ESP32 GPIO 35 (ADC1_CH7)

ESP32 NODEMCU:
GPIO 35 → Voltage Divider Output (0-2.5V safe)
GND     → Common Ground
3.3V    → Not used (MQ137 powered by 5V)
```

**⚠️ CRITICAL:** The voltage divider is MANDATORY! MQ137 outputs 0-5V, but ESP32 ADC pins only accept 0-3.3V. Direct connection will damage the ESP32.

### Components Needed

- MQ137 Sensor Module
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
  NH3: 45.00 ppm
  Uptime: 10 seconds

MEAT QUALITY ASSESSMENT (Based on NH3):
  Status: FRESH
  NH3 Level: Normal
========================================
```

## 🔧 Calibration

1. Open [`src/main.cpp`](src/main.cpp)
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

| NH3 (ppm) | Meat Quality | Action |
|-----------|--------------|--------|
| 10-50 | Fresh | Safe to consume |
| 50-100 | Good | Monitor closely |
| 100-200 | Moderate | Consume soon |
| >200 | Spoiled | Do not consume |

## ⏱️ Preheating Requirements

For accurate readings, the MQ137 sensor requires preheating:

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
| 34 | ADC1_CH6 | Input only |
| 35 | ADC1_CH7 | **RECOMMENDED** (used in this code) |
| 36 | ADC1_CH0 | Input only |
| 39 | ADC1_CH3 | Input only |

**⚠️ AVOID:** GPIO 32, 33 (ADC2) - These conflict with WiFi!

## 🛡️ Safety Checklist

Before powering on, verify:

- [ ] Voltage divider installed (2x 10kΩ resistors)
- [ ] Using ADC1 pin (GPIO 34, 35, 36, or 39)
- [ ] Common ground established
- [ ] MQ137 powered by 5V
- [ ] NO direct 5V connection to ESP32 GPIO
- [ ] All connections secure
- [ ] Code uploaded and verified

## 🔍 Troubleshooting

### Problem: Readings always 0

**Possible Causes:**
- Loose connections
- Wrong GPIO pin used
- ADC2 pin used instead of ADC1
- MQ137 not powered (check 5V supply)

**Solution:**
- Verify all connections
- Use GPIO 34, 35, 36, or 39
- Check MQ137 VCC has 5V

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

## 🔗 Integration with Main Project

To add MQ137 functionality to the main MQTT project:

1. Copy the `readMQ137()` function from [`src/main.cpp`](src/main.cpp)
2. Add to your main project's [`src/main.cpp`](../src/main.cpp)
3. Ensure voltage divider is properly installed
4. Calibrate sensor before use
5. Add MQTT publishing in your main loop:
   ```cpp
   float nh3PPM = readMQ137();
   // Publish to MQTT
   ```

## 📝 Code Structure

```cpp
// Main functions:
- setup()          // Initialize serial, ADC, calibration
- loop()           // Read sensor at intervals, print data
- readMQ137()      // Read sensor and calculate NH3 PPM
- calculateRS()    // Calculate sensor resistance
- calculatePPM()   // Convert resistance to PPM
- calibrateSensor() // Calibrate sensor in clean air
- printSensorData() // Print readings to Serial Monitor
```

## 📈 Performance Characteristics

| Parameter | Value | Notes |
|-----------|-------|-------|
| Operating Voltage | 5V | MQ137 heater requirement |
| ADC Input Range | 0-2.5V | After voltage divider |
| ADC Resolution | 12-bit (0-4095) | ESP32 native resolution |
| Read Interval | 2 seconds | Configurable |
| Preheat Time | 24-48 hours | For full accuracy |
| Measurement Range | NH3: 10-500 ppm | Approximate |

## 🎯 Use Cases

- Meat quality monitoring (spoilage detection)
- Ammonia leak detection
- Food storage monitoring
- Environmental monitoring
- Industrial safety

## 📚 Additional Documentation

For more information, see:
- [MQ137 Datasheet](https://www.sparkfun.com/datasheets/Sensors/Biometric/MQ-137.pdf)
- [ESP32 ADC Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/adc.html)
- [PlatformIO Documentation](https://docs.platformio.org/)

## 📞 Support

For issues or questions:
1. Check the circuit wiring diagram
2. Verify connections against the safety checklist
3. Check Serial Monitor for error messages
4. Ensure sensor is properly calibrated

## 📄 License

This code is part of the Meat Quality Air Data project.

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Platform:** ESP32 NodeMCU  
**Framework:** Arduino (PlatformIO)  
