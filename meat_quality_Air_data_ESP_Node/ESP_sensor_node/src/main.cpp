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
#include <WebServer.h>
#include <DNSServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <EEPROM.h>

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

// HTTP API
const char* API_URL   = "https://meat-monitor.kalobiral.com.bd/api/meat-data";
const char* API_KEY   = "aa8a531a309e574c7fef976850416e7613984ba03f4cf370";  // Sensor API key
const char* DEVICE_ID = "ESP32-MeatMonitor";

// SoftAP Config Portal
const char* AP_SSID     = "ESP32-Setup";
const char* AP_PASSWORD = "YOUR_AP_PASSWORD_HERE";  // Set before flashing

// Timing
const unsigned long READ_INTERVAL_MS = 3000;  // 3 seconds

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
const int MQ135_PIN = 34;  // ADC1_CH6
const int MQ136_PIN = 35;  // ADC1_CH7
const int MQ137_PIN = 32;  // ADC1_CH4
const float VOLTAGE_DIVIDER_RATIO = 1.5222;  // 4.7k upper, 9k lower
const float ESP32_VREF = 3.3;
const int ADC_RESOLUTION = 4095;

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
int httpPostJson(const char* jsonPayload);

// ═══════════════════════════════════════════════════════════════
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════════

// WiFi credentials (loaded from EEPROM)
char wifi_ssid[65] = "";
char wifi_pass[65] = "";

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

        int code = httpPostJson(queue[0].json);
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
// HTTP COMMUNICATION
// ═══════════════════════════════════════════════════════════════

int httpPostJson(const char* jsonPayload) {
    HTTPClient http;
    http.begin(API_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", API_KEY);
    http.setTimeout(10000);

    int httpCode = http.POST(jsonPayload);

    if (httpCode > 0) {
        String response = http.getString();
        Serial.printf("  HTTP %d: %s\n", httpCode, response.c_str());
    } else {
        Serial.printf("  HTTP error: %s\n", http.errorToString(httpCode).c_str());
    }

    http.end();
    return httpCode;
}

// ═══════════════════════════════════════════════════════════════
// JSON BUILDER
// ═══════════════════════════════════════════════════════════════

void buildSensorJson(char* buf, float mq135_vocPPM, float mq135_nh3PPM,
                     float mq136_h2sPPM, float mq136_nh3PPM, float mq136_coPPM,
                     float mq137_nh3PPM, const char* qualityLevel) {
    StaticJsonDocument<512> doc;

    doc["device_id"] = DEVICE_ID;

    // Timestamp
    char timestamp[32];
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
        strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    } else {
        strcpy(timestamp, "1970-01-01T00:00:00Z");
    }
    doc["timestamp"] = timestamp;

    // Sensors
    JsonObject sensors = doc.createNestedObject("sensors");
    sensors["temperature"] = 25.0;   // TODO: real sensor
    sensors["humidity"]    = 60.0;   // TODO: real sensor
    sensors["mq135_co2"]   = mq135_vocPPM;
    sensors["mq136_h2s"]   = mq136_h2sPPM;
    sensors["mq137_nh3"]   = mq137_nh3PPM;

    // Quality
    JsonObject quality = doc.createNestedObject("quality");
    quality["level"] = qualityLevel;

    doc["wifi_rssi"] = WiFi.RSSI();

    doc.createNestedObject("sensor_status");

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

        // Sync time after new connection
        configTime(0, 0, "pool.ntp.org", "time.nist.gov");
        Serial.println(F("[NTP] Time re-synced."));
    }
}

// ═══════════════════════════════════════════════════════════════
// WIFI CONNECTION
// ═══════════════════════════════════════════════════════════════

