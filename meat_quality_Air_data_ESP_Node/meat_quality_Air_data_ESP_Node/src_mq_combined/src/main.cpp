/*
 * MQ135 + MQ136 + MQ137 Combined Air Quality Sensor for ESP32 NodeMCU
 * SoftAP Web Calibration Version - 48-Hour Fresh Air Calibration Ready
 * 
 * This code reads all three MQ sensors (MQ135, MQ136, MQ137) and provides
 * a unified web interface for calibration via SoftAP (no WiFi router needed)
 * 
 * EEPROM STORAGE:
 * ==============
 * - Calibration data saved at 12h, 24h, and 48h intervals
 * - Persistent across reboots
 * - View saved data via web interface
 * 
 * SENSOR DETECTION:
 * ================
 * - MQ135: CO2 (Carbon Dioxide), NH3 (Ammonia), VOCs
 * - MQ136: H2S (Hydrogen Sulfide), NH3, CO (Carbon Monoxide)
 * - MQ137: NH3 (Ammonia) - specialized ammonia detection
 * 
 * CIRCUIT WIRING (Voltage Dividers for 5V → 3.3V):
 * =================================================
 * MQ135 Module (5V operation):
 * ---------------------------
 * VCC  → 5V (external power supply or 5V pin on NodeMCU)
 * GND  → GND (common ground)
 * AOUT → Voltage Divider Input (see below)
 * 
 * MQ136 Module (5V operation):
 * ---------------------------
 * VCC  → 5V (external power supply or 5V pin on NodeMCU)
 * GND  → GND (common ground)
 * AOUT → Voltage Divider Input (see below)
 * 
 * MQ137 Module (5V operation):
 * ---------------------------
 * VCC  → 5V (external power supply or 5V pin on NodeMCU)
 * GND  → GND (common ground)
 * AOUT → Voltage Divider Input (see below)
 * 
 * VOLTAGE DIVIDER (parallel 10k + 10k = 5k, then 10k to GND):
 * ------------------------------------------------------------
 * MQ135 AOUT ────[10k||10k = 5k]───┬───[10kΩ]─── GND
 *                                 │
 *                                 └─── ESP32 GPIO 34 (ADC1_CH6)
 * 
 * MQ136 AOUT ────[10k||10k = 5k]───┬───[10kΩ]─── GND
 *                                 │
 *                                 └─── ESP32 GPIO 35 (ADC1_CH7)
 * 
 * MQ137 AOUT ────[10k||10k = 5k]───┬───[10kΩ]─── GND
 *                                 │
 *                                 └─── ESP32 GPIO 32 (ADC1_CH4)
 * 
 * Voltage Divider Calculation:
 * - Input: 0-5V from MQ sensors
 * - Output: 0-3.33V to ESP32 (safe for 3.3V logic)
 * - Formula: Vout = Vin × (10k / 15k) = Vin × 0.667
 * 
 * ESP32 NodeMCU Connections:
 * --------------------------
 * GPIO 34 (ADC1_CH6) → MQ135 Voltage Divider Output
 * GPIO 35 (ADC1_CH7) → MQ136 Voltage Divider Output
 * GPIO 32 (ADC1_CH4) → MQ137 Voltage Divider Output
 * 3.3V              → Not used (MQ sensors powered by 5V)
 * GND               → Common ground with all MQ sensors
 * 
 * WEB CALIBRATION:
 * ================
 * 1. ESP32 creates SoftAP: "MQ-Calibrator"
 * 2. Connect smartphone to this WiFi (no password)
 * 3. Open browser: http://192.168.4.1
 * 4. Click "Start 48-Hour Calibration" button
 * 5. Place device in BALCONY with FRESH AIR for 48 hours
 * 6. Calibration data saved at 12h, 24h, and 48h intervals
 * 7. View saved data via web interface buttons
 * 8. Progress persists across page reloads and reboots
 * 
 * IMPORTANT NOTES:
 * ================
 * 1. Use ADC1 pins (GPIO 34, 35, 36, 39) - ADC2 pins conflict with WiFi!
 * 2. All MQ sensors require 5V for heater - do NOT power from 3.3V
 * 3. Voltage dividers are MANDATORY to protect ESP32 from 5V
 * 4. Pre-heat sensors for 24-48 hours in fresh air for accurate readings
 * 5. ESP32 ADC is 12-bit (0-4095)
 * 6. 48-hour calibration is recommended for best accuracy
 * 7. Calibration data saved to EEPROM - no need to stay connected!
 * 
 * CALIBRATION:
 * ============
 * 1. Place all sensors in clean air (outdoor or well-ventilated balcony)
 * 2. Connect to SoftAP and open web interface
 * 3. Click 48-hour calibration button
 * 4. Leave device undisturbed for 48 hours
 * 5. Data saved at 12h, 24h, and 48h intervals
 * 6. View saved R0 values via web interface
 * 7. Typical R0 values:
 *    - MQ135: 10kΩ - 100kΩ (varies by sensor)
 *    - MQ136: 10kΩ - 100kΩ (varies by sensor)
 *    - MQ137: 10kΩ - 100kΩ (varies by sensor)
 * 
 * MEAT QUALITY MONITORING:
 * ========================
 * Combined assessment using all sensors:
 * - Fresh meat: CO2 < 600ppm, H2S < 5ppm, NH3 < 50ppm
 * - Good meat: CO2 < 800ppm, H2S < 10ppm, NH3 < 100ppm
 * - Moderate: CO2 < 1000ppm, H2S < 20ppm, NH3 < 200ppm
 * - Spoiled: Any sensor above thresholds
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <EEPROM.h>

// ===== EEPROM ADDRESSES =====
#define EEPROM_SIZE 512
#define EEPROM_CALIBRATION_ACTIVE 0
#define EEPROM_CALIBRATION_START_TIME 4
#define EEPROM_CALIBRATION_DURATION 8
#define EEPROM_12H_SAVED 12
#define EEPROM_24H_SAVED 13
#define EEPROM_48H_SAVED 14
#define EEPROM_12H_R0_MQ135 15
#define EEPROM_12H_R0_MQ136 19
#define EEPROM_12H_R0_MQ137 23
#define EEPROM_24H_R0_MQ135 27
#define EEPROM_24H_R0_MQ136 31
#define EEPROM_24H_R0_MQ137 35
#define EEPROM_48H_R0_MQ135 39
#define EEPROM_48H_R0_MQ136 43
#define EEPROM_48H_R0_MQ137 47

// ===== HARDWARE CONFIGURATION =====
const int MQ135_PIN = 34;  // ADC1_CH6 - Safe with WiFi enabled
const int MQ136_PIN = 35;  // ADC1_CH7 - Safe with WiFi enabled
const int MQ137_PIN = 32;  // ADC1_CH4 - Safe with WiFi enabled
const float VOLTAGE_DIVIDER_RATIO = 1.5;  // 5V → 3.33V (divide by 1.5)
const float ESP32_VREF = 3.3;  // ESP32 reference voltage
const int ADC_RESOLUTION = 4095;  // 12-bit ADC

// ===== MQ SENSOR PARAMETERS =====
// Load resistor value (on MQ modules, typically 10kΩ)
const float RL = 10000.0;  // 10kΩ

// Sensor resistance in clean air (UPDATE THESE AFTER CALIBRATION!)
const float MQ135_R0 = 193200.00;  // From 24-Hour Burn-in
const float MQ136_R0 = 85102.55;   // From 24-Hour Burn-in
const float MQ137_R0 = 51913.09;   // From 24-Hour Burn-in

// MQ135 sensitivity curve parameters (from datasheet)
const float MQ135_CO2_A = 110.47;
const float MQ135_CO2_B = -2.862;
const float MQ135_NH3_A = 102.2;
const float MQ135_NH3_B = -2.473;

// MQ136 sensitivity curve parameters (from datasheet)
const float MQ136_H2S_A = 44.947;
const float MQ136_H2S_B = -2.648;
const float MQ136_NH3_A = 102.2;
const float MQ136_NH3_B = -2.473;
const float MQ136_CO_A = 605.18;
const float MQ136_CO_B = -3.039;

// MQ137 sensitivity curve parameters (from datasheet)
const float MQ137_NH3_A = 102.2;
const float MQ137_NH3_B = -2.473;

// ===== WIFI / WEB SERVER CONFIG =====
const char* SOFTAP_SSID = "MQ-Calibrator";
const char* SOFTAP_PASSWORD = "";  // Open network
WebServer server(80);

// ===== TIMING =====
const unsigned long READ_INTERVAL = 2000;  // Read every 2 seconds
const unsigned long CALIBRATION_DURATION_48H = 48UL * 60UL * 60UL * 1000UL;  // 48 hours
const unsigned long CALIBRATION_DURATION_12H = 12UL * 60UL * 60UL * 1000UL;  // 12 hours
const unsigned long CALIBRATION_DURATION_24H = 24UL * 60UL * 60UL * 1000UL;  // 24 hours
unsigned long lastReadTime = 0;
unsigned long startTime = 0;

// ===== CALIBRATION STATE =====
bool isCalibrating = false;
unsigned long calibrationStartTime = 0;
unsigned long calibrationDuration = CALIBRATION_DURATION_48H;  // Default: 48 hours
float calibrationSumMQ135 = 0;
float calibrationSumMQ136 = 0;
float calibrationSumMQ137 = 0;
int calibrationCount = 0;

// Saved calibration data
bool saved12h = false;
bool saved24h = false;
bool saved48h = false;
float r0_12h_MQ135 = 0.0;
float r0_12h_MQ136 = 0.0;
float r0_12h_MQ137 = 0.0;
float r0_24h_MQ135 = 0.0;
float r0_24h_MQ136 = 0.0;
float r0_24h_MQ137 = 0.0;
float r0_48h_MQ135 = 0.0;
float r0_48h_MQ136 = 0.0;
float r0_48h_MQ137 = 0.0;

// ===== FUNCTION PROTOTYPES =====
float readMQ135();
float readMQ136();
float readMQ137();
float calculatePPM(float rs, float a, float b, float r0);
float calculateRS(float voltage);
void handleRoot();
void handleStartCalibration48h();
void handleStartCalibration1h();
void handleStartCalibration10m();
void handleStopCalibration();
void handleCalibrationStatus();
void handleSensorData();
void handleGetSavedData();
void clearEEPROM();
void saveCalibrationData(int hours);
void loadCalibrationData();
String getHTML();
void setupWiFi();
void setupWebServer();

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println(F("\n========================================"));
    Serial.println(F("MQ135 + MQ136 + MQ137 Combined Sensors"));
    Serial.println(F("ESP32 NodeMCU - Web Calibration Mode"));
    Serial.println(F("EEPROM Storage Enabled"));
    Serial.println(F("========================================\n"));
    
    // Initialize EEPROM
    EEPROM.begin(EEPROM_SIZE);
    loadCalibrationData();
    
    // Configure ADC
    analogReadResolution(12);  // 12-bit resolution (0-4095)
    analogSetAttenuation(ADC_11db);  // Full range: 0-3.3V
    
    // Setup WiFi SoftAP
    setupWiFi();
    
    // Setup Web Server
    setupWebServer();
    
    // Print circuit wiring information
    Serial.println(F("CIRCUIT WIRING:"));
    Serial.println(F("MQ135 VCC  → 5V"));
    Serial.println(F("MQ135 GND  → GND"));
    Serial.println(F("MQ135 AOUT → [10k||10k] → GPIO 34"));
    Serial.println(F("              └─ [10k] → GND"));
    Serial.println(F(""));
    Serial.println(F("MQ136 VCC  → 5V"));
    Serial.println(F("MQ136 GND  → GND"));
    Serial.println(F("MQ136 AOUT → [10k||10k] → GPIO 35"));
    Serial.println(F("              └─ [10k] → GND"));
    Serial.println(F(""));
    Serial.println(F("MQ137 VCC  → 5V"));
    Serial.println(F("MQ137 GND  → GND"));
    Serial.println(F("MQ137 AOUT → [10k||10k] → GPIO 32"));
    Serial.println(F("              └─ [10k] → GND"));
    Serial.println(F(""));
    
    // Print WiFi info
    Serial.println(F("WIFI INFO:"));
    Serial.print(F("  SoftAP SSID: "));
    Serial.println(SOFTAP_SSID);
    Serial.println(F("  Connect smartphone to this network"));
    Serial.print(F("  Open browser: http://"));
    Serial.println(WiFi.softAPIP());
    Serial.println(F(""));
    
    // Print current R0 values
    Serial.println(F("CURRENT R0 VALUES:"));
    Serial.print(F("  MQ135 R0: "));
    Serial.print(MQ135_R0);
    Serial.println(F(" Ω"));
    Serial.print(F("  MQ136 R0: "));
    Serial.print(MQ136_R0);
    Serial.println(F(" Ω"));
    Serial.print(F("  MQ137 R0: "));
    Serial.print(MQ137_R0);
    Serial.println(F(" Ω"));
    Serial.println(F(""));
    
    // Print saved calibration data
    Serial.println(F("SAVED CALIBRATION DATA:"));
    Serial.print(F("  12h saved: "));
    Serial.println(saved12h ? "YES" : "NO");
    Serial.print(F("  24h saved: "));
    Serial.println(saved24h ? "YES" : "NO");
    Serial.print(F("  48h saved: "));
    Serial.println(saved48h ? "YES" : "NO");
    Serial.println(F(""));
    
    // Print sensor preheat info
    Serial.println(F("SENSOR PREHEAT:"));
    Serial.println(F("For accurate readings, preheat for 24-48 hours"));
    Serial.println(F("Use 48-hour calibration for best results"));
    Serial.println(F(""));
    
    // Restore calibration state if active
    if (isCalibrating) {
        Serial.println(F("Restoring calibration state from EEPROM"));
        Serial.print(F("Calibration started at: "));
        Serial.println(calibrationStartTime);
        Serial.print(F("Duration: "));
        Serial.print(calibrationDuration / 1000 / 60 / 60);
        Serial.println(F(" hours"));
    }
    
    startTime = millis();
    Serial.println(F("Starting sensor readings...\n"));
}

void loop() {
    server.handleClient();
    
    unsigned long currentTime = millis();
    
    // Handle calibration if active
    if (isCalibrating) {
        unsigned long elapsed = currentTime - calibrationStartTime;
        
        // Check if we need to save calibration data
        if (elapsed >= CALIBRATION_DURATION_12H && !saved12h) {
            saveCalibrationData(12);
        } else if (elapsed >= CALIBRATION_DURATION_24H && !saved24h) {
            saveCalibrationData(24);
        } else if (elapsed >= CALIBRATION_DURATION_48H && !saved48h) {
            saveCalibrationData(48);
            // Calibration complete
            isCalibrating = false;
            EEPROM.writeByte(EEPROM_CALIBRATION_ACTIVE, 0);
            EEPROM.commit();
            
            Serial.println(F("\n========================================"));
            Serial.println(F("48-HOUR CALIBRATION COMPLETE!"));
            Serial.println(F("All calibration data saved to EEPROM"));
            Serial.println(F("========================================\n"));
            return;
        } else {
            // Take calibration sample
            int adcValueMQ135 = analogRead(MQ135_PIN);
            float voltageMQ135 = (adcValueMQ135 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
            float rsMQ135 = calculateRS(voltageMQ135);
            
            int adcValueMQ136 = analogRead(MQ136_PIN);
            float voltageMQ136 = (adcValueMQ136 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
            float rsMQ136 = calculateRS(voltageMQ136);
            
            int adcValueMQ137 = analogRead(MQ137_PIN);
            float voltageMQ137 = (adcValueMQ137 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
            float rsMQ137 = calculateRS(voltageMQ137);
            
            if (rsMQ135 > 0 && rsMQ136 > 0 && rsMQ137 > 0) {
                calibrationSumMQ135 += rsMQ135;
                calibrationSumMQ136 += rsMQ136;
                calibrationSumMQ137 += rsMQ137;
                calibrationCount++;
            }
            
            delay(100);  // Sample every 100ms during calibration
        }
        return;
    }
    
    // Read sensor at specified interval
    if (currentTime - lastReadTime >= READ_INTERVAL) {
        lastReadTime = currentTime;
        
        // Read all MQ sensors
        float mq135_co2PPM = calculatePPM(calculateRS((analogRead(MQ135_PIN) / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO), MQ135_CO2_A, MQ135_CO2_B, MQ135_R0);
        float mq135_nh3PPM = calculatePPM(calculateRS((analogRead(MQ135_PIN) / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO), MQ135_NH3_A, MQ135_NH3_B, MQ135_R0);
        
        float mq136_h2sPPM = calculatePPM(calculateRS((analogRead(MQ136_PIN) / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO), MQ136_H2S_A, MQ136_H2S_B, MQ136_R0);
        float mq136_nh3PPM = calculatePPM(calculateRS((analogRead(MQ136_PIN) / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO), MQ136_NH3_A, MQ136_NH3_B, MQ136_R0);
        float mq136_coPPM = calculatePPM(calculateRS((analogRead(MQ136_PIN) / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO), MQ136_CO_A, MQ136_CO_B, MQ136_R0);
        
        float mq137_nh3PPM = calculatePPM(calculateRS((analogRead(MQ137_PIN) / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO), MQ137_NH3_A, MQ137_NH3_B, MQ137_R0);
        
        // Get raw voltage and resistance for debugging
        int adcValueMQ135 = analogRead(MQ135_PIN);
        float voltageMQ135 = (adcValueMQ135 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float rsMQ135 = calculateRS(voltageMQ135);
        
        int adcValueMQ136 = analogRead(MQ136_PIN);
        float voltageMQ136 = (adcValueMQ136 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float rsMQ136 = calculateRS(voltageMQ136);
        
        int adcValueMQ137 = analogRead(MQ137_PIN);
        float voltageMQ137 = (adcValueMQ137 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float rsMQ137 = calculateRS(voltageMQ137);
        
        // Print to Serial Monitor
        Serial.println(F("SENSOR READINGS:"));
        Serial.println(F("MQ135 (CO2/NH3):"));
        Serial.print(F("  ADC: "));
        Serial.print(adcValueMQ135);
        Serial.print(F(", Voltage: "));
        Serial.print(voltageMQ135, 3);
        Serial.print(F(" V, Rs: "));
        Serial.print(rsMQ135);
        Serial.println(F(" Ω"));
        Serial.print(F("  CO2: "));
        Serial.print(mq135_co2PPM);
        Serial.println(F(" ppm"));
        Serial.print(F("  NH3: "));
        Serial.print(mq135_nh3PPM);
        Serial.println(F(" ppm"));
        
        Serial.println(F("MQ136 (H2S/NH3/CO):"));
        Serial.print(F("  ADC: "));
        Serial.print(adcValueMQ136);
        Serial.print(F(", Voltage: "));
        Serial.print(voltageMQ136, 3);
        Serial.print(F(" V, Rs: "));
        Serial.print(rsMQ136);
        Serial.println(F(" Ω"));
        Serial.print(F("  H2S: "));
        Serial.print(mq136_h2sPPM);
        Serial.println(F(" ppm"));
        Serial.print(F("  NH3: "));
        Serial.print(mq136_nh3PPM);
        Serial.println(F(" ppm"));
        Serial.print(F("  CO: "));
        Serial.print(mq136_coPPM);
        Serial.println(F(" ppm"));
        
        Serial.println(F("MQ137 (NH3):"));
        Serial.print(F("  ADC: "));
        Serial.print(adcValueMQ137);
        Serial.print(F(", Voltage: "));
        Serial.print(voltageMQ137, 3);
        Serial.print(F(" V, Rs: "));
        Serial.print(rsMQ137);
        Serial.println(F(" Ω"));
        Serial.print(F("  NH3: "));
        Serial.print(mq137_nh3PPM);
        Serial.println(F(" ppm"));
        
        // Combined meat quality assessment
        Serial.println(F("MEAT QUALITY ASSESSMENT (Combined):"));
        bool fresh = (mq135_co2PPM < 600) && (mq136_h2sPPM < 5) && (mq137_nh3PPM < 50);
        bool good = (mq135_co2PPM < 800) && (mq136_h2sPPM < 10) && (mq137_nh3PPM < 100);
        bool moderate = (mq135_co2PPM < 1000) && (mq136_h2sPPM < 20) && (mq137_nh3PPM < 200);
        
        if (fresh) {
            Serial.println(F("  Status: FRESH"));
            Serial.println(F("  All gas levels are normal"));
        } else if (good) {
            Serial.println(F("  Status: GOOD"));
            Serial.println(F("  Gas levels slightly elevated"));
        } else if (moderate) {
            Serial.println(F("  Status: MODERATE"));
            Serial.println(F("  Gas levels elevated - monitor closely"));
        } else {
            Serial.println(F("  Status: SPOILED"));
            Serial.println(F("  High gas levels - meat may be spoiled"));
        }
        Serial.println(F("========================================\n"));
    }
}

/**
 * Save calibration data to EEPROM
 */
