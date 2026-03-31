# How to Upload MQ135 Sensor Code

## ⚠️ IMPORTANT: You Must Use the Correct Method!

The MQ135 sensor code is in a **separate project folder** (`src_mq135/`). If you use VSCode's normal upload button, it will upload the old code from the main project (`src/main.cpp`).

## 🎯 Method 1: Using Batch Script (RECOMMENDED)

This is the easiest and most reliable method.

### Step 1: Run the Build Script
Open a terminal/command prompt in the project root directory and run:
```batch
build_mq135.bat
```

This will:
1. Clean previous build
2. Build the MQ135 sensor code
3. Upload to ESP32 NodeMCU

### Step 2: Monitor Serial Output
After upload completes, run:
```batch
monitor_mq135.bat
```

This will open the serial monitor at 115200 baud.

---

## 🎯 Method 2: Using Command Line

If the batch script doesn't work, use these manual commands:

### Step 1: Navigate to MQ135 Project Directory
```bash
cd src_mq135
```

### Step 2: Build the Code
```bash
pio run
```

### Step 3: Upload to ESP32
```bash
pio run --target upload
```

### Step 4: Monitor Serial Output
```bash
pio device monitor -b 115200
```

---

## 🎯 Method 3: Using VSCode (Advanced)

If you want to use VSCode PlatformIO extension:

### Option A: Open MQ135 Project as Separate Workspace
1. Close VSCode
2. Open VSCode
3. File → Open Folder
4. Select the `src_mq135/` folder (NOT the root project)
5. Now use the PlatformIO upload button
6. This will upload the MQ135 code

### Option B: Use VSCode Terminal
1. Keep the root project open in VSCode
2. Open terminal: `Ctrl + ~` (tilde key)
3. Run these commands:
   ```bash
   cd src_mq135
   pio run --target upload
   ```
4. Then open serial monitor:
   ```bash
   pio device monitor -b 115200
   ```

---

## ❌ What NOT To Do

### ❌ DON'T Use VSCode PlatformIO Upload Button (Root Project)
If you have the root project (`meat_quality_Air_data`) open in VSCode and click the PlatformIO upload button, it will upload the OLD code from `src/main.cpp`, NOT the MQ135 code!

### ❌ DON'T Run `build.bat` or `upload.bat`
These scripts are for the main MQTT project, not the MQ135 sensor project.

### ❌ DON'T Run `pio run --target upload` from Root Directory
If you run this from the project root, it will upload the main project code, not the MQ135 code.

---

## ✅ How to Verify You're Uploading the Right Code

### Check 1: Look at Build Output
When building, you should see:
```
Compiling .pio\build\esp32dev\src\main.cpp.o
```
NOT:
```
Compiling .pio\build\esp32dev\src\mq135_sensor.cpp.o
```

### Check 2: Look at Working Directory
The build script should show:
```
Working directory: d:\projects\meat_quality_Air_data\src_mq135
```

### Check 3: Check Serial Monitor Output
After upload, the serial monitor should show:
```
========================================
MQ135 Air Quality Sensor - ESP32 NodeMCU
========================================

CIRCUIT WIRING:
MQ135 VCC  → 5V
MQ135 GND  → GND
...
```

NOT:
```
Connecting to WiFi...
MQTT connected...
```

---

## 🔧 Troubleshooting

### Problem: "Old code keeps uploading"

**Cause:** You're uploading from the wrong directory or using the wrong script.

**Solution:**
1. Make sure you're running `build_mq135.bat` (NOT `build.bat`)
2. Make sure you're in the project root directory when running the script
3. Check the working directory in the build output - it should be `src_mq135`

### Problem: "pio is not recognized"

**Cause:** PlatformIO is not in your system PATH.

**Solution:**
1. Use VSCode PlatformIO extension
2. Open VSCode terminal and run:
   ```bash
   cd src_mq135
   pio run --target upload
   ```

### Problem: "Cannot find src_mq135 directory"

**Cause:** The script is not in the correct location.

**Solution:**
1. Make sure `build_mq135.bat` is in the project root directory
2. Make sure `src_mq135/` folder exists in the project root

### Problem: "Upload failed"

**Cause:** ESP32 not connected or wrong COM port.

**Solution:**
1. Check ESP32 is connected via USB
2. Check COM port in `src_mq135/platformio.ini` (currently COM7)
3. Put ESP32 in bootloader mode (press BOOT button)
4. Try different USB cable (some cables are power-only)

---

## 📋 Quick Reference

| Task | Command | Directory |
|------|---------|-----------|
| Build MQ135 | `pio run` | `src_mq135/` |
| Upload MQ135 | `pio run --target upload` | `src_mq135/` |
| Monitor MQ135 | `pio device monitor -b 115200` | `src_mq135/` |
| Build + Upload MQ135 | `build_mq135.bat` | Project root |
| Monitor MQ135 | `monitor_mq135.bat` | Project root |

---

## 🎯 Recommended Workflow

1. **Open terminal** in project root directory
2. **Run:** `build_mq135.bat`
3. **Wait** for upload to complete
4. **Run:** `monitor_mq135.bat`
5. **Verify** you see MQ135 sensor readings
6. **Calibrate** sensor in clean air (if needed)

---

## 📞 Still Having Issues?

If you're still uploading the wrong code:

1. **Check which directory you're in:**
   ```bash
   cd
   ```
   Should show: `d:\projects\meat_quality_Air_data`

2. **Check the script exists:**
   ```bash
   dir build_mq135.bat
   ```
   Should show the file exists

3. **Check the MQ135 folder exists:**
   ```bash
   dir src_mq135
   ```
   Should show `main.cpp` and `platformio.ini`

4. **Try manual command:**
   ```bash
   cd src_mq135
   pio run --target upload
   ```

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Status:** ✅ Ready to Use
