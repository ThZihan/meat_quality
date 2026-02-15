# How to Upload MQ137 Code Using VSCode PlatformIO

## ⚠️ IMPORTANT: PlatformIO (pio) Not in PATH

Since `pio` is not in your system PATH, you should use **VSCode PlatformIO extension** instead. This is actually easier and more reliable!

---

## 🎯 Method 1: Using VSCode PlatformIO Extension (RECOMMENDED)

This is the easiest method since you already have VSCode installed.

### Step 1: Open MQ137 Project File

1. In VSCode, open the file: **`src_mq137/src/main.cpp`**
2. This will automatically set PlatformIO context to the MQ137 project

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
MQ137 Ammonia Sensor - ESP32 NodeMCU
========================================

CIRCUIT WIRING:
MQ137 VCC  → 5V
MQ137 GND  → GND
...
```

---

## 🎯 Method 2: Using VSCode Command Palette

### Step 1: Open MQ137 Project File

Open **`src_mq137/src/main.cpp`** in VSCode.

### Step 2: Open Command Palette

Press **Ctrl + Shift + P** (or **Cmd + Shift + P** on Mac).

### Step 3: Run Upload Command

Type: `PlatformIO: Upload`

Select it and press Enter.

### Step 4: Open Serial Monitor

Press **Ctrl + Shift + P** again.

Type: `PlatformIO: Serial Monitor`

Select it and press Enter.

Set the baud rate to **115200**.

---

## 🎯 Method 3: Using VSCode Terminal

### Step 1: Open MQ137 Project File

Open **`src_mq137/src/main.cpp`** in VSCode.

### Step 2: Open Terminal

Press **Ctrl + ~** (tilde key) to open the VSCode terminal.

### Step 3: Navigate to MQ137 Directory

```powershell
cd src_mq137
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
.\upload_mq137.ps1
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

This will upload the main project code (`src/main.cpp`), NOT the MQ137 code!

**Wrong:**
```powershell
# From D:\projects\meat_quality_Air_data
pio run --target upload  # ❌ Uploads main project!
```

**Correct:**
```powershell
# From D:\projects\meat_quality_Air_data\src_mq137
pio run --target upload  # ✅ Uploads MQ137 code!
```

### ❌ DON'T Use VSCode PlatformIO Upload Button with Root Project Open

If you have the root project folder open in VSCode and click the upload button, it will upload the main project code.

**Solution:** Open **`src_mq137/src/main.cpp`** first, then use the PlatformIO toolbar.

### ❌ DON'T Run Batch Scripts (They Use cmd.exe)

The batch scripts (`.bat`) use `cmd.exe` and won't work in PowerShell.

**Solution:** Use the PowerShell script (`.ps1`) or the VSCode PlatformIO extension.

---

## ✅ How to Verify You're Uploading the Right Code

### Check 1: Look at the File Tab

Make sure you have **`src_mq137/src/main.cpp`** open in VSCode.

### Check 2: Look at the Build Output

When building, you should see:
```
Compiling .pio\build\esp32dev\src\main.cpp.o
```

NOT:
```
Compiling .pio\build\esp32dev\src\mq137_sensor.cpp.o
```

### Check 3: Check the Serial Monitor Output

After upload, the serial monitor should show:
```
========================================
MQ137 Ammonia Sensor - ESP32 NodeMCU
========================================

CIRCUIT WIRING:
MQ137 VCC  → 5V
MQ137 GND  → GND
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

**Solution:** Use the VSCode PlatformIO extension (Method 1 or 2).

### Problem: "Upload failed"

**Cause:** ESP32 not connected or wrong COM port.

**Solution:**
1. Check that the ESP32 is connected via USB
2. Check the COM port in `src_mq137/platformio.ini` (currently COM7)
3. Put the ESP32 in bootloader mode (press the BOOT button)
4. Try a different USB cable

### Problem: "Multiple definition errors"

**Cause:** You're uploading from the wrong directory.

**Solution:** Make sure you have **`src_mq137/src/main.cpp`** open in VSCode before uploading.

### Problem: "Script execution error" (PowerShell)

**Cause:** PowerShell script execution policy is restricted.

**Solution:** Run this in PowerShell:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: "Old code keeps uploading"

**Cause:** You're uploading from the root project instead of the MQ137 project.

**Solution:**
1. Close **`src/main.cpp`**
2. Open **`src_mq137/src/main.cpp`**
3. Use the PlatformIO upload button

---

## 📋 Quick Reference

| Method | Command/Action | When to Use |
|--------|----------------|-------------|
| **VSCode Toolbar** | Click ⬇ Upload button | Easiest, recommended |
| **Command Palette** | Ctrl+Shift+P → PlatformIO: Upload | When toolbar not visible |
| **VSCode Terminal** | `cd src_mq137 && pio run --target upload` | When you prefer terminal |
| **PowerShell Script** | `.\upload_mq137.ps1` | When you want guided upload |

---

## 🎯 Recommended Workflow

1. **Open MQ137 file:** Open **`src_mq137/src/main.cpp`** in VSCode
2. **Upload:** Click the ⬇ Upload button in the PlatformIO toolbar
3. **Wait:** Wait for the upload to complete
4. **Monitor:** Click the 🔌 Monitor button in the PlatformIO toolbar
5. **Verify:** Check that you see MQ137 sensor readings

---

## 📞 Still Having Issues?

If you're still having trouble uploading:

1. **Check which file is open:**
   - Make sure **`src_mq137/src/main.cpp`** is open
   - Close **`src/main.cpp`**

2. **Check the VSCode workspace:**
   - Look at the VSCode title bar
   - It should show `meat_quality_Air_data` or `src_mq137`

3. **Try the VSCode terminal:**
   - Press Ctrl + ~ to open the terminal
   - Run: `cd src_mq137`
   - Run: `pio run --target upload`

4. **Check the ESP32 connection:**
   - Make sure the ESP32 is connected via USB
   - Try a different USB cable
   - Press the BOOT button on the ESP32

---

## 📚 Additional Resources

- [PlatformIO VSCode Documentation](https://docs.platformio.org/en/latest/integration/ide/vscode.html)
- [MQ137 Wiring Guide](./MQ137_WIRING_GUIDE.md)
- [MQ137 Quick Reference](./MQ137_QUICK_REFERENCE.txt)
- [MQ137 Project README](../src_mq137/README.md)

---

**Version:** 1.0  
**Date:** 2025-02-09  
**Status:** ✅ Ready to Use
