# How to Upload MQ135 Code Using VSCode PlatformIO

## ⚠️ IMPORTANT: PlatformIO (pio) Not in PATH

Since `pio` is not in your system PATH, you should use the **VSCode PlatformIO extension** instead. This is actually easier and more reliable!

---

## 🎯 Method 1: Using VSCode PlatformIO Extension (RECOMMENDED)

This is the easiest method since you already have VSCode installed.

### Step 1: Open the MQ135 Project File

1. In VSCode, open the file: [`src_mq135/main.cpp`](../src_mq135/main.cpp)
2. This will automatically set the PlatformIO context to the MQ135 project

### Step 2: Upload Using PlatformIO Toolbar

Look at the bottom of VSCode for the PlatformIO toolbar:

```
┌─────────────────────────────────────────────────────────────┐
│ [✓] [▶] [⬇] [🔌] [🔍] [📊] [⚙] [📝]              │
│  ✓  Build  ▶  Run  ⬇  Upload  🔌  Monitor  🔍  Test  │
└─────────────────────────────────────────────────────────────┘
```

Click the **⬇ Upload** button (down arrow icon).

### Step 3: Wait for Upload to Complete

You'll see the upload progress in the VSCode terminal at the bottom.

### Step 4: Open Serial Monitor

Click the **🔌 Monitor** button (plug icon) in the PlatformIO toolbar.

Set the baud rate to **115200**.

### Step 5: Verify Output

You should see:
```
========================================
MQ135 Air Quality Sensor - ESP32 NodeMCU
========================================

CIRCUIT WIRING:
MQ135 VCC  → 5V
MQ135 GND  → GND
...
```

---

## 🎯 Method 2: Using VSCode Command Palette

### Step 1: Open MQ135 Project File

Open [`src_mq135/main.cpp`](../src_mq135/main.cpp) in VSCode.

### Step 2: Open Command Palette

Press **Ctrl + Shift + P** (or **Cmd + Shift + P** on Mac).

### Step 3: Run Upload Command

Type: `PlatformIO: Upload`

Select it and press Enter.

### Step 4: Open Serial Monitor

Press **Ctrl + Shift + P** again.

Type: `PlatformIO: Serial Monitor`

Select it and press Enter.

Set baud rate to **115200**.

---

## 🎯 Method 3: Using VSCode Terminal

### Step 1: Open MQ135 Project File

Open [`src_mq135/main.cpp`](../src_mq135/main.cpp) in VSCode.

### Step 2: Open Terminal

Press **Ctrl + ~** (tilde key) to open the VSCode terminal.

### Step 3: Navigate to MQ135 Directory

```powershell
cd src_mq135
```

### Step 4: Upload

```powershell
pio run --target upload
```

### Step 5: Monitor

```powershell
pio device monitor -b 115200
```

---

## 🎯 Method 4: Using PowerShell Script

### Step 1: Run PowerShell Script

From the project root directory, run:

```powershell
.\upload_mq135.ps1
```

### Step 2: Follow the Prompts

The script will guide you through the upload process.

**Note:** If you get a script execution error, run this first:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## ❌ What NOT To Do

### ❌ DON'T Run `pio run --target upload` from Root Directory

This will upload the main project code (`src/main.cpp`), NOT the MQ135 code!

**Wrong:**
```powershell
# From D:\projects\meat_quality_Air_data
pio run --target upload  # ❌ Uploads main project!
```

**Correct:**
```powershell
# From D:\projects\meat_quality_Air_data\src_mq135
pio run --target upload  # ✅ Uploads MQ135 code!
```

### ❌ DON'T Use VSCode PlatformIO Upload Button with Root Project Open

If you have the root project folder open in VSCode and click the upload button, it will upload the main project code.

**Solution:** Open [`src_mq135/main.cpp`](../src_mq135/main.cpp) first, then use the PlatformIO toolbar.

