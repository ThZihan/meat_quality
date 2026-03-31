# MQ135 & MQ137 Sensors - Complete Guide

## 🌟 Overview

This project includes **two standalone sensor projects** for comprehensive air quality monitoring:

- **MQ135** - CO2 and VOCs detection (general air quality)
- **MQ137** - NH3 (Ammonia) detection (meat spoilage)

## 📊 Sensor Comparison

| Feature | MQ135 | MQ137 |
|---------|---------|---------|
| **Primary Gas** | CO2, VOCs | NH3 (Ammonia) |
| **Detection Range** | CO2: 400-5000 ppm | NH3: 10-500 ppm |
| **Best For** | General air quality | Meat spoilage detection |
| **GPIO Pin** | 34 (ADC1_CH6) | 35 (ADC1_CH7) |
| **Project Folder** | `src_mq135/` | `src_mq137/` |
| **Fresh Meat** | CO2: 400-600 ppm | NH3: 10-50 ppm |
| **Spoiled Meat** | CO2: >1000 ppm | NH3: >200 ppm |

**Using both sensors provides comprehensive air quality monitoring!**

## 🚀 Quick Start

### For MQ135 (CO2/VOCs)

1. **Open:** `src_mq135/src/main.cpp` in VSCode
2. **Upload:** Click → ⬇ Upload button in PlatformIO toolbar
3. **Monitor:** Click → 🔌 Monitor button (set baud rate to 115200)

### For MQ137 (Ammonia)

1. **Open:** `src_mq137/src/main.cpp` in VSCode
2. **Upload:** Click → ⬇ Upload button in PlatformIO toolbar
3. **Monitor:** Click → 🔌 Monitor button (set baud rate to 115200)

## ⚡ Circuit Wiring (Both Sensors)

### MQ135 Circuit (GPIO 34)

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

### MQ137 Circuit (GPIO 35)

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

**⚠️ CRITICAL:** Voltage dividers are MANDATORY for both sensors! Direct 5V connection will damage ESP32.

## 📁 Project Structure

```
meat_quality_Air_data/
├── src/                      # Main MQTT project
│   └── main.cpp             # WiFi, MQTT, AHT10, MQ sensors
│
├── src_mq135/               # MQ135 standalone project
│   ├── src/
│   │   └── main.cpp         # MQ135 sensor code
│   ├── platformio.ini       # PlatformIO config
│   └── README.md            # MQ135 project docs
│
├── src_mq137/               # MQ137 standalone project
│   ├── src/
│   │   └── main.cpp         # MQ137 sensor code
│   ├── platformio.ini       # PlatformIO config
│   └── README.md            # MQ137 project docs
│
├── docs/                    # Documentation
│   ├── MQ135_WIRING_GUIDE.md
│   ├── MQ135_QUICK_REFERENCE.txt
│   ├── MQ135_UPLOAD_GUIDE.md
│   ├── MQ135_FIX_SUMMARY.md
│   ├── MQ135_VSCODE_GUIDE.md
│   ├── MQ137_WIRING_GUIDE.md
│   ├── MQ137_QUICK_REFERENCE.txt
│   ├── MQ137_VSCODE_GUIDE.md
│   ├── MQ137_SUMMARY.md
│   └── BOTH_SENSORS_GUIDE.md (this file)
│
├── upload_mq135.bat         # Upload script for MQ135
├── monitor_mq135.bat        # Monitor script for MQ135
├── upload_mq137.ps1         # Upload script for MQ137
├── monitor_mq137.ps1        # Monitor script for MQ137
├── build.bat                # Main project build
├── upload.bat               # Main project upload
└── platformio.ini           # Main project config
```

## 📋 Quick Reference

| Task | MQ135 | MQ137 |
|------|---------|---------|
| **Open File** | `src_mq135/src/main.cpp` | `src_mq137/src/main.cpp` |
| **Upload (VSCode)** | Click ⬇ button | Click ⬇ button |
| **Upload (Script)** | `upload_mq135.bat` | `.\upload_mq137.ps1` |
| **Monitor (VSCode)** | Click 🔌 button | Click 🔌 button |
| **Monitor (Script)** | `monitor_mq135.bat` | `.\monitor_mq137.ps1` |
| **Manual Upload** | `cd src_mq135 && pio run --target upload` | `cd src_mq137 && pio run --target upload` |
| **Manual Monitor** | `pio device monitor -b 115200` | `pio device monitor -b 115200` |

## 📈 Meat Quality Assessment (Combined)

| CO2 (ppm) | NH3 (ppm) | Meat Quality | Action |
|-----------|-----------|--------------|--------|
| 400-600 | 10-50 | Fresh | Safe to consume |
| 600-800 | 50-100 | Good | Monitor closely |
| 800-1000 | 100-200 | Moderate | Consume soon |
| >1000 | >200 | Spoiled | Do not consume |

## 🔧 Calibration

### MQ135 Calibration

1. Set `calibrationMode = true` in `src_mq135/src/main.cpp`
2. Upload code
3. Place sensor in clean air (outdoor)
4. Wait 5 minutes
5. Note R0 value from Serial Monitor
6. Update R0 constant in code
7. Set `calibrationMode = false`
8. Re-upload

### MQ137 Calibration

