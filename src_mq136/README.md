# MQ136 Air Quality Sensor - ESP32 NodeMCU

This project provides a web-based calibration interface for the MQ136 air quality sensor with ESP32 NodeMCU.

## What is MQ136?

The MQ136 gas sensor detects:
- **H2S (Hydrogen Sulfide)** - Primary target for meat spoilage detection
- **NH3 (Ammonia)** - Protein breakdown indicator
- **CO (Carbon Monoxide)** - Combustion byproduct

## Why MQ136 for Meat Quality?

H2S is a **key indicator of meat spoilage**:
- Fresh meat: H2S < 5 ppm
- Spoiling meat: H2S > 10 ppm
- Produced during protein breakdown and bacterial growth

## Hardware Requirements

- ESP32 NodeMCU board
- MQ136 gas sensor module
- 3x 10kΩ resistors (for voltage divider)
- 5V power supply
- Jumper wires
- Breadboard

## Circuit Wiring

```
MQ136 Module:
  VCC  → 5V (external power supply or NodeMCU 5V pin)
  GND  → GND (common ground)
  AOUT → Voltage Divider Input

Voltage Divider (3x 10kΩ resistors):
  MQ136 AOUT ────[10kΩ]───┬───[10kΩ]─── GND
                              │
                              └───[10kΩ]─── ESP32 GPIO 35
```

**Note:** Two 10kΩ resistors in parallel = 5kΩ
- Total resistance: 5kΩ + 10kΩ = 15kΩ
- Voltage division: Vout = Vin × (10k / 15k) = Vin × 0.667
- Input: 0-5V → Output: 0-3.33V (safe for ESP32)

## ESP32 Connections

| Pin | Connection |
|------|------------|
| GPIO 35 | Voltage divider output (MQ136 analog reading) |
| 3.3V | Not used (MQ136 powered by 5V) |
| GND | Common ground with MQ136 |

## Important Notes

1. **Use ADC1 pins** (GPIO 34, 35, 36, 39) - ADC2 pins conflict with WiFi!
2. **MQ136 requires 5V** for heater - do NOT power from 3.3V
3. **Voltage divider is MANDATORY** to protect ESP32 from 5V
4. **Pre-heat sensor for 24-48 hours** for accurate readings
5. **ESP32 ADC is 12-bit** (0-4095)

## Calibration

### Web-Based Calibration (Recommended)

1. Upload code to ESP32
2. Connect smartphone to WiFi: "MQ136-Calibrator" (no password)
3. Open browser: http://192.168.4.1
4. Place sensor in **clean air** (outdoor or well-ventilated area)
5. Click "Start Calibration" button
6. Wait 60 seconds for sensor to stabilize
7. Copy the R0 value displayed
8. Update R0 constant in [`src/main.cpp`](src/main.cpp:76)
9. Upload code again

### Typical R0 Values

- MQ136: 10kΩ - 100kΩ (varies by sensor)
- Your calibrated value will be specific to your sensor

## MQ136 Gas Sensitivity (Approximate)

| Gas | Range | Primary Use |
|------|--------|-------------|
| H2S | 1-200 ppm | Meat spoilage detection |
| NH3 | 10-300 ppm | Protein breakdown |
| CO | 1-1000 ppm | Combustion monitoring |

## Meat Quality Assessment

Based on H2S levels:

| H2S Level | Status | Description |
|------------|---------|-------------|
| < 5 ppm | FRESH | Normal, safe to consume |
| 5-10 ppm | GOOD | Slightly elevated, monitor |
| 10-20 ppm | MODERATE | Elevated, check for spoilage |
| > 20 ppm | SPOILED | High levels, do not consume |

## Building and Uploading

```bash
# Build the project
platformio run

# Upload to ESP32
platformio run --target upload

# Clean build artifacts
platformio run --target clean

# Monitor serial output
platformio device monitor
```

## Troubleshooting

### ADC Value: 0
- Check MQ136 VCC is connected to 5V
- Verify voltage divider connections
- Ensure GND is common between MQ136 and ESP32

### Readings Fluctuate Too Much
- Add 0.1µF capacitor across voltage divider output to GND
- Pre-heat sensor for 24-48 hours
- Keep sensor away from drafts and temperature changes

### Readings Always High/Low
- Recalibrate sensor in clean air
- Check potentiometer on MQ136 module (don't adjust unless necessary)
- Verify voltage divider resistor values

## Comparison: MQ135 vs MQ136

| Feature | MQ135 | MQ136 |
|---------|---------|---------|
| Primary Gas | CO2 | H2S |
| Meat Quality | CO2 levels | H2S levels |
| Spoilage Detection | Indirect | Direct (H2S = rot) |
| Calibration | Required | Required |

## License

This project is open source and available for educational purposes.