void saveCalibrationData(int hours) {
    float avgR0_MQ135 = calibrationSumMQ135 / calibrationCount;
    float avgR0_MQ136 = calibrationSumMQ136 / calibrationCount;
    float avgR0_MQ137 = calibrationSumMQ137 / calibrationCount;
    
    Serial.println(F("\n========================================"));
    Serial.print(hours);
    Serial.println(F("-HOUR CALIBRATION DATA SAVED"));
    Serial.print(F("MQ135 R0: "));
    Serial.println(avgR0_MQ135);
    Serial.print(F("MQ136 R0: "));
    Serial.println(avgR0_MQ136);
    Serial.print(F("MQ137 R0: "));
    Serial.println(avgR0_MQ137);
    Serial.println(F("========================================\n"));
    
    // Save to EEPROM
    int baseAddr;
    if (hours == 12) {
        saved12h = true;
        EEPROM.writeByte(EEPROM_12H_SAVED, 1);
        baseAddr = EEPROM_12H_R0_MQ135;
        r0_12h_MQ135 = avgR0_MQ135;
        r0_12h_MQ136 = avgR0_MQ136;
        r0_12h_MQ137 = avgR0_MQ137;
    } else if (hours == 24) {
        saved24h = true;
        EEPROM.writeByte(EEPROM_24H_SAVED, 1);
        baseAddr = EEPROM_24H_R0_MQ135;
        r0_24h_MQ135 = avgR0_MQ135;
        r0_24h_MQ136 = avgR0_MQ136;
        r0_24h_MQ137 = avgR0_MQ137;
    } else if (hours == 48) {
        saved48h = true;
        EEPROM.writeByte(EEPROM_48H_SAVED, 1);
        baseAddr = EEPROM_48H_R0_MQ135;
        r0_48h_MQ135 = avgR0_MQ135;
        r0_48h_MQ136 = avgR0_MQ136;
        r0_48h_MQ137 = avgR0_MQ137;
    }
    
    // Save R0 values as floats (4 bytes each)
    EEPROM.put(baseAddr, avgR0_MQ135);
    EEPROM.put(baseAddr + 4, avgR0_MQ136);
    EEPROM.put(baseAddr + 8, avgR0_MQ137);
    EEPROM.commit();
}

