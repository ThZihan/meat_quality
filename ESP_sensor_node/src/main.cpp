/*
 * MQ135 + MQ136 + MQ137 Air Quality Sensor for ESP32 NodeMCU
 * MQTT Version - Sends data to Raspberry Pi
 * 
 * This code reads all three MQ sensors (MQ135, MQ136, MQ137) and sends
 * sensor readings to Raspberry Pi via MQTT protocol.
 * 
 * SENSOR DETECTION:
 * ================
 * - MQ135: VOC (General Spoilage Index)
 * - MQ136: H2S (Hydrogen Sulfide), NH3 (Ammonia), CO (Carbon Monoxide)
 * - MQ137: NH3 (Ammonia) - specialized ammonia detection
 * 
 * MQTT PROTOCOL:
 * =============
 * - Broker: Raspberry Pi IP address
 * - Topic: meat-quality/data
 * - Format: JSON with sensor readings and quality assessment
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
 * - Correction: Multiply by 1.5 to get actual sensor voltage
 * 
 * ESP32 NodeMCU Connections:
 * --------------------------
 * GPIO 34 (ADC1_CH6) → MQ135 Voltage Divider Output
 * GPIO 35 (ADC1_CH7) → MQ136 Voltage Divider Output
 * GPIO 32 (ADC1_CH4) → MQ137 Voltage Divider Output
 * 3.3V              → Not used (MQ sensors powered by 5V)
 * GND               → Common ground with all MQ sensors
 * 
 * IMPORTANT NOTES:
 * ================
 * 1. Use ADC1 pins (GPIO 34, 35, 36, 39) - ADC2 pins conflict with WiFi!
 * 2. All MQ sensors require 5V for heater - do NOT power from 3.3V
 * 3. Voltage dividers are MANDATORY to protect ESP32 from 5V
 * 4. Pre-heat sensors for 24-48 hours in fresh air for accurate readings
 * 5. ESP32 ADC is 12-bit (0-4095)
 * 6. R0 values are hardcoded from 24-hour burn-in calibration
 * 7. WiFi credentials must be configured below
 * 8. Raspberry Pi IP address must be configured below
 * 
 * CALIBRATION:
 * ============
 * R0 values from 24-hour burn-in in fresh air:
 * - MQ135 R0: 193200.00 Ω
 * - MQ136 R0: 85102.55 Ω
 * - MQ137 R0: 51913.09 Ω
 * 
 * MEAT QUALITY MONITORING:
 * ========================
 * Combined assessment using all sensors:
 * - Fresh meat: VOC < 600ppm, H2S < 5ppm, NH3 < 50ppm
 * - Good meat: VOC < 800ppm, H2S < 10ppm, NH3 < 100ppm
 * - Moderate: VOC < 1000ppm, H2S < 20ppm, NH3 < 200ppm
 * - Spoiled: Any sensor above thresholds
 * 
 * MQTT DATA FORMAT:
 * =================
 * {
 *   "timestamp": "2024-01-01T12:00:00Z",
 *   "device_id": "ESP32-MeatMonitor",
 *   "sensors": {
 *     "temperature": 25.5,
 *     "humidity": 60.0,
 *     "mq135_co2": 450.0,
 *     "mq136_h2s": 5.0,
 *     "mq137_nh3": 15.0
 *   },
 *   "quality": {
 *     "level": "EXCELLENT"
 *   },
 *   "wifi_rssi": -65,
 *   "sensor_status": {}
 * }
 */

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

// ===== WIFI CONFIGURATION =====
// CHANGE THESE TO MATCH YOUR NETWORK!
const char* ssid = "Lovly";           // Your WiFi network name
const char* password = "tweety@pichu";   // Your WiFi password

