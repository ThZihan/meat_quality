/*
 * MQ135 + MQ136 + MQ137 Air Quality Sensor for ESP32 NodeMCU
 * HTTP API Version — Offline Queue + SoftAP WiFi Portal + EEPROM
 *
 * FEATURES:
 * =========
 * 1. HTTP POST to cloud API with offline queue (guaranteed delivery)
 * 2. SoftAP WiFi Configuration Portal (type "1" in Serial to activate)
 * 3. EEPROM credential storage (survives reboots)
 * 4. 3-second sensor reading interval
 *
 * OFFLINE QUEUE:
 * ==============
 * If HTTP POST fails, JSON payload is queued (up to 20 entries).
 * Each cycle drains up to 3 queued items before sending new data.
 * At 3s interval: 20 new/min + up to 60 drain/min = safe under 120 req/min limit.
 * Queue of 20 clears in ~7 seconds during recovery.
 *
 * SOFTAP WIFI PORTAL:
 * ===================
 * Serial trigger: Type "1" + Enter in Serial Monitor to enter config mode.
 * ESP32 creates AP "ESP32-Setup" (password: configured below).
 * Connect via phone → auto-redirect to http://192.168.4.1.
 * Select network, enter password, live status feedback.
 * After success, SoftAP closes after 5 seconds.
 *
 * SENSOR DETECTION:
 * ================
 * - MQ135: VOC (General Spoilage Index)
 * - MQ136: H2S, NH3, CO
 * - MQ137: NH3 (specialized ammonia detection)
 *
 * CIRCUIT WIRING (Voltage Dividers for 5V → 3.3V):
 * =================================================
 * VOLTAGE DIVIDER (4.7k upper, 9k lower):
 * MQxxx AOUT ────[4.7kΩ]───┬───[9kΩ]─── GND
 *                            │
 *                            └─── ESP32 GPIO
 *
 * Voltage Divider Calculation:
 * - Input: 0-5V from MQ sensors
 * - Output: 0-3.28V to ESP32 (safe for 3.3V logic)
 * - Formula: Vout = Vin × (9k / 13.7k) = Vin × 0.657
 * - Correction: Multiply by 1.5222 to get actual sensor voltage
 */

#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <sys/time.h>
#include <EEPROM.h>
#include <Adafruit_BME280.h>
#include "sntp.h"

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

// MQTT Broker — Pi hotspot gateway IP (fixed, never changes)
const char* MQTT_BROKER = "192.168.4.1";
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "meat-quality/data";
const char* MQTT_CLIENT_ID = "ESP32-MeatMonitor";
const char* MQTT_USERNAME = "meat_monitor";
const char* MQTT_PASSWORD = "meat_monitor";

const char* DEVICE_ID = "ESP32-MeatMonitor";

// SoftAP Config Portal
const char* AP_SSID     = "ESP32-Setup";
const char* AP_PASSWORD = "12345678";  // Set before flashing

// Timing
const unsigned long READ_INTERVAL_MS = 5000;  // 5 seconds
const unsigned long MQTT_RECONNECT_INTERVAL_MS = 5000;

// Queue
const int MAX_QUEUE       = 20;
const int DRAIN_PER_CYCLE = 3;   // Drain up to 3 queued items per cycle
const int JSON_BUF_SIZE   = 512;

// EEPROM layout (512 bytes allocated)
#define EEPROM_SIZE        512
#define EEPROM_MAGIC_ADDR  0
#define EEPROM_SSID_ADDR   1
#define EEPROM_PASS_ADDR   65
#define EEPROM_MAGIC_BYTE  0xAA
#define EEPROM_MAX_LEN     64

// Hardware
const int MQ135_PIN = 35;  // ADC1_CH6
const int MQ136_PIN = 34;  // ADC1_CH7
const int MQ137_PIN = 32;  // ADC1_CH4
const int BME_SDA_PIN = 21;
const int BME_SCL_PIN = 22;
const uint8_t BME_ADDRESS = 0x76;  // BME280 default; code also tries 0x77
const float VOLTAGE_DIVIDER_RATIO = 1.5222;  // 4.7k upper, 9k lower
const float ESP32_VREF = 3.3;
const int ADC_RESOLUTION = 4095;
const unsigned long BME_RETRY_MS = 5000;
const unsigned long NTP_SYNC_TIMEOUT_MS = 10000;
const unsigned long NTP_RETRY_INTERVAL_MS = 10UL * 60UL * 1000UL;
const time_t PRESET_TIME_UTC = 1778652000;  // 2026-05-13T12:00:00Z — updated fallback if NTP fails

// Time sync control flag - set to true to use NTP, false to use hardcoded time
const bool ENABLE_TIME_SYNC = true;

// MQ Sensor Parameters
const float RL = 10000.0;  // 10kΩ load resistor

// R0 values from 24-hour burn-in calibration
const float MQ135_R0 = 193200.00;
const float MQ136_R0 = 85102.55;
const float MQ137_R0 = 51913.09;

// MQ135 sensitivity curve (CO2/VOC)
const float MQ135_VOC_A = 110.47;
const float MQ135_VOC_B = -2.862;
const float MQ135_NH3_A = 102.2;
const float MQ135_NH3_B = -2.473;

// MQ136 sensitivity curve (H2S/NH3/CO)
const float MQ136_H2S_A = 44.947;
const float MQ136_H2S_B = -2.648;
const float MQ136_NH3_A = 102.2;
const float MQ136_NH3_B = -2.473;
const float MQ136_CO_A  = 605.18;
const float MQ136_CO_B  = -3.039;

