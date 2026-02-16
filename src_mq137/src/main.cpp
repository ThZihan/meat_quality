/*
 * MQ137 Ammonia Sensor for ESP32 NodeMCU
 * 
 * This code reads MQ137 sensor data using ADC1 pins (safe with WiFi enabled)
 * MQ137 is specifically designed for ammonia (NH3) detection
 * 
 * CIRCUIT WIRING (Voltage Divider for 5V → 3.3V):
 * ================================================
 * MQ137 Module (5V operation):
 * ---------------------------
 * VCC  → 5V (external power supply or 5V pin on NodeMCU)
 * GND  → GND (common ground)
 * AOUT → Voltage Divider Input (see below)
 *
 * VOLTAGE DIVIDER (5kΩ + 10kΩ resistors):
 * --------------------------------------
 * MQ137 AOUT ────[5kΩ]───┬───[10kΩ]─── GND
 *                       │
 *                       └─── ESP32 GPIO 35 (ADC1_CH7)
 *
 * Voltage Divider Calculation:
 * - Input: 0-5V from MQ137
 * - Output: 0-3.33V to ESP32 (safe for 3.3V logic)
 * - Formula: Vout = Vin × (R2 / (R1 + R2)) = Vin × (10k / 15k) = Vin × 0.667
 * - To recover Vin: Vin = Vout / 0.667 = Vout × 1.5
 * 
 * ESP32 NodeMCU Connections:
 * --------------------------
 * GPIO 35 (ADC1_CH7) → Voltage Divider Output (MQ137 analog reading)
 * 3.3V              → Not used (MQ137 powered by 5V)
 * GND               → Common ground with MQ137
 * 
 * IMPORTANT NOTES:
 * ================
 * 1. Use ADC1 pins (GPIO 34, 35, 36, 39) - ADC2 pins conflict with WiFi!
 * 2. MQ137 requires 5V for heater - do NOT power from 3.3V
 * 3. Voltage divider is MANDATORY to protect ESP32 from 5V
 * 4. Calibrate sensor in clean air before first use
 * 5. Pre-heat sensor for 24-48 hours for accurate readings
 * 6. ESP32 ADC is 12-bit (0-4095), voltage divider halves the input
 * 
 * CALIBRATION:
 * ============
 * 1. Upload code and run in clean air (outdoor or well-ventilated area)
 * 2. Note the R0 value printed to Serial Monitor
 * 3. Update R0 constant in code with measured value
 * 4. Typical R0 for MQ137: 10kΩ - 100kΩ (varies by sensor)
 * 
 * MQ137 Gas Sensitivity (NH3 - Ammonia):
 * ======================================
 * - NH3: 10-500 ppm (ammonia detection range)
 * - Alcohol: 10-500 ppm
 * - Benzene: 10-1000 ppm
 * - Smoke: 100-10000 ppm
 * 
 * For Meat Quality Monitoring:
 * ============================
 * - Fresh meat: NH3 10-50 ppm
 * - Spoiling meat: NH3 > 100 ppm
 * - NH3 increase indicates protein breakdown
 * 
 * MQ137 vs MQ135:
 * ================
 * - MQ135: Better for CO2 and VOCs
 * - MQ137: Better for ammonia (NH3) detection
 * - Using both provides comprehensive air quality monitoring
 */

#include <Arduino.h>

// ===== HARDWARE CONFIGURATION =====
const int MQ137_PIN = 32;  // ADC1_CH7 - Safe with WiFi enabled
const float VOLTAGE_DIVIDER_RATIO = 1.5;  // 5V → 3.33V (5k+10k divider, multiply by 1.5 to recover)
const float ESP32_VREF = 3.3;  // ESP32 reference voltage
const int ADC_RESOLUTION = 4095;  // 12-bit ADC

// ===== MQ137 SENSOR PARAMETERS =====
// Load resistor value (on MQ137 module, typically 10kΩ)
const float RL = 10000.0;  // 10kΩ

// Sensor resistance in clean air (CALIBRATE THIS!)
// Measure in clean air and update this value
const float R0 = 25000.0;  // Default: 25kΩ (adjust after calibration)