// ===== MQTT CONFIGURATION =====
// CHANGE THIS TO YOUR RASPBERRY PI IP ADDRESS!
const char* mqttBroker = "192.168.10.107";     // Raspberry Pi IP address
const int mqttPort = 1883;
const char* mqttTopic = "meat-quality/data";
const char* mqttClientId = "ESP32-MeatMonitor";
const char* mqttUser = "meat_monitor";
const char* mqttPassword = "meat_monitor";

// ===== HARDWARE CONFIGURATION =====
const int MQ135_PIN = 34;  // ADC1_CH6 - Safe with WiFi enabled
const int MQ136_PIN = 35;  // ADC1_CH7 - Safe with WiFi enabled
const int MQ137_PIN = 32;  // ADC1_CH4 - Safe with WiFi enabled
const float VOLTAGE_DIVIDER_RATIO = 1.5;  // 5V → 3.33V (multiply by 1.5 to correct)
const float ESP32_VREF = 3.3;  // ESP32 reference voltage
const int ADC_RESOLUTION = 4095;  // 12-bit ADC

// ===== MQ SENSOR PARAMETERS =====
// Load resistor value (on MQ modules, typically 10kΩ)
const float RL = 10000.0;  // 10kΩ

// Sensor resistance in clean air (from 24-hour burn-in calibration)
const float MQ135_R0 = 193200.00;  // From 24-Hour Burn-in
const float MQ136_R0 = 85102.55;   // From 24-Hour Burn-in
const float MQ137_R0 = 51913.09;   // From 24-Hour Burn-in

// MQ135 sensitivity curve parameters (from datasheet)
// Using CO2 curve for VOC (General Spoilage Index)
const float MQ135_VOC_A = 110.47;
const float MQ135_VOC_B = -2.862;
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

// ===== TIMING =====
const unsigned long READ_INTERVAL = 2000;  // Read every 2 seconds
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;  // Reconnect every 5 seconds
unsigned long lastReadTime = 0;
unsigned long lastReconnectAttempt = 0;

// ===== GLOBAL VARIABLES =====
WiFiClient espClient;
PubSubClient mqttClient(espClient);
bool wifiConnected = false;
bool mqttConnected = false;

// ===== FUNCTION PROTOTYPES =====
float calculatePPM(float rs, float a, float b, float r0);
float calculateRS(float voltage);
void setupWiFi();
void reconnectMQTT();
void sendSensorData(float mq135_vocPPM, float mq135_nh3PPM, 
                   float mq136_h2sPPM, float mq136_nh3PPM, float mq136_coPPM,
                   float mq137_nh3PPM, const char* qualityLevel);

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println(F("\n========================================"));
    Serial.println(F("MQ135 + MQ136 + MQ137 Combined Sensors"));
    Serial.println(F("ESP32 NodeMCU - MQTT Version"));
    Serial.println(F("========================================\n"));
    
    // Configure ADC
    analogReadResolution(12);  // 12-bit resolution (0-4095)
    analogSetAttenuation(ADC_11db);  // Full range: 0-3.3V
    
    // Setup WiFi
    setupWiFi();
    
    // Setup NTP for accurate time
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
    Serial.println(F("Waiting for NTP time sync..."));
    time_t now = time(nullptr);
    while (now < 8 * 3600 * 2) {
        delay(500);
        Serial.print(F("."));
        now = time(nullptr);
    }
    Serial.println(F(""));
    struct tm timeinfo;
    getLocalTime(&timeinfo);
    Serial.print(F("NTP time synchronized: "));
    Serial.println(asctime(&timeinfo));
    
    // Setup MQTT
    mqttClient.setServer(mqttBroker, mqttPort);
    mqttClient.setBufferSize(1024);  // Increase buffer size for larger JSON payloads
    
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
    
    // Print R0 values
    Serial.println(F("CALIBRATION R0 VALUES (from 24-hour burn-in):"));
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
    
    // Print MQTT configuration
    Serial.println(F("MQTT CONFIGURATION:"));
    Serial.print(F("  Broker: "));
    Serial.println(mqttBroker);
    Serial.print(F("  Port: "));
    Serial.println(mqttPort);
    Serial.print(F("  Topic: "));
    Serial.println(mqttTopic);
    Serial.println(F(""));
    
    // Print sensor preheat info
    Serial.println(F("SENSOR PREHEAT:"));
    Serial.println(F("For accurate readings, preheat for 24-48 hours"));
    Serial.println(F("in fresh air before monitoring meat quality"));
    Serial.println(F(""));
    
    Serial.println(F("Starting sensor readings...\n"));
}