// MQ137 sensitivity curve (NH3)
const float MQ137_NH3_A = 102.2;
const float MQ137_NH3_B = -2.473;

// ═══════════════════════════════════════════════════════════════
// FORWARD DECLARATIONS
// ═══════════════════════════════════════════════════════════════
int publishJson(const char* jsonPayload);
void ensureMqttConnection();

// ═══════════════════════════════════════════════════════════════
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════════

// WiFi credentials (loaded from EEPROM)
char wifi_ssid[65] = "";
char wifi_pass[65] = "";

// MQTT client
WiFiClient mqttWifiClient;
PubSubClient mqttClient(mqttWifiClient);
unsigned long lastMqttReconnectAttempt = 0;

// Offline queue
struct QueuedPayload {
    char json[JSON_BUF_SIZE];
};
QueuedPayload queue[MAX_QUEUE];
int queueCount = 0;

// HTTP stats
int httpSuccessCount  = 0;
int httpFailCount     = 0;
int queueDrainCount   = 0;
int queueDropCount    = 0;

// Timing
unsigned long lastReadTime = 0;

// SoftAP portal objects
WebServer* portalServer = nullptr;
DNSServer* dnsServer    = nullptr;
bool portalActive       = false;

// BME280 temperature/humidity/pressure sensor
Adafruit_BME280 bme;
bool bmeReady = false;
unsigned long lastBmeInitAttempt = 0;

// Time synchronization / fallback clock
volatile bool ntpTimeSynced = false;
volatile bool ntpSyncInProgress = false;
volatile bool ntpSyncEventPending = false;
volatile bool usingFallbackTime = false;
bool fallbackTimeApplied = false;
unsigned long ntpSyncStartMs = 0;
unsigned long lastNtpAttemptMs = 0;
unsigned long lastTimeWaitLogMs = 0;

// ═══════════════════════════════════════════════════════════════
// BME280 TEMPERATURE/HUMIDITY/PRESSURE SENSOR
// ═══════════════════════════════════════════════════════════════

bool isI2CDevicePresent(uint8_t address) {
    Wire.beginTransmission(address);
    return Wire.endTransmission() == 0;
}

bool initBME280() {
    lastBmeInitAttempt = millis();
    Serial.println(F("[BME280] Initializing sensor..."));

    uint8_t detectedAddress = BME_ADDRESS;
    if (!isI2CDevicePresent(detectedAddress)) {
        Serial.println(F("[BME280] Sensor not found at 0x76, trying 0x77..."));
        detectedAddress = 0x77;
        if (!isI2CDevicePresent(detectedAddress)) {
            Serial.println(F("[BME280] Sensor not found at either 0x76 or 0x77"));
            bmeReady = false;
            return false;
        }
    }

    if (!bme.begin(detectedAddress, &Wire)) {
        Serial.printf("[BME280] Sensor detected at 0x%02X, but initialization failed\n", detectedAddress);
        bmeReady = false;
        return false;
    }

    bmeReady = true;
    Serial.printf("[BME280] ✓ Sensor initialized successfully at 0x%02X\n", detectedAddress);
    return true;
}

bool readBME280(float& temperatureC, float& humidityRH) {
    if (!bmeReady) {
        return false;
    }

    temperatureC = bme.readTemperature();
    humidityRH = bme.readHumidity();

    if (isnan(temperatureC) || isnan(humidityRH)) {
        Serial.println(F("[BME280] Invalid reading (NaN). Marking sensor unavailable."));
        bmeReady = false;
        return false;
    }

    // Range validation: BME280 spec is -40°C to 85°C, 0-100% RH
    if (temperatureC < -40.0 || temperatureC > 85.0 ||
        humidityRH < 0.0 || humidityRH > 100.0) {
        Serial.printf("[BME280] Out-of-range reading: Temp=%.2f°C Hum=%.2f%%RH — discarding\n",
                      temperatureC, humidityRH);
        return false;
    }

    return true;
}

// ═══════════════════════════════════════════════════════════════
// TIME SYNCHRONIZATION / FALLBACK CLOCK
// ═══════════════════════════════════════════════════════════════