1. Set `calibrationMode = true` in `src_mq137/src/main.cpp`
2. Upload code
3. Place sensor in clean air (outdoor)
4. Wait 5 minutes
5. Note R0 value from Serial Monitor
6. Update R0 constant in code
7. Set `calibrationMode = false`
8. Re-upload

**Typical R0 values:** 10kΩ - 100kΩ (varies by sensor)

## ❌ Common Mistakes to Avoid

### For Both Sensors:

❌ **DON'T** use VSCode PlatformIO upload button with root project open
❌ **DON'T** run `build.bat` or `upload.bat` (these are for main MQTT project)
❌ **DON'T** run `pio run --target upload` from root directory
❌ **DON'T** connect sensors directly to ESP32 without voltage dividers

### For MQ135:

✅ **DO** open `src_mq135/src/main.cpp` in VSCode first
✅ **DO** use GPIO 34 (ADC1_CH6)
✅ **DO** install voltage divider (2x 10kΩ resistors)

### For MQ137:

✅ **DO** open `src_mq137/src/main.cpp` in VSCode first
✅ **DO** use GPIO 35 (ADC1_CH7)
✅ **DO** install voltage divider (2x 10kΩ resistors)

## 📚 Documentation

### MQ135 Documentation:
- [`docs/MQ135_WIRING_GUIDE.md`](./MQ135_WIRING_GUIDE.md) - Comprehensive wiring guide
- [`docs/MQ135_QUICK_REFERENCE.txt`](./MQ135_QUICK_REFERENCE.txt) - ASCII diagram reference
- [`docs/MQ135_UPLOAD_GUIDE.md`](./MQ135_UPLOAD_GUIDE.md) - Detailed upload instructions
- [`docs/MQ135_VSCODE_GUIDE.md`](./MQ135_VSCODE_GUIDE.md) - VSCode PlatformIO guide
- [`docs/MQ135_FIX_SUMMARY.md`](./MQ135_FIX_SUMMARY.md) - Fix details and troubleshooting
- [`src_mq135/README.md`](../src_mq135/README.md) - Standalone project documentation

### MQ137 Documentation:
- [`docs/MQ137_WIRING_GUIDE.md`](./MQ137_WIRING_GUIDE.md) - Comprehensive wiring guide
- [`docs/MQ137_QUICK_REFERENCE.txt`](./MQ137_QUICK_REFERENCE.txt) - ASCII diagram reference
- [`docs/MQ137_VSCODE_GUIDE.md`](./MQ137_VSCODE_GUIDE.md) - VSCode PlatformIO guide
- [`docs/MQ137_SUMMARY.md`](./MQ137_SUMMARY.md) - Complete setup summary
- [`src_mq137/README.md`](../src_mq137/README.md) - Standalone project documentation

### General Documentation:
- [`README.md`](../README.md) - Main project documentation
- [`START_HERE.md`](../START_HERE.md) - Quick start guide

## 🔗 Integration with Main Project

To add both sensors to the main MQTT project:

1. **Copy functions** from each project:
   - `readMQ135()` from `src_mq135/src/main.cpp`
   - `readMQ137()` from `src_mq137/src/main.cpp`

2. **Add to main project:**
   - Add to `src/main.cpp`
   - Ensure voltage dividers are properly installed
   - Calibrate sensors before use

3. **Add MQTT publishing:**
   ```cpp
   float co2PPM = readMQ135();
   float nh3PPM = readMQ137();
   
   // Publish to MQTT
   publishMQTTData(co2PPM, nh3PPM);
   ```

## 🎯 Recommended Workflow

### Testing Sensors Individually:

1. **Test MQ135:**
   - Open `src_mq135/src/main.cpp`
   - Upload and monitor
   - Verify CO2 readings
   - Calibrate if needed

2. **Test MQ137:**
   - Open `src_mq137/src/main.cpp`
   - Upload and monitor
   - Verify NH3 readings
   - Calibrate if needed

### Integration:

3. **Integrate with Main Project:**
   - Copy functions to `src/main.cpp`
   - Add MQTT publishing
   - Test combined readings

## 📞 Support

For issues or questions:

### MQ135 Issues:
- Check [`docs/MQ135_WIRING_GUIDE.md`](./MQ135_WIRING_GUIDE.md)
- Check [`docs/MQ135_FIX_SUMMARY.md`](./MQ135_FIX_SUMMARY.md)
- Verify GPIO 34 connection
- Check voltage divider installation

### MQ137 Issues:
- Check [`docs/MQ137_WIRING_GUIDE.md`](./MQ137_WIRING_GUIDE.md)
- Check [`docs/MQ137_SUMMARY.md`](./MQ137_SUMMARY.md)
- Verify GPIO 35 connection
- Check voltage divider installation

### General Issues:
- Check Serial Monitor for error messages
- Verify ESP32 connection
- Check COM port settings

## ✅ Verification

To verify both sensors work:

1. **Test MQ135:**
   - Run `upload_mq135.bat`
   - Verify CO2 readings appear
   - Check calibration

2. **Test MQ137:**
   - Run `.\upload_mq137.ps1`
   - Verify NH3 readings appear
   - Check calibration

3. **Combined Test:**
   - Verify both sensors can be tested independently
   - Check that readings change with air quality
   - Confirm voltage dividers are working

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Status:** ✅ Ready to Use
