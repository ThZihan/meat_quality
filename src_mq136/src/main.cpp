/*
 * MQ136 Air Quality Sensor for ESP32 NodeMCU - Web Calibration Version
 * 
 * This code reads MQ136 sensor data and provides a web interface for calibration
 * via SoftAP (no WiFi router needed)
 * 
 * MQ136 detects: Hydrogen Sulfide (H2S), Ammonia (NH3), Carbon Monoxide (CO)
 * 
 * CIRCUIT WIRING (Voltage Divider for 5V → 3.3V):
 * ================================================
 * MQ136 Module (5V operation):
 * ---------------------------
 * VCC  → 5V (external power supply or 5V pin on NodeMCU)
 * GND  → GND (common ground)
 * AOUT → Voltage Divider Input (see below)
 * 
 * VOLTAGE DIVIDER (parallel 10k + 10k = 5k, then 10k to GND):
 * ------------------------------------------------------------
 * MQ136 AOUT ────[10k||10k = 5k]───┬───[10kΩ]─── GND
 *                                 │
 *                                 └─── ESP32 GPIO 35 (ADC1_CH7)
 * 
 * Voltage Divider Calculation:
 * - Input: 0-5V from MQ136
 * - Output: 0-3.33V to ESP32 (safe for 3.3V logic)
 * - Formula: Vout = Vin × (10k / 15k) = Vin × 0.667
 * 
 * ESP32 NodeMCU Connections:
 * --------------------------
 * GPIO 35 (ADC1_CH7) → Voltage Divider Output (MQ136 analog reading)
 * 3.3V              → Not used (MQ136 powered by 5V)
 * GND               → Common ground with MQ136
 * 
 * WEB CALIBRATION:
 * ================
 * 1. ESP32 creates SoftAP: "MQ136-Calibrator"
 * 2. Connect smartphone to this WiFi (no password)
 * 3. Open browser: http://192.168.4.1
 * 4. Click "Start Calibration" button
 * 5. Wait 60 seconds for sensor to stabilize
 * 6. Copy the R0 value displayed
 * 7. Update R0 constant in code
 * 
 * IMPORTANT NOTES:
 * ================
 * 1. Use ADC1 pins (GPIO 34, 35, 36, 39) - ADC2 pins conflict with WiFi!
 * 2. MQ136 requires 5V for heater - do NOT power from 3.3V
 * 3. Voltage divider is MANDATORY to protect ESP32 from 5V
 * 4. Pre-heat sensor for 24-48 hours for accurate readings
 * 5. ESP32 ADC is 12-bit (0-4095)
 * 
 * CALIBRATION:
 * ============
 * 1. Place sensor in clean air (outdoor or well-ventilated area)
 * 2. Connect to SoftAP and open web interface
 * 3. Click calibration button and wait
 * 4. Note the R0 value and update in code
 * 5. Typical R0 for MQ136: 10kΩ - 100kΩ (varies by sensor)
 * 
 * MQ136 Gas Sensitivity (approximate):
 * =================================
 * - H2S (Hydrogen Sulfide): 1-200 ppm (primary target for meat spoilage)
 * - NH3 (Ammonia): 10-300 ppm
 * - CO (Carbon Monoxide): 1-1000 ppm
 * 
 * For Meat Quality Monitoring:
 * ============================
 * - Fresh meat: H2S < 5 ppm
 * - Spoiling meat: H2S > 10 ppm
 * - H2S is a key indicator of protein breakdown/rotting
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

// ===== HARDWARE CONFIGURATION =====
const int MQ136_PIN = 35;  // ADC1_CH7 - Safe with WiFi enabled
const float VOLTAGE_DIVIDER_RATIO = 1.5;  // 5V → 3.33V (divide by 1.5)
const float ESP32_VREF = 3.3;  // ESP32 reference voltage
const int ADC_RESOLUTION = 4095;  // 12-bit ADC

// ===== MQ136 SENSOR PARAMETERS =====
// Load resistor value (on MQ136 module, typically 10kΩ)
const float RL = 10000.0;  // 10kΩ

// Sensor resistance in clean air (UPDATE THIS AFTER CALIBRATION!)
const float R0 = 20000.0;  // Default: 20kΩ (update after calibration)

// MQ136 sensitivity curve parameters (from datasheet)
// Rs/R0 = a * (ppm)^b
const float H2S_A = 44.947;
const float H2S_B = -2.648;
const float NH3_A = 102.2;
const float NH3_B = -2.473;
const float CO_A = 605.18;
const float CO_B = -3.039;

// ===== WIFI / WEB SERVER CONFIG =====
const char* SOFTAP_SSID = "MQ136-Calibrator";
const char* SOFTAP_PASSWORD = "";  // Open network
WebServer server(80);

// ===== TIMING =====
const unsigned long READ_INTERVAL = 2000;  // Read every 2 seconds
const unsigned long CALIBRATION_DURATION = 60000;  // 60 seconds calibration
unsigned long lastReadTime = 0;
unsigned long startTime = 0;

// ===== CALIBRATION STATE =====
bool isCalibrating = false;
unsigned long calibrationStartTime = 0;
float calibrationSum = 0;
int calibrationCount = 0;
float currentR0 = 0.0;

// ===== FUNCTION PROTOTYPES =====
float readMQ136();
float calculatePPM(float rs, float a, float b);
float calculateRS(float voltage);
void handleRoot();
void handleStartCalibration();
void handleCalibrationStatus();
void handleSensorData();
String getHTML();
void setupWiFi();
void setupWebServer();

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println(F("\n========================================"));
    Serial.println(F("MQ136 Air Quality Sensor - ESP32 NodeMCU"));
    Serial.println(F("Web Calibration Mode"));
    Serial.println(F("========================================\n"));
    
    // Configure ADC
    analogReadResolution(12);  // 12-bit resolution (0-4095)
    analogSetAttenuation(ADC_11db);  // Full range: 0-3.3V
    
    // Setup WiFi SoftAP
    setupWiFi();
    
    // Setup Web Server
    setupWebServer();
    
    // Print circuit wiring information
    Serial.println(F("CIRCUIT WIRING:"));
    Serial.println(F("MQ136 VCC  → 5V"));
    Serial.println(F("MQ136 GND  → GND"));
    Serial.println(F("MQ136 AOUT → [10k||10k] → GPIO 35"));
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
    
    // Print current R0 value
    Serial.print(F("Current R0 value: "));
    Serial.print(R0);
    Serial.println(F(" Ω"));
    Serial.println(F(""));
    
    // Print sensor preheat info
    Serial.println(F("SENSOR PREHEAT:"));
    Serial.println(F("For accurate readings, preheat for 24-48 hours"));
    Serial.println(F(""));
    
    startTime = millis();
    Serial.println(F("Starting sensor readings...\n"));
}

void loop() {
    server.handleClient();
    
    unsigned long currentTime = millis();
    
    // Handle calibration if active
    if (isCalibrating) {
        if (currentTime - calibrationStartTime >= CALIBRATION_DURATION) {
            // Calibration complete
            currentR0 = calibrationSum / calibrationCount;
            isCalibrating = false;
            
            Serial.println(F("\n========================================"));
            Serial.println(F("CALIBRATION COMPLETE!"));
            Serial.print(F("Measured R0: "));
            Serial.print(currentR0);
            Serial.println(F(" Ω"));
            Serial.println(F("Update R0 constant in code with this value"));
            Serial.println(F("========================================\n"));
        } else {
            // Take calibration sample
            int adcValue = analogRead(MQ136_PIN);
            float voltage = (adcValue / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
            float rs = calculateRS(voltage);
            
            if (rs > 0) {
                calibrationSum += rs;
                calibrationCount++;
            }
            
            delay(100);  // Sample every 100ms during calibration
        }
        return;
    }
    
    // Read sensor at specified interval
    if (currentTime - lastReadTime >= READ_INTERVAL) {
        lastReadTime = currentTime;
        
        // Read MQ136 sensor
        float h2sPPM = readMQ136();
        float nh3PPM = readMQ136();  // Using same reading for simplicity
        float coPPM = readMQ136();
        
        // Get raw voltage and resistance for debugging
        int adcValue = analogRead(MQ136_PIN);
        float voltage = (adcValue / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
        float rs = calculateRS(voltage);
        
        // Print to Serial Monitor
        Serial.println(F("SENSOR READINGS:"));
        Serial.print(F("  ADC Value: "));
        Serial.println(adcValue);
        Serial.print(F("  Voltage: "));
        Serial.print(voltage, 3);
        Serial.println(F(" V"));
        Serial.print(F("  Rs: "));
        Serial.print(rs);
        Serial.println(F(" Ω"));
        Serial.print(F("  Rs/R0: "));
        Serial.println(rs / R0);
        Serial.print(F("  H2S: "));
        Serial.print(h2sPPM);
        Serial.println(F(" ppm"));
        Serial.print(F("  NH3: "));
        Serial.print(nh3PPM);
        Serial.println(F(" ppm"));
        Serial.print(F("  CO: "));
        Serial.print(coPPM);
        Serial.println(F(" ppm"));
        
        // Meat quality assessment based on H2S
        Serial.println(F("MEAT QUALITY ASSESSMENT (H2S):"));
        if (h2sPPM < 5) {
            Serial.println(F("  Status: FRESH"));
            Serial.println(F("  H2S Level: Normal"));
        } else if (h2sPPM < 10) {
            Serial.println(F("  Status: GOOD"));
            Serial.println(F("  H2S Level: Slightly elevated"));
        } else if (h2sPPM < 20) {
            Serial.println(F("  Status: MODERATE"));
            Serial.println(F("  H2S Level: Elevated - monitor closely"));
        } else {
            Serial.println(F("  Status: SPOILED"));
            Serial.println(F("  H2S Level: High - meat may be spoiled"));
        }
        Serial.println(F("========================================\n"));
    }
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
    server.on("/start_calibration", HTTP_GET, handleStartCalibration);
    server.on("/calibration_status", HTTP_GET, handleCalibrationStatus);
    server.on("/sensor_data", HTTP_GET, handleSensorData);
    
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
 * Handle start calibration request
 */