void formatUtcTimestamp(time_t epoch, char* buf, size_t bufSize) {
    struct tm timeinfo;
    gmtime_r(&epoch, &timeinfo);
    strftime(buf, bufSize, "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
}

bool getCurrentTimestamp(char* buf, size_t bufSize) {
    if (!ntpTimeSynced && !fallbackTimeApplied) {
        return false;
    }

    time_t now = time(nullptr);
    if (now <= 0) {
        return false;
    }

    formatUtcTimestamp(now, buf, bufSize);
    return true;
}

void onNtpTimeSync(struct timeval* tv) {
    (void)tv;
    ntpTimeSynced = true;
    ntpSyncInProgress = false;
    usingFallbackTime = false;
    ntpSyncEventPending = true;
}

void applyPresetTimeFallback() {
    if (fallbackTimeApplied) {
        usingFallbackTime = true;
        return;
    }

    struct timeval tv = {};
    tv.tv_sec = PRESET_TIME_UTC;
    settimeofday(&tv, nullptr);

    fallbackTimeApplied = true;
    usingFallbackTime = true;

    char timestamp[32];
    formatUtcTimestamp(PRESET_TIME_UTC, timestamp, sizeof(timestamp));
    Serial.printf("[NTP] Using preset fallback time: %s\n", timestamp);
}

void startNtpSync(const char* reason) {
    if (!ENABLE_TIME_SYNC) {
        Serial.println("[NTP] Time sync disabled by flag. Using hardcoded time.");
        applyPresetTimeFallback();
        return;
    }

    if (WiFi.status() != WL_CONNECTED) {
        Serial.printf("[NTP] Skipping sync (%s) — WiFi not connected\n", reason);
        return;
    }

    sntp_set_time_sync_notification_cb(onNtpTimeSync);
    ntpSyncInProgress = true;
    ntpSyncEventPending = false;
    ntpSyncStartMs = millis();
    lastNtpAttemptMs = ntpSyncStartMs;

    Serial.printf("[NTP] Starting sync (%s). Timeout: %lu ms\n", reason, NTP_SYNC_TIMEOUT_MS);
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
}

void handleTimeSync() {
    if (!ENABLE_TIME_SYNC) {
        // Time sync disabled - ensure preset time is applied
        if (!fallbackTimeApplied) {
            applyPresetTimeFallback();
        }
        return;
    }

    unsigned long currentMs = millis();

    if (ntpSyncEventPending) {
        ntpSyncEventPending = false;
        char timestamp[32];
        if (getCurrentTimestamp(timestamp, sizeof(timestamp))) {
            Serial.printf("[NTP] ✓ Time synchronized: %s\n", timestamp);
        } else {
            Serial.println(F("[NTP] ✓ Time synchronized"));
        }
    }

    if (ntpSyncInProgress && !ntpTimeSynced && (currentMs - ntpSyncStartMs >= NTP_SYNC_TIMEOUT_MS)) {
        ntpSyncInProgress = false;
        Serial.println(F("[NTP] Sync timeout after 10 seconds. Switching to preset time."));
        applyPresetTimeFallback();
    }

    if (usingFallbackTime && !ntpTimeSynced && WiFi.status() == WL_CONNECTED && !ntpSyncInProgress &&
        (lastNtpAttemptMs == 0 || currentMs - lastNtpAttemptMs >= NTP_RETRY_INTERVAL_MS)) {
        Serial.println(F("[NTP] Retrying time sync while preset time is active..."));
        startNtpSync("10-minute retry");
    }
}

// ═══════════════════════════════════════════════════════════════
// EEPROM CREDENTIALS
// ═══════════════════════════════════════════════════════════════

void saveCredentials(const char* ssid, const char* pass) {
    EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_BYTE);
    for (int i = 0; i < EEPROM_MAX_LEN; i++) {
        EEPROM.write(EEPROM_SSID_ADDR + i, (i < (int)strlen(ssid)) ? ssid[i] : 0);
        EEPROM.write(EEPROM_PASS_ADDR + i, (i < (int)strlen(pass)) ? pass[i] : 0);
    }
    EEPROM.commit();
    Serial.println(F("[EEPROM] Credentials saved"));
}

bool loadCredentials() {
    if (EEPROM.read(EEPROM_MAGIC_ADDR) != EEPROM_MAGIC_BYTE) {
        Serial.println(F("[EEPROM] No saved credentials"));
        return false;
    }
    for (int i = 0; i < EEPROM_MAX_LEN; i++) {
        wifi_ssid[i] = (char)EEPROM.read(EEPROM_SSID_ADDR + i);
        wifi_pass[i] = (char)EEPROM.read(EEPROM_PASS_ADDR + i);
    }
    wifi_ssid[EEPROM_MAX_LEN] = '\0';
    wifi_pass[EEPROM_MAX_LEN] = '\0';
    if (strlen(wifi_ssid) == 0) {
        Serial.println(F("[EEPROM] Saved SSID is empty"));
        return false;
    }
    Serial.print(F("[EEPROM] Loaded SSID: "));
    Serial.println(wifi_ssid);
    return true;
}

void clearCredentials() {
    for (int i = 0; i < EEPROM_SIZE; i++) {
        EEPROM.write(i, 0);
    }
    EEPROM.commit();
    wifi_ssid[0] = '\0';
    wifi_pass[0] = '\0';
    Serial.println(F("[EEPROM] Credentials cleared"));
}

// ═══════════════════════════════════════════════════════════════
// OFFLINE QUEUE
// ═══════════════════════════════════════════════════════════════

bool enqueue(const char* json) {
    if (queueCount >= MAX_QUEUE) {
        // Queue full — drop oldest (shift everything left)
        for (int i = 0; i < MAX_QUEUE - 1; i++) {
            memcpy(queue[i].json, queue[i + 1].json, JSON_BUF_SIZE);
        }
        queueCount = MAX_QUEUE - 1;
        queueDropCount++;
        Serial.printf("[QUEUE] Full! Dropped oldest. (total dropped: %d)\n", queueDropCount);
    }
    strncpy(queue[queueCount].json, json, JSON_BUF_SIZE - 1);
    queue[queueCount].json[JSON_BUF_SIZE - 1] = '\0';
    queueCount++;
    Serial.printf("[QUEUE] Added. Size: %d/%d\n", queueCount, MAX_QUEUE);
    return true;
}

