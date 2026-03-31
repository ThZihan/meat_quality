# MQ137 Ammonia Sensor - Complete Setup Summary

## ✅ MQ137 Sensor Project Created

A complete standalone project for testing **MQ137 ammonia sensor** with ESP32 NodeMCU has been created, similar to the MQ135 setup.

## 📁 Files Created

### Project Files:
- [`src_mq137/src/main.cpp`](../src_mq137/src/main.cpp) - MQ137 sensor code
- [`src_mq137/platformio.ini`](../src_mq137/platformio.ini) - PlatformIO configuration
- [`src_mq137/README.md`](../src_mq137/README.md) - Standalone project documentation

### Upload Scripts:
- [`upload_mq137.ps1`](../upload_mq137.ps1) - PowerShell upload script
- [`monitor_mq137.ps1`](../monitor_mq137.ps1) - PowerShell monitor script

### Documentation:
- [`docs/MQ137_WIRING_GUIDE.md`](./MQ137_WIRING_GUIDE.md) - Comprehensive wiring guide
- [`docs/MQ137_QUICK_REFERENCE.txt`](./MQ137_QUICK_REFERENCE.txt) - ASCII diagram reference
- [`docs/MQ137_VSCODE_GUIDE.md`](./MQ137_VSCODE_GUIDE.md) - VSCode PlatformIO guide

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

## 🚀 How to Upload MQ137 Code

### Method 1: Using VSCode PlatformIO (Recommended)

1. **Open MQ137 file:** Open **`src_mq137/src/main.cpp`** in VSCode
2. **Upload:** Click → ⬇ Upload button in PlatformIO toolbar
3. **Monitor:** Click → 🔌 Monitor button (set baud rate to 115200)

### Method 2: Using PowerShell Script

From project root directory, run:

```powershell
.\upload_mq137.ps1
```

### Method 3: Using Command Line

```bash
cd src_mq137
pio run --target upload
pio device monitor -b 115200
```

## ⚡ Circuit Wiring (Voltage Divider with 10kΩ Resistors)

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

## 📊 Expected Output After Upload

```
========================================
MQ137 Ammonia Sensor - ESP32 NodeMCU
========================================

CIRCUIT WIRING:
MQ137 VCC  → 5V
MQ137 GND  → GND
MQ137 AOUT → Voltage Divider (2x 10kΩ)
              └─ ESP32 GPIO 35 (ADC1_CH7)

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

## 🔧 Calibration Steps

1. Set `calibrationMode = true` in [`src_mq137/src/main.cpp`](../src_mq137/src/main.cpp)
2. Upload code
3. Place sensor in clean air (outdoor)
4. Wait 5 minutes
5. Note R0 value from Serial Monitor
6. Update R0 constant in code
7. Set `calibrationMode = false`
8. Re-upload

**Typical R0:** 10kΩ - 100kΩ (varies by sensor)

## 📈 Meat Quality Reference (Based on NH3)

| NH3 (ppm) | Meat Quality | Action |
|-----------|--------------|--------|
| 10-50 | Fresh | Safe to consume |
| 50-100 | Good | Monitor closely |
| 100-200 | Moderate | Consume soon |
| >200 | Spoiled | Do not consume |

## ❌ Common Mistakes to Avoid

❌ **DON'T** use VSCode PlatformIO upload button (uploads main project, not MQ137)
❌ **DON'T** run `build.bat` or `upload.bat` (these are for main MQTT project)
❌ **DON'T** run `pio run --target upload` from root directory

✅ **DO** open `src_mq137/src/main.cpp` in VSCode first
✅ **DO** run `.\upload_mq137.ps1` from project root
✅ **DO** run `pio run --target upload` from `src_mq137` directory

## 📋 Quick Reference

| Task | Command | Directory |
|------|---------|-----------|
| Upload MQ137 | `.\upload_mq137.ps1` | Project root |
| Monitor MQ137 | `.\monitor_mq137.ps1` | Project root |
| Manual upload | `pio run --target upload` | `src_mq137/` |
| Manual monitor | `pio device monitor -b 115200` | `src_mq137/` |

## 📚 Documentation

- [`docs/MQ137_VSCODE_GUIDE.md`](./MQ137_VSCODE_GUIDE.md) - VSCode PlatformIO guide
- [`docs/MQ137_WIRING_GUIDE.md`](./MQ137_WIRING_GUIDE.md) - Comprehensive wiring guide
- [`docs/MQ137_QUICK_REFERENCE.txt`](./MQ137_QUICK_REFERENCE.txt) - ASCII diagram reference
- [`src_mq137/README.md`](../src_mq137/README.md) - Standalone project documentation
- [`README.md`](../README.md) - Updated with MQ137 section

## 🔗 Integration with Main Project

To add MQ137 functionality to the main MQTT project:

1. Copy the `readMQ137()` function from [`src_mq137/src/main.cpp`](../src_mq137/src/main.cpp)
2. Add to your main project's [`src/main.cpp`](../src/main.cpp)
3. Ensure voltage divider is properly installed
4. Calibrate sensor before use
5. Add MQTT publishing in your main loop:
   ```cpp
   float nh3PPM = readMQ137();
   // Publish to MQTT
   ```

## 📁 Complete Project Structure

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
├── src_mq137/               # MQ137 standalone project ⭐ NEW
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
│   ├── MQ137_WIRING_GUIDE.md    ⭐ NEW
│   ├── MQ137_QUICK_REFERENCE.txt  ⭐ NEW
│   └── MQ137_VSCODE_GUIDE.md      ⭐ NEW
│
├── upload_mq135.bat         # Upload script for MQ135
├── monitor_mq135.bat        # Monitor script for MQ135
├── upload_mq137.ps1         # Upload script for MQ137 ⭐ NEW
├── monitor_mq137.ps1        # Monitor script for MQ137 ⭐ NEW
├── build.bat                # Main project build
├── upload.bat               # Main project upload
└── platformio.ini           # Main project config
```

## ✅ Verification

To verify the setup works:

1. Run `.\upload_mq137.ps1` - Should build and upload successfully
2. Run `.\monitor_mq137.ps1` - Should see sensor readings
3. Verify readings change when exposed to different air quality

## 📞 Support

For issues or questions:
1. Check the [Wiring Guide](./MQ137_WIRING_GUIDE.md)
2. Review the [Quick Reference](./MQ137_QUICK_REFERENCE.txt)
3. Verify connections against the safety checklist
4. Check Serial Monitor for error messages

## 🎯 Recommended Workflow

1. **Open MQ137 file:** Open **`src_mq137/src/main.cpp`** in VSCode
2. **Upload:** Click → ⬇ Upload button in PlatformIO toolbar
3. **Wait:** Wait for upload to complete
4. **Monitor:** Click → 🔌 Monitor button in PlatformIO toolbar
5. **Verify:** Check that you see MQ137 sensor readings
6. **Calibrate:** Follow calibration steps in [`src_mq137/README.md`](../src_mq137/README.md)

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Status:** ✅ Ready to Use