### ❌ DON'T Run Batch Scripts (They Use cmd.exe)

The batch scripts (`.bat`) use `cmd.exe` and won't work in PowerShell.

**Solution:** Use the PowerShell script (`.ps1`) or VSCode PlatformIO extension.

---

## ✅ How to Verify You're Uploading the Right Code

### Check 1: Look at the File Tab

Make sure you have [`src_mq135/main.cpp`](../src_mq135/main.cpp) open in VSCode.

### Check 2: Look at Build Output

When building, you should see:
```
Compiling .pio\build\esp32dev\src\main.cpp.o
```

NOT:
```
Compiling .pio\build\esp32dev\src\mq135_sensor.cpp.o
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

### Problem: "pio is not recognized"

**Cause:** PlatformIO is not in your system PATH.

**Solution:** Use VSCode PlatformIO extension (Method 1 or 2).

### Problem: "Upload failed"

**Cause:** ESP32 not connected or wrong COM port.

**Solution:**
1. Check ESP32 is connected via USB
2. Check COM port in [`src_mq135/platformio.ini`](../src_mq135/platformio.ini)
3. Put ESP32 in bootloader mode (press BOOT button)
4. Try different USB cable

### Problem: "Multiple definition errors"

**Cause:** You're uploading from the wrong directory.

**Solution:** Make sure you have [`src_mq135/main.cpp`](../src_mq135/main.cpp) open in VSCode before uploading.

### Problem: "Script execution error" (PowerShell)

**Cause:** PowerShell script execution policy is restricted.

**Solution:** Run this in PowerShell:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: "Old code keeps uploading"

**Cause:** You're uploading from the root project instead of MQ135 project.

**Solution:**
1. Close [`src/main.cpp`](../src/main.cpp)
2. Open [`src_mq135/main.cpp`](../src_mq135/main.cpp)
3. Use the PlatformIO upload button

---

## 📋 Quick Reference

| Method | Command/Action | When to Use |
|--------|----------------|-------------|
| **VSCode Toolbar** | Click ⬇ Upload button | Easiest, recommended |
| **Command Palette** | Ctrl+Shift+P → PlatformIO: Upload | When toolbar not visible |
| **VSCode Terminal** | `cd src_mq135 && pio run --target upload` | When you prefer terminal |
| **PowerShell Script** | `.\upload_mq135.ps1` | When you want guided upload |

---

## 🎯 Recommended Workflow

1. **Open MQ135 file:** Open [`src_mq135/main.cpp`](../src_mq135/main.cpp) in VSCode
2. **Upload:** Click the ⬇ Upload button in PlatformIO toolbar
3. **Wait:** Wait for upload to complete
4. **Monitor:** Click the 🔌 Monitor button in PlatformIO toolbar
5. **Verify:** Check that you see MQ135 sensor readings

---

## 📞 Still Having Issues?

If you're still having trouble uploading:

1. **Check which file is open:**
   - Make sure [`src_mq135/main.cpp`](../src_mq135/main.cpp) is open
   - Close [`src/main.cpp`](../src/main.cpp)

2. **Check VSCode workspace:**
   - Look at the VSCode title bar
   - It should show `meat_quality_Air_data` or `src_mq135`

3. **Try VSCode terminal:**
   - Press Ctrl + ~ to open terminal
   - Run: `cd src_mq135`
   - Run: `pio run --target upload`

4. **Check ESP32 connection:**
   - Make sure ESP32 is connected via USB
   - Try a different USB cable
   - Press BOOT button on ESP32

---

## 📚 Additional Resources

- [PlatformIO VSCode Documentation](https://docs.platformio.org/en/latest/integration/ide/vscode.html)
- [MQ135 Wiring Guide](./MQ135_WIRING_GUIDE.md)
- [MQ135 Upload Guide](./MQ135_UPLOAD_GUIDE.md)

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Status:** ✅ Ready to Use
