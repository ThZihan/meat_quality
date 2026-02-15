# 🚀 Start Here: Upload MQ135 Code

## ⚡ Quick Start (3 Steps)

Since `pio` is not in your PATH, use VSCode PlatformIO extension:

### Step 1: Open MQ135 File
In VSCode, open: **`src_mq135/main.cpp`**

### Step 2: Upload
Click the **⬇ Upload** button in the PlatformIO toolbar (bottom of VSCode)

### Step 3: Monitor
Click the **🔌 Monitor** button in the PlatformIO toolbar (set baud rate to 115200)

---

## 🎯 That's It!

You should now see MQ135 sensor readings in the serial monitor.

---

## ❓ Need More Details?

See [`docs/MQ135_VSCODE_GUIDE.md`](docs/MQ135_VSCODE_GUIDE.md) for detailed instructions.

---

## ⚡ Circuit Wiring (Don't Forget!)

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

**⚠️ CRITICAL:** The voltage divider is MANDATORY! MQ135 outputs 0-5V, but ESP32 ADC pins only accept 0-3.3V.

---

## 📚 All Documentation

- [`docs/MQ135_VSCODE_GUIDE.md`](docs/MQ135_VSCODE_GUIDE.md) - VSCode PlatformIO guide
- [`docs/MQ135_WIRING_GUIDE.md`](docs/MQ135_WIRING_GUIDE.md) - Circuit wiring
- [`docs/MQ135_UPLOAD_GUIDE.md`](docs/MQ135_UPLOAD_GUIDE.md) - Upload instructions
- [`README.md`](README.md) - Main project documentation

---

**Ready? Open `src_mq135/main.cpp` and click Upload!** 🚀