// MQ137 sensitivity curve parameters (from datasheet)
// Rs/R0 = a * (ppm)^b
const float NH3_A = 102.2;
const float NH3_B = -2.473;

// ===== TIMING =====
const unsigned long READ_INTERVAL = 2000;  // Read every 2 seconds
const unsigned long PREHEAT_TIME = 48000;  // 48 hours preheat (in milliseconds)
unsigned long lastReadTime = 0;
unsigned long startTime = 0;

// ===== CALIBRATION MODE =====
bool calibrationMode = false;  // Set to true for calibration in clean air

// ===== FUNCTION PROTOTYPES =====
float readMQ137();
float calculatePPM(float rs, float a, float b);
float calculateRS(float voltage);
void calibrateSensor();
void printSensorData(float nh3PPM, float voltage, float rs);

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println(F("\n========================================"));
    Serial.println(F("MQ137 Ammonia Sensor - ESP32 NodeMCU"));
    Serial.println(F("========================================\n"));
    
    // Print circuit wiring information
    Serial.println(F("CIRCUIT WIRING:"));
    Serial.println(F("MQ137 VCC  → 5V"));
    Serial.println(F("MQ137 GND  → GND"));
    Serial.println(F("MQ137 AOUT → Voltage Divider (2x 10kΩ)"));
    Serial.println(F("              └─ ESP32 GPIO 35 (ADC1_CH7)"));
    Serial.println(F(""));
    
    // Print voltage divider info
    Serial.println(F("VOLTAGE DIVIDER (5kΩ + 10kΩ):"));
    Serial.print(F("  Ratio: 1:"));
    Serial.println(VOLTAGE_DIVIDER_RATIO);
    Serial.println(F("  Input: 0-5V (from MQ137)"));
    Serial.println(F("  Output: 0-3.33V (to ESP32 ADC)"));
    Serial.println(F("  Formula: Vin = Vadc × 1.5"));
    Serial.println(F(""));
    
    // Configure ADC
    analogReadResolution(12);  // 12-bit resolution (0-4095)
    analogSetAttenuation(ADC_11db);  // Full range: 0-3.3V
    
    // Check calibration mode
    if (calibrationMode) {
        Serial.println(F("CALIBRATION MODE ACTIVE"));
        Serial.println(F("Place sensor in clean air for 5 minutes..."));
        delay(5000);
        calibrateSensor();
    } else {
        Serial.print(F("Using R0 value: "));
        Serial.print(R0);
        Serial.println(F(" Ω"));
        Serial.println(F(""));
    }
    
    // Print sensor preheat info
    Serial.println(F("SENSOR PREHEAT:"));
    Serial.println(F("For accurate readings, preheat for 24-48 hours"));
    Serial.println(F(""));
    
    startTime = millis();
    Serial.println(F("Starting sensor readings...\n"));
}