/**
 * Load calibration data from EEPROM
 */
void loadCalibrationData() {
    // Load calibration state
    isCalibrating = EEPROM.readByte(EEPROM_CALIBRATION_ACTIVE) == 1;
    
    // Load calibration start time
    EEPROM.get(EEPROM_CALIBRATION_START_TIME, calibrationStartTime);
    EEPROM.get(EEPROM_CALIBRATION_DURATION, calibrationDuration);
    
    // Load saved flags
    saved12h = EEPROM.readByte(EEPROM_12H_SAVED) == 1;
    saved24h = EEPROM.readByte(EEPROM_24H_SAVED) == 1;
    saved48h = EEPROM.readByte(EEPROM_48H_SAVED) == 1;
    
    // Load R0 values
    if (saved12h) {
        EEPROM.get(EEPROM_12H_R0_MQ135, r0_12h_MQ135);
        EEPROM.get(EEPROM_12H_R0_MQ136, r0_12h_MQ136);
        EEPROM.get(EEPROM_12H_R0_MQ137, r0_12h_MQ137);
    }
    if (saved24h) {
        EEPROM.get(EEPROM_24H_R0_MQ135, r0_24h_MQ135);
        EEPROM.get(EEPROM_24H_R0_MQ136, r0_24h_MQ136);
        EEPROM.get(EEPROM_24H_R0_MQ137, r0_24h_MQ137);
    }
    if (saved48h) {
        EEPROM.get(EEPROM_48H_R0_MQ135, r0_48h_MQ135);
        EEPROM.get(EEPROM_48H_R0_MQ136, r0_48h_MQ136);
        EEPROM.get(EEPROM_48H_R0_MQ137, r0_48h_MQ137);
    }
}