void loop() {
    unsigned long currentTime = millis();
    
    // Maintain MQTT connection
    if (!mqttClient.connected()) {
        if (currentTime - lastReconnectAttempt >= MQTT_RECONNECT_INTERVAL) {
            lastReconnectAttempt = currentTime;
            reconnectMQTT();
        }
    } else {
        mqttClient.loop();
    }
    
    // Read sensor at specified interval
    if (currentTime - lastReadTime >= READ_INTERVAL) {
        lastReadTime = currentTime;
        
        // Read raw ADC values
        int adcValueMQ135 = analogRead(MQ135_PIN);
        int adcValueMQ136 = analogRead(MQ136_PIN);
        int adcValueMQ137 = analogRead(MQ137_PIN);
        
        // Calculate voltages (correct for voltage divider)
        float voltageMQ135 = (adcValueMQ135 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float voltageMQ136 = (adcValueMQ136 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float voltageMQ137 = (adcValueMQ137 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        
        // Calculate sensor resistance
        float rsMQ135 = calculateRS(voltageMQ135);
        float rsMQ136 = calculateRS(voltageMQ136);
        float rsMQ137 = calculateRS(voltageMQ137);
        
        // Calculate PPM values
        float mq135_vocPPM = calculatePPM(rsMQ135, MQ135_VOC_A, MQ135_VOC_B, MQ135_R0);
        float mq135_nh3PPM = calculatePPM(rsMQ135, MQ135_NH3_A, MQ135_NH3_B, MQ135_R0);
        
        float mq136_h2sPPM = calculatePPM(rsMQ136, MQ136_H2S_A, MQ136_H2S_B, MQ136_R0);
        float mq136_nh3PPM = calculatePPM(rsMQ136, MQ136_NH3_A, MQ136_NH3_B, MQ136_R0);
        float mq136_coPPM = calculatePPM(rsMQ136, MQ136_CO_A, MQ136_CO_B, MQ136_R0);
        
        float mq137_nh3PPM = calculatePPM(rsMQ137, MQ137_NH3_A, MQ137_NH3_B, MQ137_R0);
        
        // Print to Serial Monitor
        Serial.println(F("========================================"));
        Serial.println(F("SENSOR READINGS:"));
        Serial.println(F("----------------------------------------"));
        
        // MQ135 (VOC/NH3)
        Serial.println(F("MQ135 (VOC/NH3):"));
        Serial.print(F("  ADC: "));
        Serial.print(adcValueMQ135);
        Serial.print(F(", Voltage: "));
        Serial.print(voltageMQ135, 3);
        Serial.print(F(" V, Rs: "));
        Serial.print(rsMQ135);
        Serial.println(F(" Ω"));
        Serial.print(F("  VOC (Spoilage Index): "));
        Serial.print(mq135_vocPPM, 2);
        Serial.println(F(" ppm"));
        Serial.print(F("  NH3: "));
        Serial.print(mq135_nh3PPM, 2);
        Serial.println(F(" ppm"));
        Serial.println(F(""));
        
        // MQ136 (H2S/NH3/CO)
        Serial.println(F("MQ136 (H2S/NH3/CO):"));
        Serial.print(F("  ADC: "));
        Serial.print(adcValueMQ136);
        Serial.print(F(", Voltage: "));
        Serial.print(voltageMQ136, 3);
        Serial.print(F(" V, Rs: "));
        Serial.print(rsMQ136);
        Serial.println(F(" Ω"));
        Serial.print(F("  H2S: "));
        Serial.print(mq136_h2sPPM, 2);
        Serial.println(F(" ppm"));
        Serial.print(F("  NH3: "));
        Serial.print(mq136_nh3PPM, 2);
        Serial.println(F(" ppm"));
        Serial.print(F("  CO: "));
        Serial.print(mq136_coPPM, 2);
        Serial.println(F(" ppm"));
        Serial.println(F(""));
        
        // MQ137 (NH3)
        Serial.println(F("MQ137 (NH3):"));
        Serial.print(F("  ADC: "));
        Serial.print(adcValueMQ137);
        Serial.print(F(", Voltage: "));
        Serial.print(voltageMQ137, 3);
        Serial.print(F(" V, Rs: "));
        Serial.print(rsMQ137);
        Serial.println(F(" Ω"));
        Serial.print(F("  NH3: "));
        Serial.print(mq137_nh3PPM, 2);
        Serial.println(F(" ppm"));
        Serial.println(F(""));
        
        // Combined meat quality assessment
        Serial.println(F("----------------------------------------"));
        Serial.println(F("MEAT QUALITY ASSESSMENT:"));
        Serial.println(F("----------------------------------------"));
        
        bool fresh = (mq135_vocPPM < 600) && (mq136_h2sPPM < 5) && (mq137_nh3PPM < 50);
        bool good = (mq135_vocPPM < 800) && (mq136_h2sPPM < 10) && (mq137_nh3PPM < 100);
        bool moderate = (mq135_vocPPM < 1000) && (mq136_h2sPPM < 20) && (mq137_nh3PPM < 200);
        
        Serial.print(F("  VOC: "));
        Serial.print(mq135_vocPPM, 2);
        Serial.print(F(" ppm (Threshold: "));
        Serial.print(fresh ? "< 600" : (good ? "< 800" : (moderate ? "< 1000" : "> 1000")));
        Serial.println(F(")"));
        
        Serial.print(F("  H2S: "));
        Serial.print(mq136_h2sPPM, 2);
        Serial.print(F(" ppm (Threshold: "));
        Serial.print(fresh ? "< 5" : (good ? "< 10" : (moderate ? "< 20" : "> 20")));
        Serial.println(F(")"));
        
        Serial.print(F("  NH3: "));
        Serial.print(mq137_nh3PPM, 2);
        Serial.print(F(" ppm (Threshold: "));
        Serial.print(fresh ? "< 50" : (good ? "< 100" : (moderate ? "< 200" : "> 200")));
        Serial.println(F(")"));
        
        Serial.println(F(""));
        Serial.print(F("  Status: "));
        
        const char* qualityLevel;
        
        if (fresh) {
            qualityLevel = "EXCELLENT";
            Serial.println(F("EXCELLENT (Fresh)"));
            Serial.println(F("  → All gas levels are normal"));
        } else if (good) {
            qualityLevel = "GOOD";
            Serial.println(F("GOOD"));
            Serial.println(F("  → Gas levels slightly elevated"));
        } else if (moderate) {
            qualityLevel = "FAIR";
            Serial.println(F("FAIR (Moderate)"));
            Serial.println(F("  → Gas levels elevated - monitor closely"));
        } else {
            qualityLevel = "SPOILED";
            Serial.println(F("SPOILED"));
            Serial.println(F("  → High gas levels - meat may be spoiled"));
        }
        
        Serial.println(F("========================================\n"));
        
        // Send data via MQTT if connected
        if (mqttClient.connected()) {
            // Small delay to ensure WiFi/MQTT is ready
            delay(10);
            // Ensure MQTT client loop is processed before publishing
            mqttClient.loop();
            sendSensorData(mq135_vocPPM, mq135_nh3PPM,
                         mq136_h2sPPM, mq136_nh3PPM, mq136_coPPM,
                         mq137_nh3PPM, qualityLevel);
        } else {
            Serial.println(F("MQTT not connected - skipping data send"));
        }
    }
}

/**
 * Setup WiFi connection
 */
void setupWiFi() {
    Serial.println(F("Connecting to WiFi..."));
    Serial.print(F("SSID: "));
    Serial.println(ssid);
    
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(F("."));
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        Serial.println(F(""));
        Serial.print(F("WiFi connected! IP address: "));
        Serial.println(WiFi.localIP());
        Serial.print(F("Signal strength (RSSI): "));
        Serial.print(WiFi.RSSI());
        Serial.println(F(" dBm"));
    } else {
        wifiConnected = false;
        Serial.println(F(""));
        Serial.println(F("WiFi connection failed!"));
        Serial.println(F("Check your WiFi credentials and try again."));
    }
    Serial.println(F(""));
}

/**
 * Reconnect to MQTT broker
 */
void reconnectMQTT() {
    Serial.println(F("Attempting MQTT connection..."));
    
    if (mqttClient.connect(mqttClientId, mqttUser, mqttPassword)) {
        mqttConnected = true;
        Serial.println(F("MQTT connected!"));
        Serial.print(F("Connected to broker: "));
        Serial.println(mqttBroker);
    } else {
        mqttConnected = false;
        Serial.print(F("MQTT connection failed, rc="));
        Serial.print(mqttClient.state());
        Serial.println(F(" - retrying in 5 seconds"));
    }
}

/**
 * Send sensor data via MQTT
 */
void sendSensorData(float mq135_vocPPM, float mq135_nh3PPM, 
                   float mq136_h2sPPM, float mq136_nh3PPM, float mq136_coPPM,
                   float mq137_nh3PPM, const char* qualityLevel) {
    // Create JSON document
    StaticJsonDocument<512> doc;
    
    // Add timestamp (ISO 8601 format)
    char timestamp[32];
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
        strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    } else {
        strcpy(timestamp, "1970-01-01T00:00:00Z");  // Fallback if time not available
    }
    doc["timestamp"] = timestamp;
    
    // Add device ID
    doc["device_id"] = mqttClientId;
    
    // Add sensor readings
    JsonObject sensors = doc.createNestedObject("sensors");
    
    // Temperature and humidity - placeholder values (no sensor connected)
    // TODO: Add DHT11/DHT22/AHT10 sensor for real temperature/humidity readings
    sensors["temperature"] = 25.0;  // Placeholder: 25°C
    sensors["humidity"] = 60.0;      // Placeholder: 60%
    
    // Gas sensor readings
    sensors["mq135_co2"] = mq135_vocPPM;  // Using VOC as CO2 proxy
    sensors["mq136_h2s"] = mq136_h2sPPM;
    sensors["mq137_nh3"] = mq137_nh3PPM;
    
    // Add quality assessment
    JsonObject quality = doc.createNestedObject("quality");
    quality["level"] = qualityLevel;
    
    // Add WiFi signal strength
    doc["wifi_rssi"] = WiFi.RSSI();
    
    // Add sensor status (empty object for now)
    JsonObject sensorStatus = doc.createNestedObject("sensor_status");
    // Can add individual sensor status here if needed
    
    // Serialize JSON to string
    char jsonBuffer[512];
    serializeJson(doc, jsonBuffer);
    
    // Publish to MQTT topic
    if (mqttClient.publish(mqttTopic, jsonBuffer)) {
        Serial.println(F("Data sent via MQTT successfully"));
    } else {
        Serial.println(F("Failed to send data via MQTT"));
        Serial.print(F("MQTT connected: "));
        Serial.println(mqttClient.connected() ? "Yes" : "No");
        Serial.print(F("MQTT state: "));
        Serial.println(mqttClient.state());
        Serial.print(F("Payload length: "));
        Serial.println(strlen(jsonBuffer));
        Serial.print(F("Free heap: "));
        Serial.println(ESP.getFreeHeap());
    }
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
