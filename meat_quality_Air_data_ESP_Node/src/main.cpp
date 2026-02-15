#include <Arduino.h>
#include <WiFi.h>
#include <Adafruit_AHTX0.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// I2C pins for ESP32 NodeMCU
// SDA: GPIO 21, SCL: GPIO 22 (default I2C pins)
// Note: GPIO 21, 22 are safe for WiFi use
const int I2C_SDA = 21;
const int I2C_SCL = 22;

// MQ Sensor Analog Pins (ADC1 - Safe for WiFi use)
// ADC1 pins (GPIO 34, 35, 36, 39) work with WiFi enabled
// ADC2 pins (GPIO 32, 33) DO NOT work with WiFi - AVOID!
const int MQ135_PIN = 34;  // ADC1_CH6 - CO2/VOCs sensor
const int MQ136_PIN = 35;  // ADC1_CH7 - H2S sensor
const int MQ137_PIN = 36;  // ADC1_CH0 - NH3 sensor

// WiFi credentials
const char* ssid = "Lovly";
const char* password = "tweety@pichu";

// MQTT Broker Settings
// IMPORTANT: Update this IP address to your Raspberry Pi's IP address
// To find your Raspberry Pi IP: Run 'hostname -I' on the Raspberry Pi
const char* mqttBroker = "192.168.10.107";  // Raspberry Pi IP - CHANGE THIS!
const int mqttPort = 1883;
const char* mqttClientId = "ESP32-MeatMonitor";
const char* mqttUser = "meat_monitor";      // MQTT username - CHANGE THIS!
const char* mqttPassword = "meat_monitor";  // MQTT password - CHANGE THIS!

// MQTT Topics
const char* topicData = "meat-quality/data";
const char* topicStatus = "meat-quality/status";
const char* topicLWT = "meat-quality/lwt";  // Last Will and Testament

// MQTT QoS and Retain settings
const int mqttQoS = 1;  // 0=at most once, 1=at least once, 2=exactly once
const bool mqttRetain = true;  // Retain last message

// WiFi and MQTT clients
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// AHT10 sensor object
Adafruit_AHTX0 aht;

// Sensor availability flags (auto-detected)
bool aht10Available = false;
bool mq135Available = false;
bool mq136Available = false;
bool mq137Available = false;

// Variables for timing
unsigned long lastSensorReadTime = 0;
const unsigned long SENSOR_READ_INTERVAL = 2000;  // Read sensor every 2 seconds
unsigned long lastMqttReconnectAttempt = 0;
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;  // Try MQTT reconnect every 5 seconds
unsigned long lastWifiReconnectAttempt = 0;
const unsigned long WIFI_RECONNECT_INTERVAL = 10000;  // Try WiFi reconnect every 10 seconds

// Simulated gas sensor values (for meat quality monitoring)
// MQ135: CO2/VOCs (ppm) - fresh meat: 400-800 ppm, spoiled: >800 ppm
float mq135Value = 450.0;
// MQ136: H2S (ppm) - fresh meat: 0-50 ppm, spoiled: >50 ppm
float mq136Value = 15.0;
// MQ137: NH3 (ppm) - fresh meat: 10-100 ppm, spoiled: >100 ppm
float mq137Value = 25.0;

// Calibration values for MQ sensors (will be set during auto-detection)
float mq135RS0 = 0.0;  // Sensor resistance in clean air
float mq136RS0 = 0.0;
float mq137RS0 = 0.0;

// Function to generate realistic random variations
float generateRealisticValue(float baseValue, float minRange, float maxRange) {
    // Generate small random variation (±5% of base value)
    float variation = baseValue * 0.05;
    float randomChange = (random(0, 100) / 100.0) * variation - (variation / 2.0);
    float newValue = baseValue + randomChange;
    
    // Clamp to valid range
    if (newValue < minRange) newValue = minRange;
    if (newValue > maxRange) newValue = maxRange;
    
    return newValue;
}

