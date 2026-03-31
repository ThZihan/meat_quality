# MQ135 Sensor Fix - Multiple Definition Error

## Problem

The build failed with a "multiple definition" error because both [`src/main.cpp`](../src/main.cpp) and [`src/mq135_sensor.cpp`](../src/mq135_sensor.cpp) contained `setup()` and `loop()` functions. In Arduino/PlatformIO, you can only have one `setup()` and one `loop()` function per project.

## Solution

Created a separate standalone project for the MQ135 sensor in the `src_mq135/` directory. This allows you to test the MQ135 sensor independently without conflicts with the main MQTT project.

## 📁 New Project Structure

```
meat_quality_Air_data/
├── src/                      # Main MQTT project
│   ├── main.cpp             # Main project with WiFi, MQTT, AHT10, MQ sensors
│   └── (other files)
│
├── src_mq135/               # MQ135 standalone project
│   ├── main.cpp             # MQ135 sensor code (moved from src/mq135_sensor.cpp)
│   ├── platformio.ini       # PlatformIO configuration for MQ135 project
│   └── README.md            # MQ135 project documentation
│
├── docs/                    # Documentation
│   ├── MQ135_WIRING_GUIDE.md
│   ├── MQ135_QUICK_REFERENCE.txt
│   ├── README_MQ135.md
│   └── MQ135_FIX_SUMMARY.md (this file)
│
├── build_mq135.bat          # Build/upload script for MQ135 project
├── monitor_mq135.bat        # Serial monitor script for MQ135 project
├── build.bat                # Build/upload script for main project
├── upload.bat               # Upload script for main project
└── platformio.ini           # PlatformIO configuration for main project
```

## 🚀 How to Use

### Option 1: Using Batch Scripts (Recommended)

**For MQ135 Sensor (Standalone):**
```batch
# Build and upload
build_mq135.bat

# Monitor serial output
monitor_mq135.bat
```

**For Main MQTT Project:**
```batch
# Build and upload
build.bat

# Monitor serial output
# Use VSCode Serial Monitor or: pio device monitor -b 115200
```

### Option 2: Using VSCode PlatformIO

**For MQ135 Sensor:**
1. Open `src_mq135/` folder in VSCode
2. Click the arrow icon in PlatformIO toolbar to upload
3. Click the plug icon to open serial monitor

**For Main Project:**
1. Open the root project folder in VSCode
2. Click the arrow icon in PlatformIO toolbar to upload
3. Click the plug icon to open serial monitor

### Option 3: Using Command Line

**For MQ135 Sensor:**
```bash
cd src_mq135
pio run                    # Build
pio run --target upload    # Upload
pio device monitor -b 115200  # Monitor
```

**For Main Project:**
```bash
pio run                    # Build
pio run --target upload    # Upload
pio device monitor -b 115200  # Monitor
```

## ⚡ Circuit Wiring (MQ135 Sensor)

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

**⚠️ CRITICAL:** The voltage divider is MANDATORY! MQ135 outputs 0-5V, but ESP32 ADC pins only accept 0-3.3V. Direct connection will damage the ESP32.

## 🔧 Calibration Steps

1. Open [`src_mq135/main.cpp`](../src_mq135/main.cpp)
2. Set `calibrationMode = true`
3. Upload code to ESP32
4. Place sensor in clean air (outdoor)
5. Wait 5 minutes for stabilization
6. Open Serial Monitor at 115200 baud
7. Note the R0 value printed
8. Update `R0` constant in code
9. Set `calibrationMode = false`
10. Re-upload code

**Typical R0 values:** 10kΩ - 100kΩ (varies by sensor)

## 📊 Expected Output

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

## 🔗 Integration with Main Project

To add MQ135 functionality to the main MQTT project:

1. Copy the `readMQ135()` function from [`src_mq135/main.cpp`](../src_mq135/main.cpp)
2. Add to [`src/main.cpp`](../src/main.cpp)
3. Ensure voltage divider is properly installed
4. Calibrate sensor before use
5. Add MQTT publishing in your main loop:
   ```cpp
   float co2PPM = readMQ135();
   // Publish to MQTT
   ```

## 📚 Documentation

- [MQ135 Wiring Guide](./MQ135_WIRING_GUIDE.md) - Comprehensive wiring instructions
- [MQ135 Quick Reference](./MQ135_QUICK_REFERENCE.txt) - ASCII diagram reference
- [MQ135 README](./README_MQ135.md) - Complete documentation
- [MQ135 Project README](../src_mq135/README.md) - Standalone project docs

## 🛡️ Safety Checklist

Before powering on MQ135 sensor:

- [ ] Voltage divider installed (2x 10kΩ resistors)
- [ ] Using ADC1 pin (GPIO 34, 35, 36, or 39)
- [ ] Common ground established
- [ ] MQ135 powered by 5V
- [ ] NO direct 5V connection to ESP32 GPIO
- [ ] All connections secure

## 🔍 Troubleshooting

### Build Errors

**Problem:** "pio is not recognized"
- **Solution:** Install PlatformIO or use VSCode PlatformIO extension

**Problem:** Multiple definition errors
- **Solution:** Use the correct project folder (src_mq135 for MQ135, root for main project)

### Runtime Errors

**Problem:** Readings always 0
- **Solution:** Check connections, verify GPIO pin, check 5V supply

**Problem:** Erratic readings
- **Solution:** Preheat sensor for 24 hours, check voltage divider

**Problem:** Readings always maximum
- **Solution:** Install voltage divider! Check resistors are 10kΩ

**Problem:** ESP32 gets hot
- **Solution:** Disconnect power! Check for 5V on GPIO pin

## 📝 Files Modified/Created

### Created:
- [`src_mq135/`](../src_mq135/) - New standalone project directory
- [`src_mq135/main.cpp`](../src_mq135/main.cpp) - MQ135 sensor code (moved)
- [`src_mq135/platformio.ini`](../src_mq135/platformio.ini) - PlatformIO config
- [`src_mq135/README.md`](../src_mq135/README.md) - Project documentation
- [`build_mq135.bat`](../build_mq135.bat) - Build/upload script
- [`monitor_mq135.bat`](../monitor_mq135.bat) - Serial monitor script
- [`docs/MQ135_FIX_SUMMARY.md`](./MQ135_FIX_SUMMARY.md) - This file

### Modified:
- [`docs/MQ135_WIRING_GUIDE.md`](./MQ135_WIRING_GUIDE.md) - Created earlier
- [`docs/MQ135_QUICK_REFERENCE.txt`](./MQ135_QUICK_REFERENCE.txt) - Created earlier
- [`docs/README_MQ135.md`](./README_MQ135.md) - Created earlier

### Moved:
- [`src/mq135_sensor.cpp`](../src/mq135_sensor.cpp) → [`src_mq135/main.cpp`](../src_mq135/main.cpp)

## ✅ Verification

To verify the fix works:

1. Run `build_mq135.bat` - Should build successfully without errors
2. Upload to ESP32
3. Run `monitor_mq135.bat` - Should see sensor readings
4. Verify readings change when exposed to different air quality

## 📞 Support

For issues or questions:
1. Check the [Wiring Guide](./MQ135_WIRING_GUIDE.md)
2. Review the [Quick Reference](./MQ135_QUICK_REFERENCE.txt)
3. Verify connections against the safety checklist
4. Check Serial Monitor for error messages

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Status:** ✅ Fixed and Ready to Use
