# MQ135 Sensor Wiring Guide for ESP32 NodeMCU

## Overview
This guide explains how to connect the MQ135 air quality sensor to ESP32 NodeMCU using a voltage divider to protect the ESP32 from the 5V sensor output.

## ⚠️ CRITICAL SAFETY WARNINGS

1. **NEVER connect MQ135 AOUT directly to ESP32** - The MQ135 outputs 0-5V, but ESP32 ADC pins only accept 0-3.3V. Direct connection will damage the ESP32!
2. **Use ADC1 pins only** - ADC2 pins (GPIO 32, 33) conflict with WiFi and will not work properly.
3. **Common ground is mandatory** - All devices must share the same ground reference.
4. **MQ135 requires 5V power** - Do NOT power from 3.3V pin, the heater will not work properly.

## Circuit Diagram

```
                    MQ135 SENSOR MODULE
                    ┌─────────────────┐
                    │                 │
5V ────────────────│ VCC             │
                    │                 │
GND ───────────────│ GND             │
                    │                 │
                    │ AOUT ───────────┼─────┐
                    │                 │     │
                    └─────────────────┘     │
                                            │
                                    ┌───────▼───────┐
                                    │  VOLTAGE      │
                                    │  DIVIDER      │
                                    │               │
                                    │  R1: 10kΩ     │
                                    │  R2: 10kΩ     │
                                    │               │
                                    └───────┬───────┘
                                            │
                                            │ 0-2.5V (Safe!)
                                            │
                                            │
                    ESP32 NODEMCU           │
                    ┌─────────────────┐     │
                    │                 │     │
                    │  GPIO 34        │◀────┘
                    │  (ADC1_CH6)     │
                    │                 │
                    │  3.3V           │
                    │                 │
                    │  GND            │
                    └─────────────────┘
```

## Detailed Connections

### MQ135 Sensor Module
| Pin | Connection | Notes |
|-----|------------|-------|
| VCC | 5V | External 5V supply or NodeMCU 5V pin |
| GND | GND | Common ground with ESP32 |
| AOUT | Voltage Divider Input | 0-5V analog output |

### Voltage Divider (2x 10kΩ Resistors)
```
MQ135 AOUT ────[10kΩ R1]───┬───[10kΩ R2]─── GND
                            │
                            └─── ESP32 GPIO 34
```

**Voltage Divider Calculation:**
- Input: 0-5V from MQ135
- Output: 0-2.5V to ESP32
- Formula: Vout = Vin × (R2 / (R1 + R2))
- Vout = Vin × (10k / 20k) = Vin × 0.5

**Why 2.5V is safe:**
- ESP32 ADC max input: 3.3V
- Voltage divider output: 0-2.5V
- Safety margin: 0.8V (24% headroom)

### ESP32 NodeMCU
| Pin | Connection | Notes |
|-----|------------|-------|
| GPIO 34 | Voltage Divider Output | ADC1_CH6 - Safe with WiFi |
| GND | Common Ground | Share with MQ135 |
| 3.3V | Not used | MQ135 powered by 5V |

## Component List

| Component | Quantity | Value/Type | Notes |
|-----------|----------|------------|-------|
| MQ135 Sensor Module | 1 | Air Quality | Includes load resistor |
| ESP32 NodeMCU | 1 | Development Board | - |
| Resistor | 2 | 10kΩ, 1/4W | Carbon film or metal film |
| Breadboard | 1 | - | For prototyping |
| Jumper Wires | Multiple | Male-to-Male | For connections |
| Power Supply | 1 | 5V, 500mA minimum | USB or external supply |

## Alternative ADC Pins

The following ADC1 pins are safe to use with WiFi enabled:

| GPIO | ADC Channel | Notes |
|------|------------|-------|
| 36 | ADC1_CH0 | Input only (no output) |
| 39 | ADC1_CH3 | Input only (no output) |
| 34 | ADC1_CH6 | Input only (no output) |
| 35 | ADC1_CH7 | Input only (no output) |

**⚠️ AVOID ADC2 PINS (GPIO 32, 33)** - These conflict with WiFi!

## Calibration Procedure

1. **Upload the code** to ESP32 NodeMCU
2. **Set calibration mode** to `true` in the code:
   ```cpp
   bool calibrationMode = true;
   ```
3. **Place sensor in clean air** - Outdoor or well-ventilated area
4. **Wait 5 minutes** for sensor to stabilize
5. **Read Serial Monitor** at 115200 baud
6. **Note the R0 value** printed during calibration
7. **Update R0 constant** in the code:
   ```cpp
   const float R0 = [YOUR_MEASURED_VALUE];  // Replace with actual value
   ```
8. **Set calibration mode** to `false`:
   ```cpp
   bool calibrationMode = false;
   ```
9. **Re-upload code** with new R0 value

## Preheating Requirements

For accurate readings, the MQ135 sensor requires preheating:

| Time | Accuracy | Notes |
|------|----------|-------|
| 5 minutes | ~60% | Quick readings, not accurate |
| 1 hour | ~80% | Acceptable for monitoring |
| 24 hours | ~95% | Recommended for accuracy |
| 48 hours | ~100% | Full accuracy achieved |

**Best Practice:** Preheat sensor for 24-48 hours before critical measurements.

## Meat Quality Monitoring Reference

### CO2 Levels (Freshness Indicator)
| CO2 (ppm) | Meat Quality | Action |
|-----------|--------------|--------|
| 400-600 | Fresh | Safe to consume |
| 600-800 | Good | Monitor closely |
| 800-1000 | Moderate | Consume soon |
| >1000 | Spoiled | Do not consume |

### NH3 Levels (Protein Breakdown)
| NH3 (ppm) | Meat Quality | Action |
|-----------|--------------|--------|
| 10-50 | Fresh | Safe to consume |
| 50-100 | Good | Monitor closely |
| 100-200 | Moderate | Consume soon |
| >200 | Spoiled | Do not consume |

## Troubleshooting

### Problem: Readings are always 0
**Possible Causes:**
- Loose connections
- Wrong GPIO pin used
- ADC2 pin used instead of ADC1
- MQ135 not powered (check 5V supply)

**Solution:**
- Verify all connections
- Use GPIO 34, 35, 36, or 39
- Check MQ135 VCC has 5V

### Problem: Readings are erratic
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

## Code Integration

To use this with your existing MQTT project:

1. **Copy the sensor reading function** from `mq135_sensor.cpp` to your main code
2. **Add MQTT publishing** in the loop:
   ```cpp
   float co2PPM = readMQ135();
   publishMQTTData(co2PPM);
   ```
3. **Update platformio.ini** if needed (already configured for ESP32)

## Safety Checklist

Before powering on:
- [ ] Voltage divider installed (2x 10kΩ resistors)
- [ ] Using ADC1 pin (GPIO 34, 35, 36, or 39)
- [ ] Common ground established
- [ ] MQ135 powered by 5V
- [ ] No direct 5V connection to ESP32 GPIO
- [ ] All connections secure
- [ ] Code uploaded and verified

## Additional Resources

- MQ135 Datasheet: [Link to datasheet]
- ESP32 ADC Documentation: [Link to docs]
- PlatformIO Documentation: [Link to docs]

## Version History

- v1.0 (2025-02-09): Initial wiring guide created