void drainQueue() {
    int drained = 0;
    while (queueCount > 0 && drained < DRAIN_PER_CYCLE) {
        Serial.printf("[QUEUE] Draining %d/%d (attempt %d/%d)...\n",
                      1, queueCount, drained + 1, DRAIN_PER_CYCLE);

        int code = publishJson(queue[0].json);
        if (code == 200 || code == 201) {
            // Success — shift remaining items forward
            for (int i = 0; i < queueCount - 1; i++) {
                memcpy(queue[i].json, queue[i + 1].json, JSON_BUF_SIZE);
            }
            queueCount--;
            drained++;
            queueDrainCount++;
            httpSuccessCount++;
            Serial.printf("[QUEUE] ✓ Drained %d, remaining: %d\n", drained, queueCount);
        } else {
            // Drain failed — stop trying this cycle
            Serial.printf("[QUEUE] ✗ Drain failed (HTTP %d), will retry next cycle\n", code);
            httpFailCount++;
            break;
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// MQTT COMMUNICATION
// ═══════════════════════════════════════════════════════════════

void ensureMqttConnection() {
    if (WiFi.status() != WL_CONNECTED) {
        return;
    }

    if (mqttClient.connected()) {
        return;
    }

    unsigned long now = millis();
    if (lastMqttReconnectAttempt != 0 && (now - lastMqttReconnectAttempt) < MQTT_RECONNECT_INTERVAL_MS) {
        return;
    }
    lastMqttReconnectAttempt = now;

    Serial.printf("[MQTT] Connecting to %s:%d...\n", MQTT_BROKER, MQTT_PORT);

    bool connected = false;
    if (strlen(MQTT_USERNAME) > 0) {
        connected = mqttClient.connect(MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD);
    } else {
        connected = mqttClient.connect(MQTT_CLIENT_ID);
    }

    if (connected) {
        Serial.println(F("[MQTT] ✓ Connected"));
        return;
    }

    Serial.printf("[MQTT] ✗ Connect failed, state=%d\n", mqttClient.state());
}

int publishJson(const char* jsonPayload) {
    ensureMqttConnection();

    if (!mqttClient.connected()) {
        return 503;
    }

    bool ok = mqttClient.publish(MQTT_TOPIC, jsonPayload, false);
    mqttClient.loop();

    if (ok) {
        Serial.printf("  MQTT publish OK (topic=%s, bytes=%u)\n", MQTT_TOPIC, (unsigned int)strlen(jsonPayload));
        return 200;
    }

    Serial.printf("  MQTT publish failed (state=%d)\n", mqttClient.state());
    return 500;
}

// ═══════════════════════════════════════════════════════════════
// JSON BUILDER
// ═══════════════════════════════════════════════════════════════

void buildSensorJson(char* buf, float temperatureC, float humidityRH, bool bmeReadOk,
                     float mq135_vocPPM, float mq135_nh3PPM,
                     float mq136_h2sPPM, float mq136_nh3PPM, float mq136_coPPM,
                     float mq137_nh3PPM, const char* qualityLevel) {
    StaticJsonDocument<512> doc;

    doc["device_id"] = DEVICE_ID;

    // Timestamp
    char timestamp[32];
    if (getCurrentTimestamp(timestamp, sizeof(timestamp))) {
        doc["timestamp"] = timestamp;
    } else {
        doc["timestamp"] = "1970-01-01T00:00:00Z";
    }

    // Sensors
    JsonObject sensors = doc.createNestedObject("sensors");
    if (bmeReadOk) {
        sensors["temperature"] = temperatureC;
        sensors["humidity"]    = humidityRH;
    } else {
        // Server requires numbers — send 0 as sentinel when BME280 is unavailable
        sensors["temperature"] = 0.0f;
        sensors["humidity"]    = 0.0f;
    }
    sensors["mq135_co2"]   = mq135_vocPPM;
    sensors["mq136_h2s"]   = mq136_h2sPPM;
    sensors["mq137_nh3"]   = mq137_nh3PPM;

    // Quality
    JsonObject quality = doc.createNestedObject("quality");
    quality["level"] = qualityLevel;

    doc["wifi_rssi"] = WiFi.RSSI();

    JsonObject sensorStatus = doc.createNestedObject("sensor_status");
    sensorStatus["bme280_ready"] = bmeReady;
    sensorStatus["bme280_read_ok"] = bmeReadOk;
    sensorStatus["time_source"] = ntpTimeSynced ? "ntp" : (fallbackTimeApplied ? "preset" : "unset");

    serializeJson(doc, buf, JSON_BUF_SIZE);
}

// ═══════════════════════════════════════════════════════════════
// SOFTAP WIFI CONFIGURATION PORTAL
// ═══════════════════════════════════════════════════════════════

const char PORTAL_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 WiFi Setup</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f0f23;color:#e0e0e0;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px}
.card{background:#1a1a2e;border-radius:16px;padding:28px;max-width:400px;width:100%;box-shadow:0 8px 32px rgba(0,0,0,0.4)}
h1{color:#00d4ff;font-size:22px;text-align:center;margin-bottom:6px}
.sub{color:#888;text-align:center;font-size:13px;margin-bottom:20px}
.networks{list-style:none;max-height:240px;overflow-y:auto;margin-bottom:16px}
.networks li{padding:12px 14px;border-radius:10px;background:#16213e;margin-bottom:6px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;transition:background 0.2s}
.networks li:hover,.networks li.selected{background:#0a4d68;border-color:#00d4ff}
.rssi{font-size:20px}
.ssid-text{font-weight:600;font-size:14px}
label{display:block;color:#aaa;font-size:13px;margin-bottom:6px;margin-top:16px}
input[type=password]{width:100%;padding:12px;border-radius:10px;border:1px solid #333;background:#16213e;color:#fff;font-size:16px;outline:none}
input[type=password]:focus{border-color:#00d4ff}
button{width:100%;padding:14px;border:none;border-radius:10px;background:linear-gradient(135deg,#00d4ff,#0078d4);color:#fff;font-size:16px;font-weight:700;cursor:pointer;margin-top:16px;transition:opacity 0.2s}
button:hover{opacity:0.9}
button:disabled{opacity:0.5;cursor:not-allowed}
#status{text-align:center;margin-top:14px;font-size:14px;min-height:20px}
.spinner{display:inline-block;width:16px;height:16px;border:2px solid #333;border-top-color:#00d4ff;border-radius:50%;animation:spin 0.8s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}
.hidden{display:none}
</style>
</head>
<body>
<div class="card">
<h1>&#128225; ESP32 WiFi Setup</h1>
<p class="sub">Meat Quality Monitor — Select your network</p>
<ul class="networks" id="networks">Loading networks...</ul>
<label id="passLabel" class="hidden">Password for <span id="selectedSsid"></span></label>
<input type="password" id="password" class="hidden" placeholder="Enter WiFi password">
<button id="connectBtn" class="hidden" onclick="doConnect()">Connect</button>
<div id="status"></div>
</div>
<script>
let selectedSsid='';
let pollInterval=null;
function rssiIcon(r){
  if(r>-50) return '&#128994;'; // green
  if(r>-70) return '&#128993;'; // yellow
  return '&#128308;'; // red
}
fetch('/scan').then(r=>r.json()).then(data=>{
  let html='';
  data.sort((a,b)=>b.rssi-a.rssi);
  data.forEach(n=>{
    let enc=n.enc?'&#128274;':'';
    html+=`<li onclick="selectNet('${n.ssid.replace(/'/g,"\\'")}')"><span class="ssid-text">${enc} ${n.ssid}</span><span class="rssi">${rssiIcon(n.rssi)}</span></li>`;
  });
  document.getElementById('networks').innerHTML=html||'<li>No networks found</li>';
}).catch(()=>{
  document.getElementById('networks').innerHTML='<li>Scan failed</li>';
});
function selectNet(ssid){
  selectedSsid=ssid;
  document.querySelectorAll('.networks li').forEach(li=>li.classList.remove('selected'));
  event.currentTarget.classList.add('selected');
  document.getElementById('selectedSsid').textContent=ssid;
  document.getElementById('passLabel').classList.remove('hidden');
  document.getElementById('password').classList.remove('hidden');
  document.getElementById('connectBtn').classList.remove('hidden');
  document.getElementById('password').focus();
}
function doConnect(){
  let pass=document.getElementById('password').value;
  document.getElementById('connectBtn').disabled=true;
  document.getElementById('status').innerHTML='<span class="spinner"></span>Connecting...';
  fetch('/connect?ssid='+encodeURIComponent(selectedSsid)+'&pass='+encodeURIComponent(pass))
    .then(r=>r.json()).then(data=>{
      if(data.status==='connecting'){
        pollInterval=setInterval(()=>{
          fetch('/status').then(r=>r.json()).then(d=>{
            if(d.connected){
              clearInterval(pollInterval);
              document.getElementById('status').innerHTML='<span style="color:#00d4ff">&#10004; Connected! Closing portal...</span>';
              setTimeout(()=>{document.getElementById('status').innerHTML+=' You can close this page.';},3000);
            } else if(d.status==='failed'){
              clearInterval(pollInterval);
              document.getElementById('status').innerHTML='<span style="color:#ff4444">&#10008; Connection failed. Try again.</span>';
              document.getElementById('connectBtn').disabled=false;
            }
          });
        },1000);
      } else {
        document.getElementById('status').innerHTML='<span style="color:#ff4444">'+data.message+'</span>';
        document.getElementById('connectBtn').disabled=false;
      }
    });
}
</script>
</body>
</html>
)rawliteral";

// Connection tracking for portal
bool portalConnecting    = false;
unsigned long portalConnectStart = 0;
String portalTargetSsid  = "";
String portalTargetPass  = "";

void startConfigPortal() {
    if (portalActive) return;

    Serial.println(F("\n╔══════════════════════════════════════╗"));
    Serial.println(F("║   STARTING WIFI CONFIGURATION PORTAL ║"));
    Serial.println(F("╚══════════════════════════════════════╝"));

    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    delay(100);

    Serial.printf("  AP: %s (pass: %s)\n", AP_SSID, AP_PASSWORD);
    Serial.printf("  Portal: http://%s\n", WiFi.softAPIP().toString().c_str());
    Serial.println(F("  Connect your phone to the AP above."));

    dnsServer = new DNSServer();
    dnsServer->start(53, "*", WiFi.softAPIP());

    portalServer = new WebServer(80);

    portalServer->on("/", HTTP_GET, []() {
        portalServer->send(200, "text/html", PORTAL_HTML);
    });

    portalServer->on("/scan", HTTP_GET, []() {
        int n = WiFi.scanNetworks();
        String json = "[";
        for (int i = 0; i < n; i++) {
            if (i > 0) json += ",";
            json += "{\"ssid\":\"" + WiFi.SSID(i) + "\",\"rssi\":" + String(WiFi.RSSI(i)) + ",\"enc\":" + String(WiFi.encryptionType(i) != WIFI_AUTH_OPEN ? "true" : "false") + "}";
        }
        json += "]";
        portalServer->send(200, "application/json", json);
    });

    portalServer->on("/connect", HTTP_GET, []() {
        if (!portalServer->hasArg("ssid")) {
            portalServer->send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing SSID\"}");
            return;
        }
        portalTargetSsid = portalServer->arg("ssid");
        portalTargetPass = portalServer->hasArg("pass") ? portalServer->arg("pass") : "";
        portalConnecting = true;
        portalConnectStart = millis();

        Serial.printf("[PORTAL] Connecting to: %s\n", portalTargetSsid.c_str());
        WiFi.begin(portalTargetSsid.c_str(), portalTargetPass.c_str());

        portalServer->send(200, "application/json", "{\"status\":\"connecting\"}");
    });

    portalServer->on("/status", HTTP_GET, []() {
        if (WiFi.status() == WL_CONNECTED) {
            portalServer->send(200, "application/json",
                "{\"connected\":true,\"ip\":\"" + WiFi.localIP().toString() + "\"}");
        } else if (portalConnecting && (millis() - portalConnectStart > 20000)) {
            portalServer->send(200, "application/json", "{\"connected\":false,\"status\":\"failed\"}");
            portalConnecting = false;
        } else {
            portalServer->send(200, "application/json", "{\"connected\":false,\"status\":\"connecting\"}");
        }
    });

    // Captive portal — catch-all for any other URL
    portalServer->onNotFound([]() {
        portalServer->send(200, "text/html", PORTAL_HTML);
    });

    portalServer->begin();
    portalActive = true;
    Serial.println(F("  Portal ready!\n"));
}

void stopConfigPortal() {
    if (!portalActive) return;

    Serial.println(F("[PORTAL] Stopping config portal..."));

    // Save credentials to EEPROM
    if (portalTargetSsid.length() > 0) {
        saveCredentials(portalTargetSsid.c_str(), portalTargetPass.c_str());
        strncpy(wifi_ssid, portalTargetSsid.c_str(), sizeof(wifi_ssid) - 1);
        strncpy(wifi_pass, portalTargetPass.c_str(), sizeof(wifi_pass) - 1);
    }

    portalServer->stop();
    delete portalServer;
    portalServer = nullptr;

    dnsServer->stop();
    delete dnsServer;
    dnsServer = nullptr;

    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);

    portalActive = false;
    portalConnecting = false;

    Serial.println(F("[PORTAL] Portal closed. Resuming normal operation.\n"));
}

void handlePortalLoop() {
    if (!portalActive) return;

    dnsServer->processNextRequest();
    portalServer->handleClient();

    // Check if WiFi connected during portal
    if (portalConnecting && WiFi.status() == WL_CONNECTED) {
        Serial.printf("[PORTAL] ✓ WiFi connected! IP: %s\n", WiFi.localIP().toString().c_str());
        Serial.println(F("[PORTAL] Closing portal in 5 seconds..."));

        // Send success to any pending status polls
        delay(5000);
        stopConfigPortal();

        // Restart NTP sync after new connection
        startNtpSync("portal connection");
    }
}

// ═══════════════════════════════════════════════════════════════
// WIFI CONNECTION
// ═══════════════════════════════════════════════════════════════

bool connectWiFi(const char* ssid, const char* pass, int timeoutMs = 30000) {
    Serial.printf("[WiFi] Connecting to: %s\n", ssid);

    // Full reset of WiFi stack
    WiFi.disconnect(true);
    delay(300);
    WiFi.mode(WIFI_STA);
    delay(100);

    // Pi hotspot BSSID and channel (fixed, never changes)
    // BSSID: 2C:CF:67:08:94:61, Channel: 1
    uint8_t bssid[6] = {0x2C, 0xCF, 0x67, 0x08, 0x94, 0x61};
    Serial.printf("[WiFi] Connecting with BSSID=%02X:%02X:%02X:%02X:%02X:%02X ch=1\n",
                  bssid[0], bssid[1], bssid[2], bssid[3], bssid[4], bssid[5]);

    // Use BSSID-specific connect to bypass ESP32 internal scan bug
    WiFi.begin(ssid, pass, 1, bssid);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start < timeoutMs)) {
        delay(500);
        Serial.print(F("."));
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] ✓ Connected! IP: %s, RSSI: %d dBm\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
        return true;
    }

    Serial.printf("\n[WiFi] ✗ Connection failed! (status: %d)\n", WiFi.status());
    // Fallback: try without BSSID
    Serial.println(F("[WiFi] Retrying without BSSID..."));
    WiFi.disconnect(true);
    delay(300);
    WiFi.mode(WIFI_STA);
    delay(100);
    WiFi.begin(ssid, pass);
    start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start < timeoutMs)) {
        delay(500);
        Serial.print(F("."));
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] ✓ Connected (fallback)! IP: %s, RSSI: %d dBm\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
        return true;
    }
    Serial.printf("\n[WiFi] ✗ Fallback also failed! (status: %d)\n", WiFi.status());
    return false;
}

// ═══════════════════════════════════════════════════════════════
// SENSOR CALCULATIONS
// ═══════════════════════════════════════════════════════════════

float calculateRS(float voltage) {
    if (voltage <= 0) return 0;
    return ((5.0 - voltage) / voltage) * RL;
}

float calculatePPM(float rs, float a, float b, float r0) {
    if (rs <= 0) return 0;
    float ratio = rs / r0;
    return pow((ratio / a), (1.0 / b));
}

// ═══════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println(F("\n╔══════════════════════════════════════════╗"));
    Serial.println(F("║  MQ135+MQ136+MQ137 — MQTT + Queue        ║"));
    Serial.println(F("║  ESP32 NodeMCU — SoftAP WiFi Portal      ║"));
    Serial.println(F("╚══════════════════════════════════════════╝\n"));

    // ADC
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    // I2C / BME280
    Wire.begin(BME_SDA_PIN, BME_SCL_PIN);
    Serial.printf("[BME280] I2C initialized on SDA=%d, SCL=%d\n", BME_SDA_PIN, BME_SCL_PIN);
    initBME280();

    // EEPROM
    EEPROM.begin(EEPROM_SIZE);

    // Force-overwrite EEPROM with Pi hotspot credentials (ensures correct network)
    Serial.println(F("[BOOT] Writing Pi hotspot credentials to EEPROM..."));
    strncpy(wifi_ssid, "MeatMonitor-Pi", sizeof(wifi_ssid) - 1);
    strncpy(wifi_pass, "MeatPi@12345", sizeof(wifi_pass) - 1);
    saveCredentials(wifi_ssid, wifi_pass);

    Serial.println(F("[BOOT] Connecting to Pi hotspot..."));
    if (connectWiFi(wifi_ssid, wifi_pass)) {
        startNtpSync("boot");
    } else {
        Serial.println(F("[BOOT] Pi hotspot connection failed."));
        Serial.println(F("[BOOT] Type '1' + Enter in Serial Monitor to configure WiFi."));
        if (!ENABLE_TIME_SYNC) {
            applyPresetTimeFallback();
        }
    }

    // Print config
    Serial.println(F(""));
    Serial.println(F("CONFIGURATION:"));
    Serial.printf("  MQTT Broker: %s:%d\n", MQTT_BROKER, MQTT_PORT);
    Serial.printf("  MQTT Topic: %s\n", MQTT_TOPIC);
    Serial.printf("  Device: %s\n", DEVICE_ID);
    Serial.printf("  Interval: %lu ms\n", READ_INTERVAL_MS);
    Serial.printf("  Queue: %d entries, drain %d/cycle\n", MAX_QUEUE, DRAIN_PER_CYCLE);
    Serial.printf("  Voltage Divider: 4.7k/9k (ratio %.4f)\n", VOLTAGE_DIVIDER_RATIO);
    Serial.printf("  NTP Timeout: %lu ms, Retry: %lu ms\n", NTP_SYNC_TIMEOUT_MS, NTP_RETRY_INTERVAL_MS);
    Serial.printf("  BME280: SDA=%d SCL=%d Addr=0x%02X/0x77 Status=%s\n",
                  BME_SDA_PIN, BME_SCL_PIN, BME_ADDRESS,
                  bmeReady ? "READY" : "NOT DETECTED");
    Serial.println(F(""));
    Serial.println(F("R0 VALUES (24-hour burn-in):"));
    Serial.printf("  MQ135: %.2f Ω\n", MQ135_R0);
    Serial.printf("  MQ136: %.2f Ω\n", MQ136_R0);
    Serial.printf("  MQ137: %.2f Ω\n", MQ137_R0);
    Serial.println(F(""));
    Serial.println(F("COMMANDS: Type '1' + Enter → WiFi config portal"));
    Serial.println(F(""));
    Serial.println(F("Starting sensor readings...\n"));

    // Configure MQTT endpoint (connection attempts happen in loop)
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setBufferSize(JSON_BUF_SIZE);
}

// ═══════════════════════════════════════════════════════════════
// LOOP
// ═══════════════════════════════════════════════════════════════

void loop() {
    // ── Check serial input for config trigger ──
    if (Serial.available()) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        if (input == "1" && !portalActive) {
            startConfigPortal();
        }
    }

    // ── Handle SoftAP portal if active ──
    if (portalActive) {
        handlePortalLoop();
        return;  // Don't do sensor readings while in config mode
    }

    handleTimeSync();

    // ── Check WiFi ──
    if (WiFi.status() != WL_CONNECTED) {
        if (strlen(wifi_ssid) > 0) {
            Serial.println(F("[WiFi] Disconnected! Reconnecting..."));
            if (!connectWiFi(wifi_ssid, wifi_pass, 10000)) {
                Serial.println(F("[WiFi] Reconnect failed. Will retry next cycle."));
                Serial.println(F("       Type '1' + Enter to reconfigure WiFi."));
            } else if (!ntpTimeSynced && ENABLE_TIME_SYNC) {
                startNtpSync(usingFallbackTime ? "reconnect while using preset time" : "reconnect");
            }
        }
        // If no credentials, just skip — user needs to type "1"
    }

    handleTimeSync();

    // Keep MQTT session alive / reconnect while WiFi is available
    ensureMqttConnection();
    if (mqttClient.connected()) {
        mqttClient.loop();
    }

    // ── Sensor reading cycle ──
    unsigned long currentTime = millis();
    if (!ntpTimeSynced && !fallbackTimeApplied) {
        if (currentTime - lastTimeWaitLogMs >= 2000) {
            Serial.println(F("[NTP] Waiting for initial sync (max 10s) before sending timestamped data..."));
            lastTimeWaitLogMs = currentTime;
        }
        return;
    }

    if (currentTime - lastReadTime < READ_INTERVAL_MS) {
        return;
    }
    lastReadTime = currentTime;

    if (!bmeReady && (lastBmeInitAttempt == 0 || currentTime - lastBmeInitAttempt >= BME_RETRY_MS)) {
        initBME280();
    }

    // ── 1. Drain queue first (up to DRAIN_PER_CYCLE) ──
    if (queueCount > 0 && WiFi.status() == WL_CONNECTED) {
        Serial.printf("[DRAIN] Queue has %d items, draining up to %d...\n", queueCount, DRAIN_PER_CYCLE);
        drainQueue();
    }

    // ── 2. Read sensors ──
    float temperatureC = NAN;
    float humidityRH = NAN;
    bool bmeReadOk = readBME280(temperatureC, humidityRH);

    int adcMQ135 = analogRead(MQ135_PIN);
    int adcMQ136 = analogRead(MQ136_PIN);
    int adcMQ137 = analogRead(MQ137_PIN);

    float vMQ135 = (adcMQ135 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float vMQ136 = (adcMQ136 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float vMQ137 = (adcMQ137 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;

    float rsMQ135 = calculateRS(vMQ135);
    float rsMQ136 = calculateRS(vMQ136);
    float rsMQ137 = calculateRS(vMQ137);

    float mq135_voc = calculatePPM(rsMQ135, MQ135_VOC_A, MQ135_VOC_B, MQ135_R0);
    float mq135_nh3 = calculatePPM(rsMQ135, MQ135_NH3_A, MQ135_NH3_B, MQ135_R0);
    float mq136_h2s = calculatePPM(rsMQ136, MQ136_H2S_A, MQ136_H2S_B, MQ136_R0);
    float mq136_nh3 = calculatePPM(rsMQ136, MQ136_NH3_A, MQ136_NH3_B, MQ136_R0);
    float mq136_co  = calculatePPM(rsMQ136, MQ136_CO_A,  MQ136_CO_B,  MQ136_R0);
    float mq137_nh3 = calculatePPM(rsMQ137, MQ137_NH3_A, MQ137_NH3_B, MQ137_R0);

    // ── 3. Quality assessment ──
    bool fresh    = (mq135_voc < 600) && (mq136_h2s < 5)  && (mq137_nh3 < 50);
    bool good     = (mq135_voc < 800) && (mq136_h2s < 10) && (mq137_nh3 < 100);
    bool moderate = (mq135_voc < 1000) && (mq136_h2s < 20) && (mq137_nh3 < 200);

    const char* qualityLevel;
    if (fresh)         qualityLevel = "EXCELLENT";
    else if (good)     qualityLevel = "GOOD";
    else if (moderate) qualityLevel = "FAIR";
    else               qualityLevel = "SPOILED";

    // ── 4. Print readings ──
    Serial.println(F("════════════════════════════════════════"));
    Serial.println(F("SENSOR READINGS:"));
    Serial.println(F("────────────────────────────────────────"));
    if (bmeReadOk) {
        Serial.printf("BME280 Temp:%.2f C  Hum:%.2f %%RH\n", temperatureC, humidityRH);
    } else {
        Serial.printf("BME280 Temp/Hum unavailable (%s)\n",
                      bmeReady ? "read failed" : "not detected");
    }
    Serial.printf("MQ135  ADC:%-4d V:%.3f Rs:%.1f  VOC:%.2f NH3:%.2f ppm\n",
                  adcMQ135, vMQ135, rsMQ135, mq135_voc, mq135_nh3);
    Serial.printf("MQ136  ADC:%-4d V:%.3f Rs:%.1f  H2S:%.2f NH3:%.2f CO:%.2f ppm\n",
                  adcMQ136, vMQ136, rsMQ136, mq136_h2s, mq136_nh3, mq136_co);
    Serial.printf("MQ137  ADC:%-4d V:%.3f Rs:%.1f  NH3:%.2f ppm\n",
                  adcMQ137, vMQ137, rsMQ137, mq137_nh3);
    Serial.println(F("────────────────────────────────────────"));
    Serial.printf("Quality: %s  VOC:%.1f H2S:%.1f NH3:%.1f\n",
                  qualityLevel, mq135_voc, mq136_h2s, mq137_nh3);

    // ── 5. Build JSON and send (or queue) ──
    char jsonBuf[JSON_BUF_SIZE];
    buildSensorJson(jsonBuf, temperatureC, humidityRH, bmeReadOk,
                    mq135_voc, mq135_nh3,
                    mq136_h2s, mq136_nh3, mq136_co,
                    mq137_nh3, qualityLevel);

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(F("[LIVE] Publishing current data via MQTT..."));
        int code = publishJson(jsonBuf);
        if (code == 200 || code == 201) {
            httpSuccessCount++;
            Serial.println(F("✓ Live data published"));
        } else {
            Serial.printf("✗ Live publish failed (status %d) — queuing\n", code);
            enqueue(jsonBuf);
            httpFailCount++;
        }
    } else {
        Serial.println(F("✗ No WiFi — queuing data"));
        enqueue(jsonBuf);
        httpFailCount++;
    }

    // ── 6. Stats ──
    Serial.println(F("────────────────────────────────────────"));
    Serial.printf("Stats ✓:%d ✗:%d | Queue:%d/%d Drained:%d Dropped:%d\n",
                  httpSuccessCount, httpFailCount,
                  queueCount, MAX_QUEUE, queueDrainCount, queueDropCount);
    Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
    Serial.println(F("════════════════════════════════════════\n"));
}