// Function to read MQ sensor and convert to ppm
float readMQSensor(int pin, float rs0, float r0, float a, float b, float minPpm, float maxPpm) {
    int adcValue = analogRead(pin);
    
    // Convert ADC to voltage (ESP32 ADC is 12-bit: 0-4095)
    float voltage = (adcValue / 4095.0) * 3.3;
    
    // Calculate sensor resistance
    // RL = 10K (load resistor)
    float rs = ((3.3 - voltage) / voltage) * 10000.0;
    
    // Calculate ratio Rs/R0
    float ratio = rs / r0;
    
    // Calculate ppm using power law: ppm = a * (ratio)^b
    float ppm = a * pow(ratio, b);
    
    // Clamp to valid range
    if (ppm < minPpm) ppm = minPpm;
    if (ppm > maxPpm) ppm = maxPpm;
    
    return ppm;
}

// Function to auto-detect MQ sensors
bool detectMQSensor(int pin, const char* sensorName) {
    // Take multiple readings to check for sensor presence
    int readings = 10;
    float sum = 0;
    int validReadings = 0;
    
    for (int i = 0; i < readings; i++) {
        int adcValue = analogRead(pin);
        // Valid sensor should give readings between 100 and 4000
        if (adcValue > 100 && adcValue < 4000) {
            sum += adcValue;
            validReadings++;
        }
        delay(10);
    }
    
    // If we have valid readings, sensor is present
    if (validReadings > readings / 2) {
        float avgAdc = sum / validReadings;
        float voltage = (avgAdc / 4095.0) * 3.3;
        Serial.print(sensorName);
        Serial.print(F(" detected! ADC: "));
        Serial.print((int)avgAdc);
        Serial.print(F(", Voltage: "));
        Serial.print(voltage, 2);
        Serial.println(F("V"));
        return true;
    }
    
    return false;
}

// Function to determine meat quality based on sensor readings
String determineMeatQuality(float temp, float humidity, float mq135, float mq136, float mq137) {
    // Quality assessment based on sensor thresholds
    // Temperature: optimal storage 0-4°C
    // Humidity: optimal 60-80%
    // Gas sensors: lower values indicate fresher meat
    
    int qualityScore = 100;
    
    // Temperature penalty (optimal: 0-4°C)
    if (temp > 4.0) {
        qualityScore -= (temp - 4.0) * 10;  // Lose 10 points per degree above 4°C
    } else if (temp < 0.0) {
        qualityScore -= (0.0 - temp) * 5;   // Lose 5 points per degree below 0°C
    }
    
    // Humidity penalty (optimal: 60-80%)
    if (humidity < 60.0) {
        qualityScore -= (60.0 - humidity) * 0.5;
    } else if (humidity > 80.0) {
        qualityScore -= (humidity - 80.0) * 0.5;
    }
    
    // Gas sensor penalties (higher values = worse quality)
    if (mq135 > 800.0) qualityScore -= (mq135 - 800.0) / 20.0;  // CO2/VOCs
    if (mq136 > 50.0)  qualityScore -= (mq136 - 50.0) / 5.0;    // H2S
    if (mq137 > 100.0) qualityScore -= (mq137 - 100.0) / 10.0; // NH3
    
    // Clamp score
    if (qualityScore < 0) qualityScore = 0;
    if (qualityScore > 100) qualityScore = 100;
    
    // Determine quality level
    if (qualityScore >= 80) return "EXCELLENT";
    if (qualityScore >= 60) return "GOOD";
    if (qualityScore >= 40) return "FAIR";
    if (qualityScore >= 20) return "POOR";
    return "SPOILED";
}

// MQTT Callback function - called when message is received
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    Serial.print(F("MQTT Message arrived ["));
    Serial.print(topic);
    Serial.print(F("]: "));
    for (unsigned int i = 0; i < length; i++) {
        Serial.print((char)payload[i]);
    }
    Serial.println();
}