/**
 * Clear EEPROM (factory reset)
 */
void clearEEPROM() {
    for (int i = 0; i < EEPROM_SIZE; i++) {
        EEPROM.writeByte(i, 0);
    }
    EEPROM.commit();
    
    // Reset state
    isCalibrating = false;
    saved12h = false;
    saved24h = false;
    saved48h = false;
    calibrationStartTime = 0;
    calibrationDuration = CALIBRATION_DURATION_48H;
    calibrationSumMQ135 = 0;
    calibrationSumMQ136 = 0;
    calibrationSumMQ137 = 0;
    calibrationCount = 0;
    
    Serial.println(F("EEPROM cleared - factory reset"));
}

/**
 * Setup WiFi SoftAP
 */
void setupWiFi() {
    Serial.println(F("Setting up SoftAP..."));
    
    WiFi.mode(WIFI_AP);
    WiFi.softAP(SOFTAP_SSID, SOFTAP_PASSWORD);
    
    Serial.print(F("SoftAP IP: "));
    Serial.println(WiFi.softAPIP());
}

/**
 * Setup Web Server routes
 */
void setupWebServer() {
    server.on("/", HTTP_GET, handleRoot);
    server.on("/calibrate_48h", HTTP_GET, handleStartCalibration48h);
    server.on("/calibrate_1h", HTTP_GET, handleStartCalibration1h);
    server.on("/calibrate_10m", HTTP_GET, handleStartCalibration10m);
    server.on("/stop_calibration", HTTP_GET, handleStopCalibration);
    server.on("/calibration_status", HTTP_GET, handleCalibrationStatus);
    server.on("/sensor_data", HTTP_GET, handleSensorData);
    server.on("/get_saved_data", HTTP_GET, handleGetSavedData);
    server.on("/clear_eeprom", HTTP_GET, []() {
        clearEEPROM();
        server.send(200, "text/plain", "EEPROM cleared");
    });
    
    server.begin();
    Serial.println(F("Web server started"));
}

/**
 * Handle root page - show calibration interface
 */
void handleRoot() {
    server.send(200, "text/html", getHTML());
}

/**
 * Handle start 48-hour calibration request
 */
void handleStartCalibration48h() {
    if (!isCalibrating) {
        isCalibrating = true;
        calibrationStartTime = millis();
        calibrationDuration = CALIBRATION_DURATION_48H;
        calibrationSumMQ135 = 0;
        calibrationSumMQ136 = 0;
        calibrationSumMQ137 = 0;
        calibrationCount = 0;
        
        // Save to EEPROM
        EEPROM.writeByte(EEPROM_CALIBRATION_ACTIVE, 1);
        EEPROM.put(EEPROM_CALIBRATION_START_TIME, calibrationStartTime);
        EEPROM.put(EEPROM_CALIBRATION_DURATION, calibrationDuration);
        EEPROM.commit();
        
        Serial.println(F("\n48-Hour Calibration started..."));
        Serial.println(F("Place device in balcony with fresh air"));
    }
    
    server.send(200, "text/plain", "48-Hour Calibration started");
}