void loop() {
    unsigned long currentTime = millis();
    
    // Read sensor at specified interval
    if (currentTime - lastReadTime >= READ_INTERVAL) {
        lastReadTime = currentTime;
        
        // Read MQ137 sensor
        float nh3PPM = readMQ137();
        
        // Get raw voltage and resistance for debugging
        int adcValue = analogRead(MQ137_PIN);
        float voltage = (adcValue / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float rs = calculateRS(voltage);
        
        // Print sensor data
        printSensorData(nh3PPM, voltage, rs);
        
        // Meat quality assessment
        Serial.println(F("MEAT QUALITY ASSESSMENT (Based on NH3):"));
        if (nh3PPM < 50) {
            Serial.println(F("  Status: FRESH"));
            Serial.println(F("  NH3 Level: Normal"));
        } else if (nh3PPM < 100) {
            Serial.println(F("  Status: GOOD"));
            Serial.println(F("  NH3 Level: Slightly elevated"));
        } else if (nh3PPM < 200) {
            Serial.println(F("  Status: MODERATE"));
            Serial.println(F("  NH3 Level: Elevated - monitor closely"));
        } else {
            Serial.println(F("  Status: SPOILED"));
            Serial.println(F("  NH3 Level: High - meat may be spoiled"));
        }
        Serial.println(F("========================================\n"));
    }
}

/**
 * Read MQ137 sensor and calculate NH3 PPM
 * @return NH3 concentration in PPM
 */
float readMQ137() {
    int adcValue = analogRead(MQ137_PIN);
    
    // Convert ADC to voltage (accounting for voltage divider)
    float voltage = (adcValue / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    
    // Calculate sensor resistance
    float rs = calculateRS(voltage);
    
    // Calculate PPM using NH3 curve
    float ppm = calculatePPM(rs, NH3_A, NH3_B);
    
    return ppm;
}

/**
 * Calculate sensor resistance Rs from voltage
 * @param voltage Measured voltage from sensor
 * @return Sensor resistance in ohms
 */
float calculateRS(float voltage) {
    if (voltage <= 0) return 0;
    
    // Rs = ((Vcc - Vout) / Vout) * RL
    // Vcc = 5V (MQ137 supply voltage)
    float rs = ((5.0 - voltage) / voltage) * RL;
    
    return rs;
}

/**
 * Calculate gas concentration in PPM
 * @param rs Sensor resistance
 * @param a Sensitivity curve parameter a
 * @param b Sensitivity curve parameter b
 * @return Gas concentration in PPM
 */
float calculatePPM(float rs, float a, float b) {
    if (rs <= 0) return 0;
    
    // Rs/R0 = a * (ppm)^b
    // ppm = ((Rs/R0) / a)^(1/b)
    float ratio = rs / R0;
    float ppm = pow((ratio / a), (1.0 / b));
    
    return ppm;
}

/**
 * Calibrate sensor in clean air
 * Prints the R0 value to Serial Monitor
 */
void calibrateSensor() {
    Serial.println(F("Calibrating sensor in clean air..."));
    Serial.println(F("This will take 10 seconds..."));
    
    float rsSum = 0;
    int readings = 10;
    
    for (int i = 0; i < readings; i++) {
        int adcValue = analogRead(MQ137_PIN);
        float voltage = (adcValue / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float rs = calculateRS(voltage);
        rsSum += rs;
        
        Serial.print(F("Reading "));
        Serial.print(i + 1);
        Serial.print(F("/"));
        Serial.print(readings);
        Serial.print(F(": Rs = "));
        Serial.print(rs);
        Serial.println(F(" Ω"));
        
        delay(1000);
    }
    
    float avgRs = rsSum / readings;
    float calculatedR0 = avgRs;  // In clean air, Rs ≈ R0
    
    Serial.println(F("\nCALIBRATION COMPLETE:"));
    Serial.print(F("Average Rs in clean air: "));
    Serial.print(avgRs);
    Serial.println(F(" Ω"));
    Serial.print(F("Update R0 constant in code to: "));
    Serial.println(calculatedR0);
    Serial.println(F(""));
}

/**
 * Print sensor data to Serial Monitor
 * @param nh3PPM NH3 concentration in PPM
 * @param voltage Measured voltage
 * @param rs Sensor resistance
 */
void printSensorData(float nh3PPM, float voltage, float rs) {
    Serial.println(F("SENSOR READINGS:"));
    
    // Raw ADC and voltage
    Serial.print(F("  ADC Value: "));
    Serial.println(analogRead(MQ137_PIN));
    Serial.print(F("  Voltage: "));
    Serial.print(voltage);
    Serial.println(F(" V"));
    
    // Sensor resistance
    Serial.print(F("  Rs: "));
    Serial.print(rs);
    Serial.println(F(" Ω"));
    Serial.print(F("  Rs/R0: "));
    Serial.println(rs / R0);
    
    // Gas concentrations
    Serial.print(F("  NH3: "));
    Serial.print(nh3PPM);
    Serial.println(F(" ppm"));
    
    // Uptime
    unsigned long uptime = (millis() - startTime) / 1000;
    Serial.print(F("  Uptime: "));
    Serial.print(uptime);
    Serial.println(F(" seconds"));
}