// Connect to MQTT broker
bool mqttConnect() {
    // Set callback for incoming messages
    mqttClient.setCallback(mqttCallback);
    
    Serial.print(F("Connecting to MQTT broker "));
    Serial.print(mqttBroker);
    Serial.println(F("..."));
    
    // Attempt to connect with LWT (Last Will and Testament)
    // Parameters: clientId, username, password, willTopic, willQoS, willRetain, willMessage
    if (mqttClient.connect(mqttClientId, mqttUser, mqttPassword, topicLWT, mqttQoS, mqttRetain, "offline")) {
        Serial.println(F("MQTT connected!"));
        
        // Publish online status
        mqttClient.publish(topicStatus, "online", mqttRetain);
        mqttClient.publish(topicLWT, "online", mqttRetain);
        
        // Subscribe to any command topics if needed
        // mqttClient.subscribe("meat-quality/commands/#");
        
        return true;
    } else {
        Serial.print(F("MQTT connection failed, rc="));
        Serial.print(mqttClient.state());
        Serial.println(F(" (0=success, -2=network, -4=timeout, -5=connection lost)"));
        return false;
    }
}

// Reconnect to MQTT broker (with retry logic)
void mqttReconnect() {
    unsigned long currentMillis = millis();
    
    // Only attempt reconnection at intervals
    if (currentMillis - lastMqttReconnectAttempt < MQTT_RECONNECT_INTERVAL) {
        return;
    }
    
    lastMqttReconnectAttempt = currentMillis;
    
    // Check if WiFi is connected before attempting MQTT
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println(F("WiFi not connected, skipping MQTT reconnect"));
        return;
    }
    
    if (!mqttClient.connected()) {
        Serial.println(F("MQTT client disconnected, attempting to reconnect..."));
        if (mqttConnect()) {
            Serial.println(F("MQTT reconnected successfully!"));
        } else {
            Serial.println(F("MQTT reconnect failed, will try again later"));
        }
    }
}

// Reconnect to WiFi (with retry logic)
void wifiReconnect() {
    unsigned long currentMillis = millis();
    
    // Only attempt reconnection at intervals
    if (currentMillis - lastWifiReconnectAttempt < WIFI_RECONNECT_INTERVAL) {
        return;
    }
    
    lastWifiReconnectAttempt = currentMillis;
    
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println(F("WiFi disconnected, attempting to reconnect..."));
        Serial.print(F("Connecting to "));
        Serial.println(ssid);
        
        // Disconnect and reconnect
        WiFi.disconnect();
        WiFi.mode(WIFI_STA);
        WiFi.begin(ssid, password);
        
        // Wait for connection (with timeout)
        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 10) {
            delay(500);
            Serial.print(F("."));
            attempts++;
        }
        
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println(F(""));
            Serial.println(F("WiFi reconnected!"));
            Serial.print(F("IP Address: "));
            Serial.println(WiFi.localIP());
        } else {
            Serial.println(F(""));
            Serial.println(F("WiFi reconnect failed, will try again later"));
        }
    }
}