/**
 * Handle start 1-hour calibration request
 */
void handleStartCalibration1h() {
    if (!isCalibrating) {
        isCalibrating = true;
        calibrationStartTime = millis();
        calibrationDuration = 60UL * 60UL * 1000UL;  // 1 hour
        calibrationSumMQ135 = 0;
        calibrationSumMQ136 = 0;
        calibrationSumMQ137 = 0;
        calibrationCount = 0;
        
        // Save to EEPROM
        EEPROM.writeByte(EEPROM_CALIBRATION_ACTIVE, 1);
        EEPROM.put(EEPROM_CALIBRATION_START_TIME, calibrationStartTime);
        EEPROM.put(EEPROM_CALIBRATION_DURATION, calibrationDuration);
        EEPROM.commit();
        
        Serial.println(F("\n1-Hour Calibration started..."));
    }
    
    server.send(200, "text/plain", "1-Hour Calibration started");
}

/**
 * Handle start 10-minute calibration request
 */
void handleStartCalibration10m() {
    if (!isCalibrating) {
        isCalibrating = true;
        calibrationStartTime = millis();
        calibrationDuration = 10UL * 60UL * 1000UL;  // 10 minutes
        calibrationSumMQ135 = 0;
        calibrationSumMQ136 = 0;
        calibrationSumMQ137 = 0;
        calibrationCount = 0;
        
        // Save to EEPROM
        EEPROM.writeByte(EEPROM_CALIBRATION_ACTIVE, 1);
        EEPROM.put(EEPROM_CALIBRATION_START_TIME, calibrationStartTime);
        EEPROM.put(EEPROM_CALIBRATION_DURATION, calibrationDuration);
        EEPROM.commit();
        
        Serial.println(F("\n10-Minute Calibration started..."));
    }
    
    server.send(200, "text/plain", "10-Minute Calibration started");
}

/**
 * Handle stop calibration request
 */
void handleStopCalibration() {
    if (isCalibrating) {
        isCalibrating = false;
        EEPROM.writeByte(EEPROM_CALIBRATION_ACTIVE, 0);
        EEPROM.commit();
        
        Serial.println(F("\nCalibration stopped by user"));
    }
    
    server.send(200, "text/plain", "Calibration stopped");
}

/**
 * Handle calibration status request
 */
void handleCalibrationStatus() {
    String status;
    
    if (isCalibrating) {
        unsigned long elapsed = millis() - calibrationStartTime;
        unsigned long remaining = (calibrationDuration - elapsed) / 1000;
        unsigned long totalSeconds = calibrationDuration / 1000;
        unsigned long elapsedSeconds = elapsed / 1000;
        int progress = (int)((elapsedSeconds * 100) / totalSeconds);
        
        status = String("{\"calibrating\":true,\"remaining\":") + String(remaining) + 
                  String(",\"progress\":") + String(progress) + 
                  String(",\"totalSeconds\":") + String(totalSeconds) + 
                  String(",\"startTime\":") + String(calibrationStartTime) + 
                  String(",\"saved12h\":") + String(saved12h ? "true" : "false") + 
                  String(",\"saved24h\":") + String(saved24h ? "true" : "false") + 
                  String(",\"saved48h\":") + String(saved48h ? "true" : "false") + "}";
    } else {
        status = String("{\"calibrating\":false,") +
                  String("\"saved12h\":") + String(saved12h ? "true" : "false") + 
                  String(",\"saved24h\":") + String(saved24h ? "true" : "false") + 
                  String(",\"saved48h\":") + String(saved48h ? "true" : "false") + "}";
    }
    
    server.send(200, "application/json", status);
}

/**
 * Handle get saved data request
 */
void handleGetSavedData() {
    String data = String("{") +
                  String("\"saved12h\":") + String(saved12h ? "true" : "false") + 
                  String(",\"r0_12h\":{\"mq135\":") + String(r0_12h_MQ135, 2) + 
                  String(",\"mq136\":") + String(r0_12h_MQ136, 2) + 
                  String(",\"mq137\":") + String(r0_12h_MQ137, 2) + 
                  String("},") +
                  String("\"saved24h\":") + String(saved24h ? "true" : "false") + 
                  String(",\"r0_24h\":{\"mq135\":") + String(r0_24h_MQ135, 2) + 
                  String(",\"mq136\":") + String(r0_24h_MQ136, 2) + 
                  String(",\"mq137\":") + String(r0_24h_MQ137, 2) + 
                  String("},") +
                  String("\"saved48h\":") + String(saved48h ? "true" : "false") + 
                  String(",\"r0_48h\":{\"mq135\":") + String(r0_48h_MQ135, 2) + 
                  String(",\"mq136\":") + String(r0_48h_MQ136, 2) + 
                  String(",\"mq137\":") + String(r0_48h_MQ137, 2) + 
                  String("}}");
    
    server.send(200, "application/json", data);
}

/**
 * Handle sensor data request
 */
