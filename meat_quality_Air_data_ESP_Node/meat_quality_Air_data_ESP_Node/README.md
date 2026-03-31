# Meat Quality Air Data - ESP32 NodeMCU Project

## ⚠️ CRITICAL ISSUE: Path Problem

Your project is located in a path with spaces and special characters:
```
c:/Users/tahfi/OneDrive - Independent University, Bangladesh/Documents/Arduino/meat_quality_Air_data
```

**This is causing linker errors!** The ESP32 toolchain cannot handle paths with:
- Spaces
- Special characters (commas, hyphens, etc.)
- Long path names

## 🔧 SOLUTION: Move Project to Simple Path

### Option 1: Move to C:\ (Recommended)

1. Create a new folder: `C:\Projects\meat_quality_Air_data`
2. Copy all project files to the new location
3. Open VS Code and select the new folder
4. Build and upload should work!

### Option 2: Use Short Path Name (8.3 format)

Windows has a built-in short path feature. Try using:
```
C:\Users\tahfi\OneDriv~1\Arduino\meat_q~1
```

### Option 3: Create Symbolic Link

```cmd
mklink /D C:\ESP32_Project "c:\Users\tahfi\OneDrive - Independent University, Bangladesh\Documents\Arduino\meat_quality_Air_data"
```

Then work from `C:\ESP32_Project`

---

## Quick Start (After Moving Project)

### 1. Build and Upload

```bash
# Build the project
pio run

# Upload to ESP32 (COM6)
pio run --target upload

# Or build and upload in one command
pio run --target upload
```

### 2. Monitor Serial Output

```bash
pio device monitor
```

### 3. Configure WiFi

Edit [`src/main.cpp`](src/main.cpp:30) and replace:
```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
```

With your actual WiFi credentials.

---

## Project Files

| File | Description |
|------|-------------|
| [`src/main.cpp`](src/main.cpp:1) | Main code - LED blink + WiFi test |
| [`platformio.ini`](platformio.ini:1) | ESP32 configuration |
| [`.vscode/tasks.json`](.vscode/tasks.json:1) | VS Code tasks (not used for ESP32) |
| [`.vscode/launch.json`](.vscode/launch.json:1) | Debug config (not used for ESP32) |
| [`.gitignore`](.gitignore:1) | Git ignore patterns |

---

## Hardware Specifications

| Feature | Specification |
|---------|---------------|
| Processor | Xtensa LX6 dual-core @ 240MHz |
| Flash Memory | 4 MB |
| SRAM | 520 KB |
| WiFi | 802.11 b/g/n (2.4 GHz) |
| Bluetooth | Classic + BLE |
| Built-in LED | GPIO 2 (Blue LED) |

---

## Test Code Features

The [`src/main.cpp`](src/main.cpp:1) test program includes:

- ✅ **LED Blink Test** - Built-in LED toggles every 1 second
- ✅ **WiFi Connection Test** - Connects to WiFi and displays IP address
- ✅ **Serial Debug Output** - Shows LED state and WiFi status at 115200 baud
- ✅ **Non-blocking Timing** - Uses `millis()` instead of `delay()`

---

## Expected Serial Output

```
========================================
ESP32 NodeMCU - Test Program
========================================

Testing WiFi connection...
Connecting to YourWiFiName
....
WiFi connected!
IP Address: 192.168.1.100
MAC Address: AA:BB:CC:DD:EE:FF
Signal Strength (RSSI): -45 dBm

========================================
Setup complete. LED blinking started...
========================================

[1s] LED State: ON
    WiFi: Connected (192.168.1.100)
[2s] LED State: OFF
    WiFi: Connected (192.168.1.100)
[3s] LED State: ON
    WiFi: Connected (192.168.1.100)
...
```

---

## PlatformIO Configuration

[`platformio.ini`](platformio.ini:1) settings:

| Setting | Value |
|---------|-------|
| Platform | `espressif32` |
| Board | `nodemcu-32s` (ESP32 NodeMCU) |
| Framework | `arduino` |
| Serial Speed | 115200 baud |
| Upload Port | COM6 |
| Upload Speed | 921600 |

---

## Next Steps for Meat Quality Air Data

Once your ESP32 is tested and working, you can add:

### Sensors
- **DHT22/DHT11** - Temperature and humidity
- **MQ-135** - Air quality (CO2, NH3, alcohol, smoke)
- **BME280/BMP280** - Pressure and humidity
- **SGP30** - TVOC and CO2 eCO2

### Data Storage
- **SD Card Module** - Local data logging
- **SPIFFS/LittleFS** - Internal flash storage

### Data Transmission
- **MQTT** - Real-time data to IoT platform
- **HTTP/HTTPS** - REST API endpoints
- **Web Server** - Built-in web interface

### Display
- **OLED (SSD1306)** - Real-time data display
- **TFT LCD** - Color display with graphs

---

## Common Issues

**Upload fails / "A fatal error occurred: Failed to connect to ESP32"**
- Press and hold the **BOOT** button while uploading
- Check USB cable (use data cable, not charging-only)
- Verify COM port in [`platformio.ini`](platformio.ini:17)

**WiFi connection fails**
- Verify WiFi credentials in [`src/main.cpp`](src/main.cpp:30)
- Check if 2.4 GHz network (ESP32 doesn't support 5 GHz)
- Move ESP32 closer to router

**Linker error about firmware.map**
- **This is the path issue!** Move project to simple path (see above)

**Serial monitor shows garbage**
- Check baud rate is 115200
- Try different USB cable

---

## PlatformIO Commands Reference

```bash
# Build
pio run

# Upload
pio run --target upload

# Clean build
pio run --target clean

# Monitor serial
pio device monitor

# Upload and monitor
pio run --target upload && pio device monitor

# Install library
pio lib install "library name"

# Update platform
pio platform update
```

---

## Library Dependencies

To add libraries, uncomment and edit the `lib_deps` section in [`platformio.ini`](platformio.ini:23):

```ini
lib_deps =
    bblanchon/ArduinoJson@^6.21.0
    adafruit/Adafruit Unified Sensor
    adafruit/DHT sensor library
    bblanchon/ESP32Servo
    adafruit/Adafruit SSD1306
```

---

## ESP32 Pin Reference

| Pin | Function | Notes |
|-----|---------|-------|
| GPIO 2 | Built-in LED | Blue LED (active LOW) |
| GPIO 0 | BOOT button | Press to enter upload mode |
| GPIO 4, 5 | I2C SDA, SCL | Default I2C pins |
| GPIO 16, 17 | UART2 RX, TX | Alternative serial |
| GPIO 18-23 | SPI | Default SPI pins |

⚠️ **Warning:** GPIO 6-11 are used for flash memory - do not use these pins!

---

## Memory Considerations

ESP32 has:
- **520 KB SRAM** - Plenty for complex projects
- **4 MB Flash** - Use `F()` macro for strings to save RAM
- **SPIFFS/LittleFS** - Use for storing configuration and data

**Best Practices:**
- Use `const` instead of `#define`
- Use `F()` macro for Serial.print strings
- Avoid `String` class - use char arrays or String literals
- Use `millis()` instead of `delay()` in loops

---

## Troubleshooting Path Issues

If you're still having issues after moving the project:

1. **Check for hidden files:**
   ```cmd
   dir /a
   ```

2. **Verify no spaces in path:**
   ```cmd
   cd
   ```

3. **Use absolute path in terminal:**
   ```cmd
   cd C:\Projects\meat_quality_Air_data
   pio run
   ```

4. **Clear PlatformIO cache:**
   ```cmd
   rmdir /s /q .pio
   pio run
   ```

---

## 🌬️ MQ135 Air Quality Sensor (Standalone Project)

A standalone project for testing the MQ135 air quality sensor with ESP32 NodeMCU.

### ⚠️ IMPORTANT: Separate Project

The MQ135 sensor code is in a **separate project folder** (`src_mq135/`). This prevents conflicts with the main MQTT project.

### Quick Start

#### Option 1: Using Diagnostic Script (Recommended)
```batch
check_mq135_setup.bat
```
This will verify your setup and show you how to upload the MQ135 code.

#### Option 2: Using Upload Script
```batch
upload_mq135.bat
```
This will build and upload the MQ135 sensor code to your ESP32.

#### Option 3: Manual Commands
```bash
cd src_mq135
pio run --target upload
pio device monitor -b 115200
```

### ⚡ Circuit Wiring (Voltage Divider Required)

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

### Available Scripts

| Script | Purpose |
|--------|---------|
| [`check_mq135_setup.bat`](check_mq135_setup.bat) | Verify setup and diagnose issues |
| [`upload_mq135.bat`](upload_mq135.bat) | Simple upload for MQ135 code |
| [`build_mq135.bat`](build_mq135.bat) | Full build + upload for MQ135 |
| [`monitor_mq135.bat`](monitor_mq135.bat) | Open serial monitor for MQ135 |

### Documentation

- [`docs/MQ135_UPLOAD_GUIDE.md`](docs/MQ135_UPLOAD_GUIDE.md) - Detailed upload instructions
- [`docs/MQ135_WIRING_GUIDE.md`](docs/MQ135_WIRING_GUIDE.md) - Comprehensive wiring guide
- [`docs/MQ135_QUICK_REFERENCE.txt`](docs/MQ135_QUICK_REFERENCE.txt) - ASCII diagram reference
- [`docs/MQ135_FIX_SUMMARY.md`](docs/MQ135_FIX_SUMMARY.md) - Fix details and troubleshooting
- [`src_mq135/README.md`](src_mq135/README.md) - Standalone project documentation

### Common Mistakes to Avoid

❌ **DON'T** use VSCode PlatformIO upload button (uploads main project, not MQ135)
❌ **DON'T** run `build.bat` or `upload.bat` (these are for main MQTT project)
❌ **DON'T** run `pio run --target upload` from root directory

✅ **DO** run `upload_mq135.bat` from project root
✅ **DO** run `build_mq135.bat` from project root
✅ **DO** run `pio run --target upload` from `src_mq135` directory

### Calibration

1. Set `calibrationMode = true` in [`src_mq135/main.cpp`](src_mq135/main.cpp)
2. Upload code
3. Place sensor in clean air (outdoor)
4. Wait 5 minutes
5. Note R0 value from Serial Monitor
6. Update R0 constant in code
7. Set `calibrationMode = false`
8. Re-upload

**Typical R0:** 10kΩ - 100kΩ (varies by sensor)

### Expected Output

```
========================================
MQ135 Air Quality Sensor - ESP32 NodeMCU
========================================

CIRCUIT WIRING:
MQ135 VCC  → 5V
MQ135 GND  → GND
MQ135 AOUT → Voltage Divider (2x 10kΩ)
             └─ ESP32 GPIO 34 (ADC1_CH6)

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

### Integration with Main Project

To add MQ135 functionality to the main MQTT project:

1. Copy the `readMQ135()` function from [`src_mq135/main.cpp`](src_mq135/main.cpp)
2. Add to [`src/main.cpp`](src/main.cpp)
3. Ensure voltage divider is properly installed
4. Calibrate sensor before use
5. Add MQTT publishing in your main loop

---

## 🌟 MQ137 Ammonia Sensor (Standalone Project)

A standalone project for testing the **MQ137 ammonia sensor** with ESP32 NodeMCU. MQ137 is specifically designed for ammonia (NH3) detection, which is particularly useful for meat quality monitoring because ammonia increases when meat spoils.

### ⚠️ IMPORTANT: Separate Project

The MQ137 sensor code is in a **separate project folder** (`src_mq137/`). This prevents conflicts with the main MQTT project.

### Quick Start

#### Option 1: Using VSCode PlatformIO (Recommended)
1. Open **`src_mq137/src/main.cpp`** in VSCode
2. Click the ⬇ Upload button in PlatformIO toolbar
3. Click the 🔌 Monitor button (set baud rate to 115200)

#### Option 2: Using PowerShell Script
```powershell
.\upload_mq137.ps1
```
This will build and upload MQ137 sensor code to your ESP32.

#### Option 3: Manual Commands
```bash
cd src_mq137
pio run --target upload
pio device monitor -b 115200
```

### ⚡ Circuit Wiring (Voltage Divider Required)

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

### Available Scripts

| Script | Purpose |
|--------|---------|
| [`upload_mq137.ps1`](upload_mq137.ps1) | Simple upload for MQ137 code |
| [`monitor_mq137.ps1`](monitor_mq137.ps1) | Open serial monitor for MQ137 |

### Documentation

- [`docs/MQ137_VSCODE_GUIDE.md`](docs/MQ137_VSCODE_GUIDE.md) - VSCode PlatformIO guide
- [`docs/MQ137_WIRING_GUIDE.md`](docs/MQ137_WIRING_GUIDE.md) - Comprehensive wiring guide
- [`docs/MQ137_QUICK_REFERENCE.txt`](docs/MQ137_QUICK_REFERENCE.txt) - ASCII diagram reference
- [`src_mq137/README.md`](src_mq137/README.md) - Standalone project documentation

### Common Mistakes to Avoid

❌ **DON'T** use VSCode PlatformIO upload button (uploads main project, not MQ137)
❌ **DON'T** run `build.bat` or `upload.bat` (these are for main MQTT project)
❌ **DON'T** run `pio run --target upload` from root directory

✅ **DO** open `src_mq137/src/main.cpp` in VSCode first
✅ **DO** run `.\upload_mq137.ps1` from project root
✅ **DO** run `pio run --target upload` from `src_mq137` directory

### Calibration

1. Set `calibrationMode = true` in [`src_mq137/src/main.cpp`](src_mq137/src/main.cpp)
2. Upload code
3. Place sensor in clean air (outdoor)
4. Wait 5 minutes
5. Note R0 value from Serial Monitor
6. Update R0 constant in code
7. Set `calibrationMode = false`
8. Re-upload

**Typical R0:** 10kΩ - 100kΩ (varies by sensor)

### Expected Output

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

### Integration with Main Project

To add MQ137 functionality to the main MQTT project:

1. Copy the `readMQ137()` function from [`src_mq137/src/main.cpp`](src_mq137/src/main.cpp)
2. Add to [`src/main.cpp`](src/main.cpp)
3. Ensure voltage divider is properly installed
4. Calibrate sensor before use
5. Add MQTT publishing in your main loop

### MQ137 vs MQ135

| Sensor | Primary Gas | Best For |
|--------|--------------|-----------|
| **MQ135** | CO2, VOCs | General air quality, CO2 monitoring |
| **MQ137** | NH3 (Ammonia) | Meat spoilage detection, protein breakdown |

**Using both sensors provides comprehensive air quality monitoring!**

---

## 📁 Project Structure

```
meat_quality_Air_data/
├── src/                      # Main MQTT project
│   └── main.cpp             # WiFi, MQTT, AHT10, MQ sensors
│
├── src_mq135/               # MQ135 standalone project
│   ├── main.cpp             # MQ135 sensor code
│   ├── platformio.ini       # PlatformIO config
│   └── README.md            # MQ135 project docs
│
├── docs/                    # Documentation
│   ├── MQ135_WIRING_GUIDE.md
│   ├── MQ135_QUICK_REFERENCE.txt
│   ├── MQ135_UPLOAD_GUIDE.md
│   ├── MQ135_FIX_SUMMARY.md
│   └── README_MQ135.md
│
├── check_mq135_setup.bat    # Diagnostic tool
├── upload_mq135.bat         # Simple upload script
├── build_mq135.bat          # Full build+upload script
├── monitor_mq135.bat        # Serial monitor script
├── build.bat                # Main project build
├── upload.bat               # Main project upload
└── platformio.ini           # Main project config
```

---

## 🔗 Quick Reference

| Task | Command | Notes |
|------|---------|-------|
| **Main MQTT Project** |
| Build | `pio run` | From project root |
| Upload | `pio run --target upload` | From project root |
| Monitor | `pio device monitor -b 115200` | From project root |
| **MQ135 Sensor Project** |
| Check setup | `check_mq135_setup.bat` | From project root |
| Upload | `upload_mq135.bat` | From project root |
| Build+Upload | `build_mq135.bat` | From project root |
| Monitor | `monitor_mq135.bat` | From project root |
| Manual upload | `cd src_mq135 && pio run --target upload` | From project root |

---

## 📞 Support

For issues or questions:
- Main project: Check this README and [`README-MQTT.md`](README-MQTT.md)
- MQ135 sensor: Run [`check_mq135_setup.bat`](check_mq135_setup.bat) and see [`docs/MQ135_UPLOAD_GUIDE.md`](docs/MQ135_UPLOAD_GUIDE.md)
- General: Check Serial Monitor for error messages

---

**Version:** 2.0
**Date:** 2025-02-09
**Status:** ✅ Ready to Use