// Publish sensor data via MQTT
void publishSensorData(float temperature, float humidity, float mq135, float mq136, float mq137, String quality) {
    if (!mqttClient.connected()) {
        Serial.println(F("MQTT not connected, skipping publish"));
        return;
    }
    
    // Create JSON document
    StaticJsonDocument<512> doc;
    
    // Add timestamp (simple version - could use NTP for accurate time)
    char timestamp[32];
    snprintf(timestamp, sizeof(timestamp), "%lu", millis());
    doc["timestamp"] = timestamp;
    doc["device_id"] = mqttClientId;
    
    // Add sensor data
    JsonObject sensors = doc.createNestedObject("sensors");
    sensors["temperature"] = round(temperature * 10) / 10.0;  // Round to 1 decimal
    sensors["humidity"] = round(humidity * 10) / 10.0;
    sensors["mq135_co2"] = round(mq135 * 10) / 10.0;
    sensors["mq136_h2s"] = round(mq136 * 10) / 10.0;
    sensors["mq137_nh3"] = round(mq137 * 10) / 10.0;
    
    // Add quality assessment
    JsonObject qualityObj = doc.createNestedObject("quality");
    qualityObj["level"] = quality;
    
    // Add WiFi signal strength
    doc["wifi_rssi"] = WiFi.RSSI();
    
    // Add sensor availability
    JsonObject status = doc.createNestedObject("sensor_status");
    status["aht10"] = aht10Available;
    status["mq135"] = mq135Available;
    status["mq136"] = mq136Available;
    status["mq137"] = mq137Available;
    
    // Serialize JSON to string
    char jsonBuffer[512];
    size_t jsonLen = serializeJson(doc, jsonBuffer, sizeof(jsonBuffer));
    
    // Publish to MQTT topic
    if (mqttClient.publish(topicData, jsonBuffer, mqttRetain)) {
        Serial.print(F("MQTT published ("));
        Serial.print(jsonLen);
        Serial.print(F(" bytes): "));
        Serial.println(jsonBuffer);
    } else {
        Serial.println(F("MQTT publish failed!"));
    }
}

void setup() {
    // Initialize serial communication at 115200 baud
    Serial.begin(115200);
    delay(1000);  // Wait for serial to be ready
    
    Serial.println(F(""));
    Serial.println(F("========================================"));
    Serial.println(F("ESP32 NodeMCU - Meat Quality Monitoring"));
    Serial.println(F("========================================"));
    Serial.println(F(""));

    // Initialize I2C with custom pins
    Wire.begin(I2C_SDA, I2C_SCL);
    Serial.println(F("I2C initialized on SDA=21, SCL=22"));

    // Initialize AHT10 sensor
    Serial.println(F(""));
    Serial.println(F("Initializing AHT10 sensor..."));
    if (!aht.begin()) {
        Serial.println(F("Failed to find AHT10 sensor! Using simulated data."));
        aht10Available = false;
    } else {
        Serial.println(F("AHT10 sensor found successfully!"));
        aht10Available = true;
        
        // Read initial sensor data
        sensors_event_t humidity, temp;
        aht.getEvent(&humidity, &temp);
        
        Serial.println(F(""));
        Serial.println(F("Initial Sensor Readings:"));
        Serial.print(F("Temperature: "));
        Serial.print(temp.temperature);
        Serial.println(F(" *C"));
        Serial.print(F("Humidity:    "));
        Serial.print(humidity.relative_humidity);
        Serial.println(F(" %"));
        Serial.println(F(""));
    }

    // Detect MQ sensors
    Serial.println(F(""));
    Serial.println(F("Detecting MQ gas sensors (ADC1 pins - WiFi safe)..."));
    Serial.println(F("MQ135 on GPIO 34 (ADC1_CH6)"));
    Serial.println(F("MQ136 on GPIO 35 (ADC1_CH7)"));
    Serial.println(F("MQ137 on GPIO 36 (ADC1_CH0)"));
    Serial.println(F(""));
    
    // Warm up time for MQ sensors (they need time to stabilize)
    Serial.println(F("Waiting for MQ sensors to warm up (3 seconds)..."));
    delay(3000);
    
    // Auto-detect each MQ sensor
    Serial.println(F("Scanning for sensors..."));
    mq135Available = detectMQSensor(MQ135_PIN, "MQ135");
    mq136Available = detectMQSensor(MQ136_PIN, "MQ136");
    mq137Available = detectMQSensor(MQ137_PIN, "MQ137");
    
    // Set default R0 values for calibration (will be refined with real sensors)
    // These are approximate values - should be calibrated in clean air
    if (mq135Available) {
        // MQ135: R0 ~ 10K-47K in clean air (CO2/VOCs)
        float voltage = (analogRead(MQ135_PIN) / 4095.0) * 3.3;
        float rs = ((3.3 - voltage) / voltage) * 10000.0;
        mq135RS0 = rs / 3.6;  // Typical Rs/R0 ratio for clean air
    }
    if (mq136Available) {
        // MQ136: R0 ~ 10K-47K in clean air (H2S)
        float voltage = (analogRead(MQ136_PIN) / 4095.0) * 3.3;
        float rs = ((3.3 - voltage) / voltage) * 10000.0;
        mq136RS0 = rs / 3.6;
    }
    if (mq137Available) {
        // MQ137: R0 ~ 10K-47K in clean air (NH3)
        float voltage = (analogRead(MQ137_PIN) / 4095.0) * 3.3;
        float rs = ((3.3 - voltage) / voltage) * 10000.0;
        mq137RS0 = rs / 3.6;
    }
    
    // Report detection status
    Serial.println(F(""));
    Serial.println(F("Sensor Detection Summary:"));
    Serial.print(F("MQ135: "));
    Serial.println(mq135Available ? F("DETECTED") : F("Not detected - Using simulated data"));
    Serial.print(F("MQ136: "));
    Serial.println(mq136Available ? F("DETECTED") : F("Not detected - Using simulated data"));
    Serial.print(F("MQ137: "));
    Serial.println(mq137Available ? F("DETECTED") : F("Not detected - Using simulated data"));
    Serial.println(F(""));

    Serial.println(F("Testing WiFi connection..."));
    Serial.print(F("Connecting to "));
    Serial.println(ssid);

    // Initialize WiFi
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    // Wait for connection (with timeout)
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(F("."));
        attempts++;
    }

    Serial.println(F(""));

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(F("WiFi connected!"));
        Serial.print(F("IP Address: "));
        Serial.println(WiFi.localIP());
        Serial.print(F("MAC Address: "));
        Serial.println(WiFi.macAddress());
        Serial.print(F("Signal Strength (RSSI): "));
        Serial.print(WiFi.RSSI());
        Serial.println(F(" dBm"));
    } else {
        Serial.println(F("WiFi connection failed or timeout"));
        Serial.println(F("Continuing without WiFi..."));
    }

    Serial.println(F(""));
    Serial.println(F("========================================"));
    Serial.println(F("Setup complete."));
    Serial.println(F("Sensor readings will display every 2 seconds"));
    Serial.println(F("========================================"));
    Serial.println(F(""));
    
    // Initialize MQTT client
    mqttClient.setServer(mqttBroker, mqttPort);
    
    // Connect to MQTT broker
    if (WiFi.status() == WL_CONNECTED) {
        mqttConnect();
    } else {
        Serial.println(F("WiFi not connected, MQTT connection skipped"));
    }
}