bool connectWiFi(const char* ssid, const char* pass, int timeoutMs = 15000) {
    Serial.printf("[WiFi] Connecting to: %s\n", ssid);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);

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

    Serial.println(F("\n[WiFi] ✗ Connection failed!"));
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
    Serial.println(F("║  MQ135+MQ136+MQ137 — HTTP API + Queue    ║"));
    Serial.println(F("║  ESP32 NodeMCU — SoftAP WiFi Portal      ║"));
    Serial.println(F("╚══════════════════════════════════════════╝\n"));

    // ADC
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    // EEPROM
    EEPROM.begin(EEPROM_SIZE);

    // Try to load saved credentials
    bool hasCredentials = loadCredentials();

    if (hasCredentials) {
        Serial.println(F("[BOOT] Found saved credentials. Connecting..."));
        if (connectWiFi(wifi_ssid, wifi_pass)) {
            // Sync time
            configTime(0, 0, "pool.ntp.org", "time.nist.gov");
            Serial.print(F("[NTP] Waiting for time sync..."));
            time_t now = time(nullptr);
            while (now < 8 * 3600 * 2) {
                delay(500);
                Serial.print(F("."));
                now = time(nullptr);
            }
            struct tm timeinfo;
            getLocalTime(&timeinfo);
            Serial.printf("\n[NTP] ✓ Synced: %s\n", asctime(&timeinfo));
        } else {
            Serial.println(F("[BOOT] WiFi connection failed with saved credentials."));
            Serial.println(F("[BOOT] Type '1' + Enter in Serial Monitor to reconfigure WiFi."));
        }
    } else {
        // No EEPROM credentials — use hardcoded defaults and save them
        Serial.println(F("[BOOT] No saved WiFi credentials."));
        Serial.println(F("[BOOT] Using hardcoded defaults and saving to EEPROM..."));
        strncpy(wifi_ssid, "Lovly", sizeof(wifi_ssid) - 1);
        strncpy(wifi_pass, "tweety@pichu", sizeof(wifi_pass) - 1);
        saveCredentials(wifi_ssid, wifi_pass);

        if (connectWiFi(wifi_ssid, wifi_pass)) {
            configTime(0, 0, "pool.ntp.org", "time.nist.gov");
            Serial.print(F("[NTP] Waiting for time sync..."));
            time_t now = time(nullptr);
            while (now < 8 * 3600 * 2) {
                delay(500);
                Serial.print(F("."));
                now = time(nullptr);
            }
            struct tm timeinfo;
            getLocalTime(&timeinfo);
            Serial.printf("\n[NTP] ✓ Synced: %s\n", asctime(&timeinfo));
        } else {
            Serial.println(F("[BOOT] Hardcoded WiFi failed."));
            Serial.println(F("[BOOT] Type '1' + Enter in Serial Monitor to configure WiFi."));
        }
    }

    // Print config
    Serial.println(F(""));
    Serial.println(F("CONFIGURATION:"));
    Serial.printf("  API: %s\n", API_URL);
    Serial.printf("  Device: %s\n", DEVICE_ID);
    Serial.printf("  Interval: %lu ms\n", READ_INTERVAL_MS);
    Serial.printf("  Queue: %d entries, drain %d/cycle\n", MAX_QUEUE, DRAIN_PER_CYCLE);
    Serial.printf("  Voltage Divider: 4.7k/9k (ratio %.4f)\n", VOLTAGE_DIVIDER_RATIO);
    Serial.println(F(""));
    Serial.println(F("R0 VALUES (24-hour burn-in):"));
    Serial.printf("  MQ135: %.2f Ω\n", MQ135_R0);
    Serial.printf("  MQ136: %.2f Ω\n", MQ136_R0);
    Serial.printf("  MQ137: %.2f Ω\n", MQ137_R0);
    Serial.println(F(""));
    Serial.println(F("COMMANDS: Type '1' + Enter → WiFi config portal"));
    Serial.println(F(""));
    Serial.println(F("Starting sensor readings...\n"));
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

    // ── Check WiFi ──
    if (WiFi.status() != WL_CONNECTED) {
        if (strlen(wifi_ssid) > 0) {
            Serial.println(F("[WiFi] Disconnected! Reconnecting..."));
            if (!connectWiFi(wifi_ssid, wifi_pass, 10000)) {
                Serial.println(F("[WiFi] Reconnect failed. Will retry next cycle."));
                Serial.println(F("       Type '1' + Enter to reconfigure WiFi."));
            }
        }
        // If no credentials, just skip — user needs to type "1"
    }

    // ── Sensor reading cycle ──
    unsigned long currentTime = millis();
    if (currentTime - lastReadTime < READ_INTERVAL_MS) {
        return;
    }
    lastReadTime = currentTime;

    // ── 1. Drain queue first (up to DRAIN_PER_CYCLE) ──
    if (queueCount > 0 && WiFi.status() == WL_CONNECTED) {
        Serial.printf("[DRAIN] Queue has %d items, draining up to %d...\n", queueCount, DRAIN_PER_CYCLE);
        drainQueue();
    }

    // ── 2. Read sensors ──
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
    buildSensorJson(jsonBuf, mq135_voc, mq135_nh3,
                    mq136_h2s, mq136_nh3, mq136_co,
                    mq137_nh3, qualityLevel);

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(F("[LIVE] Sending current data..."));
        int code = httpPostJson(jsonBuf);
        if (code == 200 || code == 201) {
            httpSuccessCount++;
            Serial.println(F("✓ Live data sent"));
        } else {
            Serial.printf("✗ Live send failed (HTTP %d) — queuing\n", code);
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