void handleStartCalibration() {
    if (!isCalibrating) {
        isCalibrating = true;
        calibrationStartTime = millis();
        calibrationSum = 0;
        calibrationCount = 0;
        currentR0 = 0.0;
        
        Serial.println(F("\nCalibration started..."));
    }
    
    server.send(200, "text/plain", "Calibration started");
}

/**
 * Handle calibration status request
 */
void handleCalibrationStatus() {
    String status;
    
    if (isCalibrating) {
        unsigned long elapsed = millis() - calibrationStartTime;
        int remaining = (CALIBRATION_DURATION - elapsed) / 1000;
        
        status = "{\"calibrating\":true,\"remaining\":" + String(remaining) + "}";
    } else if (currentR0 > 0) {
        status = "{\"calibrating\":false,\"complete\":true,\"r0\":" + String(currentR0, 2) + "}";
    } else {
        status = "{\"calibrating\":false,\"complete\":false}";
    }
    
    server.send(200, "application/json", status);
}

/**
 * Handle sensor data request
 */
void handleSensorData() {
    int adcValue = analogRead(MQ136_PIN);
    float voltage = (adcValue / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float rs = calculateRS(voltage);
    float h2sPPM = calculatePPM(rs, H2S_A, H2S_B);
    float nh3PPM = calculatePPM(rs, NH3_A, NH3_B);
    float coPPM = calculatePPM(rs, CO_A, CO_B);
    
    String data = "{\"adc\":" + String(adcValue) + 
                  ",\"voltage\":" + String(voltage, 3) + 
                  ",\"rs\":" + String(rs, 2) + 
                  ",\"h2s\":" + String(h2sPPM, 2) + 
                  ",\"nh3\":" + String(nh3PPM, 2) + 
                  ",\"co\":" + String(coPPM, 2) + "}";
    
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
    <title>MQ136 Calibration</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 600px;
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
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 10px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(240, 147, 251, 0.4);
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
            background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
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
            font-size: 32px;
            font-weight: bold;
        }
        .result-unit {
            color: #155724;
            font-size: 18px;
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
    </style>
</head>
<body>
    <div class='container'>
        <h1>MQ136 Calibration</h1>
        <p class='subtitle'>H2S/NH3/CO Gas Sensor Calibration Tool</p>
        
        <div class='instructions'>
            <div class='instructions-title'>📋 Calibration Instructions:</div>
            <ol class='instructions-list'>
                <li>Place sensor in CLEAN AIR (outdoor or well-ventilated area)</li>
                <li>Click "Start Calibration" button below</li>
                <li>Wait 60 seconds for sensor to stabilize</li>
                <li>Copy the R0 value displayed</li>
                <li>Update R0 constant in your code</li>
            </ol>
        </div>
        
        <div id='status' class='status idle'>Ready to Calibrate</div>
        
        <div id='progressContainer' style='display:none;'>
            <div class='progress-bar'>
                <div id='progressFill' class='progress-fill' style='width: 0%'>0%</div>
            </div>
        </div>
        
        <div id='resultContainer' style='display:none;'>
            <div class='result-box'>
                <div class='result-label'>Calibration Complete!</div>
                <div class='result-value' id='r0Value'>0.00</div>
                <div class='result-unit'>Ω (ohms)</div>
            </div>
        </div>
        
        <button id='calibrateBtn' class='btn btn-primary' onclick='startCalibration()'>Start Calibration</button>
        <button class='btn btn-secondary' onclick='location.reload()'>Refresh</button>
        
        <div class='section'>
            <div class='section-title'>📊 Sensor Readings</div>
            <div class='data-row'>
                <span class='data-label'>ADC Value:</span>
                <span class='data-value' id='adcValue'>--</span>
            </div>
            <div class='data-row'>
                <span class='data-label'>Voltage:</span>
                <span class='data-value' id='voltage'>-- V</span>
            </div>
            <div class='data-row'>
                <span class='data-label'>Rs (Sensor Resistance):</span>
                <span class='data-value' id='rs'>-- Ω</span>
            </div>
            <div class='data-row'>
                <span class='data-label'>Rs/R0 Ratio:</span>
                <span class='data-value' id='rsR0'>--</span>
            </div>
            <div class='data-row'>
                <span class='data-label'>H2S (Hydrogen Sulfide):</span>
                <span class='data-value' id='h2s'>-- ppm</span>
            </div>
            <div class='data-row'>
                <span class='data-label'>NH3 (Ammonia):</span>
                <span class='data-value' id='nh3'>-- ppm</span>
            </div>
            <div class='data-row'>
                <span class='data-label'>CO (Carbon Monoxide):</span>
                <span class='data-value' id='co'>-- ppm</span>
            </div>
            <div id='meatStatus' class='meat-status fresh' style='display:none;'>--</div>
        </div>
    </div>

    <script>
        const R0_VALUE = )" + String(R0, 2) + R"(;
        
        function startCalibration() {
            fetch('/start_calibration')
                .then(response => response.text())
                .then(data => {
                    document.getElementById('calibrateBtn').disabled = true;
                    document.getElementById('calibrateBtn').textContent = 'Calibrating...';
                    document.getElementById('status').className = 'status calibrating';
                    document.getElementById('status').textContent = 'Calibrating...';
                    document.getElementById('progressContainer').style.display = 'block';
                    document.getElementById('resultContainer').style.display = 'none';
                    checkCalibrationStatus();
                });
        }
        
        function checkCalibrationStatus() {
            fetch('/calibration_status')
                .then(response => response.json())
                .then(data => {
                    if (data.calibrating) {
                        const progress = ((60 - data.remaining) / 60) * 100;
                        document.getElementById('progressFill').style.width = progress + '%';
                        document.getElementById('progressFill').textContent = Math.round(progress) + '%';
                        setTimeout(checkCalibrationStatus, 1000);
                    } else if (data.complete) {
                        document.getElementById('progressContainer').style.display = 'none';
                        document.getElementById('resultContainer').style.display = 'block';
                        document.getElementById('r0Value').textContent = data.r0.toFixed(2);
                        document.getElementById('status').className = 'status complete';
                        document.getElementById('status').textContent = 'Calibration Complete!';
                        document.getElementById('calibrateBtn').disabled = false;
                        document.getElementById('calibrateBtn').textContent = 'Start New Calibration';
                    }
                });
        }
        
        function updateSensorData() {
            fetch('/sensor_data')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('adcValue').textContent = data.adc;
                    document.getElementById('voltage').textContent = data.voltage.toFixed(3) + ' V';
                    document.getElementById('rs').textContent = data.rs.toFixed(2) + ' Ω';
                    document.getElementById('rsR0').textContent = (data.rs / R0_VALUE).toFixed(2);
                    document.getElementById('h2s').textContent = data.h2s.toFixed(2) + ' ppm';
                    document.getElementById('nh3').textContent = data.nh3.toFixed(2) + ' ppm';
                    document.getElementById('co').textContent = data.co.toFixed(2) + ' ppm';
                    
                    const meatStatus = document.getElementById('meatStatus');
                    meatStatus.style.display = 'block';
                    
                    if (data.h2s < 5) {
                        meatStatus.className = 'meat-status fresh';
                        meatStatus.textContent = 'Status: FRESH';
                    } else if (data.h2s < 10) {
                        meatStatus.className = 'meat-status good';
                        meatStatus.textContent = 'Status: GOOD';
                    } else if (data.h2s < 20) {
                        meatStatus.className = 'meat-status moderate';
                        meatStatus.textContent = 'Status: MODERATE';
                    } else {
                        meatStatus.className = 'meat-status spoiled';
                        meatStatus.textContent = 'Status: SPOILED';
                    }
                });
        }
        
        // Update sensor data every 2 seconds
        setInterval(updateSensorData, 2000);
        updateSensorData();
    </script>
</body>
</html>)";
    
    return html;
}

/**
 * Read MQ136 sensor and calculate H2S PPM
 * @return H2S concentration in PPM
 */
float readMQ136() {
    int adcValue = analogRead(MQ136_PIN);
    
    // Convert ADC to voltage (accounting for voltage divider)
    float voltage = (adcValue / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    
    // Calculate sensor resistance
    float rs = calculateRS(voltage);
    
    // Calculate PPM using H2S curve
    float ppm = calculatePPM(rs, H2S_A, H2S_B);
    
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
    // Vcc = 5V (MQ136 supply voltage)
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