void loop() {
    unsigned long currentMillis = millis();

    // Handle WiFi reconnection
    wifiReconnect();
    
    // Handle MQTT reconnection
    mqttReconnect();
    
    // Process incoming MQTT messages
    mqttClient.loop();

    // Read sensors at regular intervals
    if (currentMillis - lastSensorReadTime >= SENSOR_READ_INTERVAL) {
        lastSensorReadTime = currentMillis;
        
        // Variables for sensor readings
        float temperature = 0.0;
        float humidity = 0.0;
        
        // Read AHT10 sensor (or use simulated data)
        if (aht10Available) {
            sensors_event_t ahtHumidity, ahtTemp;
            aht.getEvent(&ahtHumidity, &ahtTemp);
            temperature = ahtTemp.temperature;
            humidity = ahtHumidity.relative_humidity;
        } else {
            // Simulate realistic temperature and humidity for meat storage
            // Temperature: 2-6°C (typical refrigeration)
            temperature = generateRealisticValue(3.5, 2.0, 6.0);
            // Humidity: 65-85% (typical for meat storage)
            humidity = generateRealisticValue(75.0, 65.0, 85.0);
        }
        
        // Read or simulate MQ135 (CO2/VOCs)
        if (mq135Available) {
            // MQ135: CO2/VOCs (ppm) - a=110.47, b=-2.862 (approximate)
            mq135Value = readMQSensor(MQ135_PIN, mq135RS0, 10000.0, 110.47, -2.862, 400.0, 900.0);
        } else {
            mq135Value = generateRealisticValue(mq135Value, 400.0, 900.0);
        }
        
        // Read or simulate MQ136 (H2S)
        if (mq136Available) {
            // MQ136: H2S (ppm) - a=116.3, b=-2.76 (approximate)
            mq136Value = readMQSensor(MQ136_PIN, mq136RS0, 10000.0, 116.3, -2.76, 10.0, 80.0);
        } else {
            mq136Value = generateRealisticValue(mq136Value, 10.0, 80.0);
        }
        
        // Read or simulate MQ137 (NH3)
        if (mq137Available) {
            // MQ137: NH3 (ppm) - a=110.0, b=-2.62 (approximate)
            mq137Value = readMQSensor(MQ137_PIN, mq137RS0, 10000.0, 110.0, -2.62, 20.0, 120.0);
        } else {
            mq137Value = generateRealisticValue(mq137Value, 20.0, 120.0);
        }
        
        // Determine meat quality
        String meatQuality = determineMeatQuality(temperature, humidity, mq135Value, mq136Value, mq137Value);
        
        // Display sensor readings
        Serial.println(F("========================================"));
        Serial.println(F("       MEAT QUALITY MONITORING"));
        Serial.println(F("========================================"));
        
        // Temperature and Humidity
        Serial.println(F(""));
        Serial.println(F("--- Environmental Conditions ---"));
        Serial.print(F("Temperature: "));
        Serial.print(temperature, 1);
        Serial.print(F(" *C"));
        if (!aht10Available) Serial.print(F(" (Simulated)"));
        Serial.println(F(""));
        
        Serial.print(F("Humidity:    "));
        Serial.print(humidity, 1);
        Serial.print(F(" %"));
        if (!aht10Available) Serial.print(F(" (Simulated)"));
        Serial.println(F(""));
        
        // Gas Sensors
        Serial.println(F(""));
        Serial.println(F("--- Gas Sensor Readings ---"));
        Serial.print(F("MQ135 (CO2/VOCs): "));
        Serial.print(mq135Value, 1);
        Serial.print(F(" ppm"));
        if (!mq135Available) Serial.print(F(" (Simulated)"));
        Serial.println(F(""));
        
        Serial.print(F("MQ136 (H2S):      "));
        Serial.print(mq136Value, 1);
        Serial.print(F(" ppm"));
        if (!mq136Available) Serial.print(F(" (Simulated)"));
        Serial.println(F(""));
        
        Serial.print(F("MQ137 (NH3):      "));
        Serial.print(mq137Value, 1);
        Serial.print(F(" ppm"));
        if (!mq137Available) Serial.print(F(" (Simulated)"));
        Serial.println(F(""));
        
        // Meat Quality Assessment
        Serial.println(F(""));
        Serial.println(F("--- Quality Assessment ---"));
        Serial.print(F("Meat Quality: "));
        
        // Color code the quality (ANSI escape codes - may not work on all monitors)
        if (meatQuality == "EXCELLENT") Serial.print(F("[EXCELLENT]"));
        else if (meatQuality == "GOOD") Serial.print(F("[GOOD]     "));
        else if (meatQuality == "FAIR") Serial.print(F("[FAIR]     "));
        else if (meatQuality == "POOR") Serial.print(F("[POOR]     "));
        else Serial.print(F("[SPOILED]  "));
        
        Serial.println(meatQuality);
        
        // Publish sensor data via MQTT
        publishSensorData(temperature, humidity, mq135Value, mq136Value, mq137Value, meatQuality);
        
        // WiFi Status
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println(F(""));
            Serial.print(F("WiFi: Connected ("));
            Serial.print(WiFi.localIP());
            Serial.println(F(")"));
        }
        
        Serial.println(F(""));
        Serial.println(F("========================================"));
        Serial.println(F(""));
    }
}