void handleSensorData() {
    int adcValueMQ135 = analogRead(MQ135_PIN);
    float voltageMQ135 = (adcValueMQ135 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float rsMQ135 = calculateRS(voltageMQ135);
    float mq135_co2PPM = calculatePPM(rsMQ135, MQ135_CO2_A, MQ135_CO2_B, MQ135_R0);
    float mq135_nh3PPM = calculatePPM(rsMQ135, MQ135_NH3_A, MQ135_NH3_B, MQ135_R0);
    
    int adcValueMQ136 = analogRead(MQ136_PIN);
    float voltageMQ136 = (adcValueMQ136 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float rsMQ136 = calculateRS(voltageMQ136);
    float mq136_h2sPPM = calculatePPM(rsMQ136, MQ136_H2S_A, MQ136_H2S_B, MQ136_R0);
    float mq136_nh3PPM = calculatePPM(rsMQ136, MQ136_NH3_A, MQ136_NH3_B, MQ136_R0);
    float mq136_coPPM = calculatePPM(rsMQ136, MQ136_CO_A, MQ136_CO_B, MQ136_R0);
    
    int adcValueMQ137 = analogRead(MQ137_PIN);
    float voltageMQ137 = (adcValueMQ137 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float rsMQ137 = calculateRS(voltageMQ137);
    float mq137_nh3PPM = calculatePPM(rsMQ137, MQ137_NH3_A, MQ137_NH3_B, MQ137_R0);
    
    String data = String("{") +
                   String("\"mq135\":{") +
                   String("\"adc\":") + String(adcValueMQ135) + 
                   String(",\"voltage\":") + String(voltageMQ135, 3) + 
                   String(",\"rs\":") + String(rsMQ135, 2) + 
                   String(",\"co2\":") + String(mq135_co2PPM, 2) + 
                   String(",\"nh3\":") + String(mq135_nh3PPM, 2) + 
                   String("},") +
                   String("\"mq136\":{") +
                   String("\"adc\":") + String(adcValueMQ136) + 
                   String(",\"voltage\":") + String(voltageMQ136, 3) + 
                   String(",\"rs\":") + String(rsMQ136, 2) + 
                   String(",\"h2s\":") + String(mq136_h2sPPM, 2) + 
                   String(",\"nh3\":") + String(mq136_nh3PPM, 2) + 
                   String(",\"co\":") + String(mq136_coPPM, 2) + 
                   String("},") +
                   String("\"mq137\":{") +
                   String("\"adc\":") + String(adcValueMQ137) + 
                   String(",\"voltage\":") + String(voltageMQ137, 3) + 
                   String(",\"rs\":") + String(rsMQ137, 2) + 
                   String(",\"nh3\":") + String(mq137_nh3PPM, 2) + 
                   String("}}");
    
    server.send(200, "application/json", data);
}

/**
 * Generate HTML page for calibration interface
 */
String getHTML() {
    String html = R"(<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>MQ Sensors Calibration</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .section {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .section-title {
            font-weight: bold;
            color: #495057;
            margin-bottom: 15px;
            font-size: 16px;
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #dee2e6;
        }
        .data-row:last-child {
            border-bottom: none;
        }
        .data-label {
            color: #6c757d;
            font-size: 14px;
        }
        .data-value {
            font-weight: bold;
            color: #495057;
            font-size: 14px;
        }
        .status {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 20px;
        }
        .status.idle {
            background: #e9ecef;
            color: #495057;
        }
        .status.calibrating {
            background: #fff3cd;
            color: #856404;
        }
        .status.complete {
            background: #d4edda;
            color: #155724;
        }
        .btn {
            display: block;
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 10px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        .btn-secondary:hover {
            background: #5a6268;
        }
        .btn-warning {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        .btn-warning:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(240, 147, 251, 0.4);
        }
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        .btn-success {
            background: #28a745;
            color: white;
        }
        .btn-success:hover {
            background: #218838;
        }
        .btn-info {
            background: #17a2b8;
            color: white;
        }
        .btn-info:hover {
            background: #138496;
        }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            margin-bottom: 20px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.5s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        .result-box {
            background: #d4edda;
            border: 2px solid #c3e6cb;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
        }
        .result-label {
            color: #155724;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .result-value {
            color: #155724;
            font-size: 24px;
            font-weight: bold;
        }
        .result-unit {
            color: #155724;
            font-size: 14px;
        }
        .instructions {
            background: #fff3cd;
            border: 2px solid #ffeeba;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .instructions-title {
            color: #856404;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .instructions-list {
            color: #856404;
            font-size: 14px;
            line-height: 1.6;
        }
        .instructions-list li {
            margin-bottom: 5px;
        }
        .meat-status {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 20px;
            margin-top: 10px;
        }
        .meat-status.fresh {
            background: #d4edda;
            color: #155724;
        }
        .meat-status.good {
            background: #cce5ff;
            color: #004085;
        }
        .meat-status.moderate {
            background: #fff3cd;
            color: #856404;
        }
        .meat-status.spoiled {
            background: #f8d7da;
            color: #721c24;
        }
        .sensor-card {
            background: white;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .sensor-title {
            font-weight: bold;
            color: #495057;
            margin-bottom: 10px;
            font-size: 16px;
        }
        .saved-data-section {
            background: #e7f3ff;
            border: 2px solid #b197fc;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .saved-data-title {
            color: #3f2b96;
            font-weight: bold;
            margin-bottom: 15px;
            font-size: 16px;
        }
        .saved-data-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #b197fc;
        }
        .saved-data-row:last-child {
            border-bottom: none;
        }
        .time-info {
            text-align: center;
            color: #666;
            margin-bottom: 15px;
            font-size: 14px;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal-content {
            background: white;
            border-radius: 20px;
            padding: 30px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .modal-title {
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }
        .close-btn {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #666;
        }
        .close-btn:hover {
            color: #333;
        }
    </style>
</head>
<body>
    <div class='container'>
        <h1>MQ Sensors Calibration</h1>
        <p class='subtitle'>MQ135 + MQ136 + MQ137 Combined Calibration Tool with EEPROM Storage</p>
        
        <div class='instructions'>
            <div class='instructions-title'>📋 48-Hour Calibration Instructions:</div>
            <ol class='instructions-list'>
                <li>Place ALL sensors in CLEAN FRESH AIR (outdoor balcony recommended)</li>
                <li>Ensure good air circulation around sensors</li>
                <li>Click "Start 48-Hour Calibration" button below</li>
                <li>Leave device undisturbed for 48 hours</li>
                <li>Data saved automatically at 12h, 24h, and 48h intervals</li>
                <li>Disconnect from WiFi - calibration continues in background!</li>
                <li>Reconnect anytime to check progress or view saved data</li>
                <li>After 48 hours, copy R0 values from saved data</li>
                <li>Update R0 constants in your code</li>
            </ol>
        </div>
        
        <div id='status' class='status idle'>Ready to Calibrate</div>
        
        <div id='timeInfo' class='time-info' style='display:none;'>
            Calibration started: <span id='startTime'>--</span>
        </div>
        
        <div id='progressContainer' style='display:none;'>
            <div class='progress-bar'>
                <div id='progressFill' class='progress-fill' style='width: 0%'>0%</div>
            </div>
            <p style='text-align: center; color: #666; margin-bottom: 20px;'>
                Time remaining: <span id='timeRemaining'>--:--:--</span>
            </p>
            <p style='text-align: center; color: #666; margin-bottom: 10px;'>
                <strong>Next save in:</strong> <span id='nextSave'>--</span>
            </p>
        </div>
        
        <div id='savedDataSection' class='saved-data-section' style='display:none;'>
            <div class='saved-data-title'>💾 Saved Calibration Data</div>
            <p style='text-align: center; color: #3f2b96; margin-bottom: 15px; font-size: 14px;'>
                Click buttons below to view saved R0 values
            </p>
            <button id='btn12h' class='btn btn-info' onclick='showSavedData(12)' disabled>View 12h Data</button>
            <button id='btn24h' class='btn btn-success' onclick='showSavedData(24)' disabled>View 24h Data</button>
            <button id='btn48h' class='btn btn-primary' onclick='showSavedData(48)' disabled>View 48h Data</button>
        </div>
        
        <button id='calibrateBtn48h' class='btn btn-primary' onclick='startCalibration48h()'>Start 48-Hour Calibration</button>
        <button id='calibrateBtn1h' class='btn btn-warning' onclick='startCalibration1h()'>Start 1-Hour Calibration (Quick Test)</button>
        <button id='calibrateBtn10m' class='btn btn-warning' onclick='startCalibration10m()'>Start 10-Minute Calibration (Demo)</button>
        <button id='stopBtn' class='btn btn-danger' onclick='stopCalibration()' style='display:none;'>Stop Calibration</button>
        <button class='btn btn-secondary' onclick='location.reload()'>Refresh</button>
        <button class='btn btn-secondary' onclick='clearEEPROM()' style='margin-top: 10px;'>Clear EEPROM (Factory Reset)</button>
        
        <div class='section'>
            <div class='section-title'>📊 Sensor Readings</div>
            
            <div class='sensor-card'>
                <div class='sensor-title'>MQ135 (CO2/NH3)</div>
                <div class='data-row'>
                    <span class='data-label'>ADC Value:</span>
                    <span class='data-value' id='mq135_adc'>--</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>Voltage:</span>
                    <span class='data-value' id='mq135_voltage'>-- V</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>Rs:</span>
                    <span class='data-value' id='mq135_rs'>-- Ω</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>CO2:</span>
                    <span class='data-value' id='mq135_co2'>-- ppm</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>NH3:</span>
                    <span class='data-value' id='mq135_nh3'>-- ppm</span>
                </div>
            </div>
            
            <div class='sensor-card'>
                <div class='sensor-title'>MQ136 (H2S/NH3/CO)</div>
                <div class='data-row'>
                    <span class='data-label'>ADC Value:</span>
                    <span class='data-value' id='mq136_adc'>--</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>Voltage:</span>
                    <span class='data-value' id='mq136_voltage'>-- V</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>Rs:</span>
                    <span class='data-value' id='mq136_rs'>-- Ω</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>H2S:</span>
                    <span class='data-value' id='mq136_h2s'>-- ppm</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>NH3:</span>
                    <span class='data-value' id='mq136_nh3'>-- ppm</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>CO:</span>
                    <span class='data-value' id='mq136_co'>-- ppm</span>
                </div>
            </div>
            
            <div class='sensor-card'>
                <div class='sensor-title'>MQ137 (NH3)</div>
                <div class='data-row'>
                    <span class='data-label'>ADC Value:</span>
                    <span class='data-value' id='mq137_adc'>--</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>Voltage:</span>
                    <span class='data-value' id='mq137_voltage'>-- V</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>Rs:</span>
                    <span class='data-value' id='mq137_rs'>-- Ω</span>
                </div>
                <div class='data-row'>
                    <span class='data-label'>NH3:</span>
                    <span class='data-value' id='mq137_nh3'>-- ppm</span>
                </div>
            </div>
            
            <div id='meatStatus' class='meat-status fresh' style='display:none;'>--</div>
        </div>
    </div>

    <div id='savedDataModal' class='modal'>
        <div class='modal-content'>
            <div class='modal-header'>
                <div class='modal-title' id='modalTitle'>Saved Calibration Data</div>
                <button class='close-btn' onclick='closeModal()'>&times;</button>
            </div>
            <div id='modalBody'></div>
        </div>
    </div>

    <script>
        const MQ135_R0_VALUE = )" + String(MQ135_R0, 2) + R"(;
        const MQ136_R0_VALUE = )" + String(MQ136_R0, 2) + R"(;
        const MQ137_R0_VALUE = )" + String(MQ137_R0, 2) + R"(;
        
        let savedData = null;
        
        function formatTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        
        function formatStartTime(timestamp) {
            // timestamp is millis() value (relative time), not Unix timestamp
            // Return a placeholder since we can't determine actual date without RTC/NTP
            return 'Calibration in progress';
        }
        
        function startCalibration48h() {
            fetch('/calibrate_48h')
                .then(response => response.text())
                .then(data => {
                    disableAllButtons();
                    document.getElementById('status').className = 'status calibrating';
                    document.getElementById('status').textContent = 'Calibrating (48 Hours)...';
                    document.getElementById('stopBtn').style.display = 'block';
                    checkCalibrationStatus();
                });
        }
        
        function startCalibration1h() {
            fetch('/calibrate_1h')
                .then(response => response.text())
                .then(data => {
                    disableAllButtons();
                    document.getElementById('status').className = 'status calibrating';
                    document.getElementById('status').textContent = 'Calibrating (1 Hour)...';
                    document.getElementById('stopBtn').style.display = 'block';
                    checkCalibrationStatus();
                });
        }
        
        function startCalibration10m() {
            fetch('/calibrate_10m')
                .then(response => response.text())
                .then(data => {
                    disableAllButtons();
                    document.getElementById('status').className = 'status calibrating';
                    document.getElementById('status').textContent = 'Calibrating (10 Minutes)...';
                    document.getElementById('stopBtn').style.display = 'block';
                    checkCalibrationStatus();
                });
        }
        
        function stopCalibration() {
            if (confirm('Are you sure you want to stop calibration?')) {
                fetch('/stop_calibration')
                    .then(response => response.text())
                    .then(data => {
                        location.reload();
                    });
            }
        }
        
        function clearEEPROM() {
            if (confirm('Are you sure you want to clear EEPROM? This will delete all saved calibration data!')) {
                fetch('/clear_eeprom')
                    .then(response => response.text())
                    .then(data => {
                        alert('EEPROM cleared! Page will reload.');
                        location.reload();
                    });
            }
        }
        
        function disableAllButtons() {
            document.getElementById('calibrateBtn48h').disabled = true;
            document.getElementById('calibrateBtn1h').disabled = true;
            document.getElementById('calibrateBtn10m').disabled = true;
        }
        
        function enableAllButtons() {
            document.getElementById('calibrateBtn48h').disabled = false;
            document.getElementById('calibrateBtn1h').disabled = false;
            document.getElementById('calibrateBtn10m').disabled = false;
        }
        
        function checkCalibrationStatus() {
            fetch('/calibration_status')
                .then(response => response.json())
                .then(data => {
                    if (data.calibrating) {
                        document.getElementById('progressFill').style.width = data.progress + '%';
                        document.getElementById('progressFill').textContent = data.progress + '%';
                        document.getElementById('timeRemaining').textContent = formatTime(data.remaining);
                        document.getElementById('timeInfo').style.display = 'block';
                        document.getElementById('startTime').textContent = formatStartTime(data.startTime);
                        document.getElementById('progressContainer').style.display = 'block';
                        document.getElementById('savedDataSection').style.display = 'block';
                        
                        // Update saved data buttons
                        document.getElementById('btn12h').disabled = !data.saved12h;
                        document.getElementById('btn24h').disabled = !data.saved24h;
                        document.getElementById('btn48h').disabled = !data.saved48h;
                        
                        // Calculate next save time based on remaining time
                        // Use the remaining time directly from the server
                        const elapsedSeconds = data.totalSeconds - data.remaining;
                        let nextSaveText = '--';
                        
                        if (!data.saved12h) {
                            const remaining12h = (12 * 3600) - elapsedSeconds;
                            if (remaining12h > 0) {
                                nextSaveText = formatTime(Math.floor(remaining12h)) + ' (12h data)';
                            }
                        } else if (!data.saved24h) {
                            const remaining24h = (24 * 3600) - elapsedSeconds;
                            if (remaining24h > 0) {
                                nextSaveText = formatTime(Math.floor(remaining24h)) + ' (24h data)';
                            }
                        } else if (!data.saved48h) {
                            const remaining48h = (48 * 3600) - elapsedSeconds;
                            if (remaining48h > 0) {
                                nextSaveText = formatTime(Math.floor(remaining48h)) + ' (48h data)';
                            }
                        }
                        
                        document.getElementById('nextSave').textContent = nextSaveText;
                        
                        setTimeout(checkCalibrationStatus, 1000);
                    } else {
                        document.getElementById('progressContainer').style.display = 'none';
                        document.getElementById('timeInfo').style.display = 'none';
                        document.getElementById('status').className = 'status complete';
                        document.getElementById('status').textContent = 'Calibration Complete!';
                        document.getElementById('stopBtn').style.display = 'none';
                        enableAllButtons();
                        
                        // Show saved data section
                        document.getElementById('savedDataSection').style.display = 'block';
                        document.getElementById('btn12h').disabled = !data.saved12h;
                        document.getElementById('btn24h').disabled = !data.saved24h;
                        document.getElementById('btn48h').disabled = !data.saved48h;
                    }
                });
        }
        
        function showSavedData(hours) {
            fetch('/get_saved_data')
                .then(response => response.json())
                .then(data => {
                    let title, r0Data;
                    
                    if (hours === 12) {
                        title = '12-Hour Calibration Data';
                        r0Data = data.r0_12h;
                    } else if (hours === 24) {
                        title = '24-Hour Calibration Data';
                        r0Data = data.r0_24h;
                    } else if (hours === 48) {
                        title = '48-Hour Calibration Data';
                        r0Data = data.r0_48h;
                    }
                    
                    document.getElementById('modalTitle').textContent = title;
                    document.getElementById('modalBody').innerHTML = `
                        <div class='result-box'>
                            <div class='result-label'>R0 Values (Ω)</div>
                            <div style='margin: 15px 0;'>
                                <div style='margin-bottom: 10px;'>
                                    <span class='result-value'>${r0Data.mq135.toFixed(2)}</span>
                                    <span class='result-unit'>Ω (MQ135)</span>
                                </div>
                                <div style='margin-bottom: 10px;'>
                                    <span class='result-value'>${r0Data.mq136.toFixed(2)}</span>
                                    <span class='result-unit'>Ω (MQ136)</span>
                                </div>
                                <div>
                                    <span class='result-value'>${r0Data.mq137.toFixed(2)}</span>
                                    <span class='result-unit'>Ω (MQ137)</span>
                                </div>
                            </div>
                        </div>
                        <p style='text-align: center; color: #666; margin-top: 15px; font-size: 14px;'>
                            Update these values in your code's R0 constants
                        </p>
                    `;
                    
                    document.getElementById('savedDataModal').style.display = 'flex';
                });
        }
        
        function closeModal() {
            document.getElementById('savedDataModal').style.display = 'none';
        }
        
        function updateSensorData() {
            fetch('/sensor_data')
                .then(response => response.json())
                .then(data => {
                    // MQ135
                    document.getElementById('mq135_adc').textContent = data.mq135.adc;
                    document.getElementById('mq135_voltage').textContent = data.mq135.voltage.toFixed(3) + ' V';
                    document.getElementById('mq135_rs').textContent = data.mq135.rs.toFixed(2) + ' Ω';
                    document.getElementById('mq135_co2').textContent = data.mq135.co2.toFixed(2) + ' ppm';
                    document.getElementById('mq135_nh3').textContent = data.mq135.nh3.toFixed(2) + ' ppm';
                    
                    // MQ136
                    document.getElementById('mq136_adc').textContent = data.mq136.adc;
                    document.getElementById('mq136_voltage').textContent = data.mq136.voltage.toFixed(3) + ' V';
                    document.getElementById('mq136_rs').textContent = data.mq136.rs.toFixed(2) + ' Ω';
                    document.getElementById('mq136_h2s').textContent = data.mq136.h2s.toFixed(2) + ' ppm';
                    document.getElementById('mq136_nh3').textContent = data.mq136.nh3.toFixed(2) + ' ppm';
                    document.getElementById('mq136_co').textContent = data.mq136.co.toFixed(2) + ' ppm';
                    
                    // MQ137
                    document.getElementById('mq137_adc').textContent = data.mq137.adc;
                    document.getElementById('mq137_voltage').textContent = data.mq137.voltage.toFixed(3) + ' V';
                    document.getElementById('mq137_rs').textContent = data.mq137.rs.toFixed(2) + ' Ω';
                    document.getElementById('mq137_nh3').textContent = data.mq137.nh3.toFixed(2) + ' ppm';
                    
                    // Combined meat quality assessment
                    const meatStatus = document.getElementById('meatStatus');
                    meatStatus.style.display = 'block';
                    
                    const fresh = (data.mq135.co2 < 600) && (data.mq136.h2s < 5) && (data.mq137.nh3 < 50);
                    const good = (data.mq135.co2 < 800) && (data.mq136.h2s < 10) && (data.mq137.nh3 < 100);
                    const moderate = (data.mq135.co2 < 1000) && (data.mq136.h2s < 20) && (data.mq137.nh3 < 200);
                    
                    if (fresh) {
                        meatStatus.className = 'meat-status fresh';
                        meatStatus.textContent = 'Status: FRESH';
                    } else if (good) {
                        meatStatus.className = 'meat-status good';
                        meatStatus.textContent = 'Status: GOOD';
                    } else if (moderate) {
                        meatStatus.className = 'meat-status moderate';
                        meatStatus.textContent = 'Status: MODERATE';
                    } else {
                        meatStatus.className = 'meat-status spoiled';
                        meatStatus.textContent = 'Status: SPOILED';
                    }
                });
        }
        
        // Initial check
        checkCalibrationStatus();
        
        // Update sensor data every 2 seconds
        setInterval(updateSensorData, 2000);
        updateSensorData();
    </script>
</body>
</html>)";
    
    return html;
}

/**
 * Calculate sensor resistance Rs from voltage
 * @param voltage Measured voltage from sensor
 * @return Sensor resistance in ohms
 */
float calculateRS(float voltage) {
    if (voltage <= 0) return 0;
    
    // Rs = ((Vcc - Vout) / Vout) * RL
    // Vcc = 5V (MQ sensor supply voltage)
    float rs = ((5.0 - voltage) / voltage) * RL;
    
    return rs;
}

/**
 * Calculate gas concentration in PPM
 * @param rs Sensor resistance
 * @param a Sensitivity curve parameter a
 * @param b Sensitivity curve parameter b
 * @param r0 Sensor resistance in clean air
 * @return Gas concentration in PPM
 */
float calculatePPM(float rs, float a, float b, float r0) {
    if (rs <= 0) return 0;
    
    // Rs/R0 = a * (ppm)^b
    // ppm = ((Rs/R0) / a)^(1/b)
    float ratio = rs / r0;
    float ppm = pow((ratio / a), (1.0 / b));
    
    return ppm;
}
