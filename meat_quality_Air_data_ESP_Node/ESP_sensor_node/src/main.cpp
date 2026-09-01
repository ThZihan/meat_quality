/*
 * ═══════════════════════════════════════════════════════════════════════════
 * Meat Quality Air Sensor Node — BLE-only firmware
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * MQ135 (VOC) + MQ136 (H2S) + MQ137 (NH3) + BME280 (temp/humidity/pressure)
 *
 * There is NO WiFi, NO HTTP, and NO NTP in this build. The node's only link is
 * BLE to the Raspberry Pi sitting ~10 inches away, which owns the uplink to the
 * cloud. That makes the Pi the single place where data durability is decided,
 * and it means a dead server can no longer cost us readings.
 *
 * ── Delivery guarantee ─────────────────────────────────────────────────────
 * Every reading gets a monotonic uint32 sequence number and stays queued until
 * the Pi acknowledges it. The Pi commits the row to SQLite BEFORE it ACKs, so
 * an acknowledgement always means "durably stored", never "received". If the
 * Pi disconnects, reboots, or its service restarts, the ESP keeps the backlog
 * and replays it on reconnect. Retransmits are harmless: the Pi collapses them
 * on a UNIQUE index over (device_id:seq).
 *
 * ── Clock handling (never blocks sending) ──────────────────────────────────
 * With no WiFi there is no NTP. Two independent mechanisms cover timestamps,
 * and neither is allowed to gate the send path:
 *
 *   1. The Pi pushes epoch-millis on connect (TIME characteristic). The ESP
 *      records an offset and can then stamp readings with real wall time --
 *      including retroactively resolving anything already queued this boot.
 *   2. Every transmission carries "ag", the age in ms between capture and this
 *      send, taken from the monotonic uptime counter. The Pi subtracts that
 *      from its own clock.
 *
 * If the Pi never pushes the time, readings still flow and still land with an
 * accurate timestamp via mechanism 2. The clock is an optimization, not a
 * prerequisite.
 *
 * ── Flash wear ─────────────────────────────────────────────────────────────
 * The queue lives in RAM and is only checkpointed to NVS when the backlog
 * suggests the Pi is actually gone (see QUEUE_PERSIST_THRESHOLD), rate-limited
 * to one write per minute. During normal operation -- Pi connected, backlog
 * empty -- the firmware performs zero flash writes. Sequence numbers are
 * likewise reserved in blocks of SEQ_BLOCK so the counter costs one write per
 * ~1000 readings rather than one per reading.
 * ═══════════════════════════════════════════════════════════════════════════
 */

#include <Arduino.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_BME280.h>
#include <Preferences.h>
#include <NimBLEDevice.h>

// ═══════════════════════════════════════════════════════════════
// IDENTITY & GATT PROFILE
// Keep these byte-identical to meat-quality-monitoring/ble_protocol.py
// ═══════════════════════════════════════════════════════════════

const char* DEVICE_ID   = "ESP32-MeatMonitor";
const char* DEVICE_NAME = "MeatNode";

#define SVC_UUID     "19859e41-e7f2-41cc-b771-2b33ce845fb2"
#define CH_DATA_UUID "0a09c96d-05e0-495f-a8c4-2fb19c75a695"  // notify  ESP -> Pi
#define CH_ACK_UUID  "8b4d8427-af8d-4979-b233-6e1d95eab4ea"  // write   Pi  -> ESP
#define CH_TIME_UUID "fc8acb7e-b802-4f11-8dce-58212ff25092"  // write   Pi  -> ESP
#define CH_STAT_UUID "33db1a8b-1226-49cb-9dfb-2eeab1d3ef01"  // read    Pi  <- ESP

// ═══════════════════════════════════════════════════════════════
// TIMING & QUEUE SIZING
// ═══════════════════════════════════════════════════════════════

const unsigned long READ_INTERVAL_MS   = 3000;  // one reading every 3 s
const unsigned long ACK_TIMEOUT_MS     = 4000;  // re-send if unacked this long
const unsigned long SEND_GAP_MS        = 60;    // spacing while draining backlog

// 1200 x 3 s = 1 hour of backlog held in RAM (~53 KB of the ESP32's 320 KB).
// Sized to cover a Pi reboot, a failed service restart, or a short power cut on
// the Pi without dropping anything. Beyond this the oldest readings are shed --
// the node has finite memory, so a multi-hour Pi outage is the one scenario
// that can still cost data. Free heap is logged at boot so the margin against
// the NimBLE stack stays visible.
const uint16_t QUEUE_CAPACITY = 1200;

// Only checkpoint to flash once the backlog looks like a real outage
// (20 readings = ~1 minute), and never more than once a minute.
const uint16_t      QUEUE_PERSIST_THRESHOLD = 20;
const unsigned long QUEUE_PERSIST_MIN_GAP_MS = 60000;

// Upper bound on how many readings are written to flash in one checkpoint.
// The RAM queue holds 720, but persisting all of it is 31 KiB -- more than the
// stock 20 KiB `nvs` partition can store. Those writes failed silently, the
// recorded length promised data the blob did not contain, and the node
// eventually wedged. 128 readings is 5,632 bytes, which fits the stock
// partition with room to spare and keeps the flash-cache-disabled window short
// while BLE is running. The OLDEST readings are kept: they are the ones
// closest to being dropped from the ring.
//
// Consequence, deliberately accepted: a power cut during an outage longer than
// ~6 minutes loses the readings beyond this bound. The RAM queue still covers
// 36 minutes of Pi downtime, which is the failure this design actually targets.
const uint16_t QUEUE_PERSIST_MAX = 128;

// Sequence numbers are handed out from pre-reserved blocks so the NVS counter
// is written once per block instead of once per reading. A reboot burns the
// remainder of the current block -- harmless, since seq only has to be unique
// and increasing, not gap-free.
const uint32_t SEQ_BLOCK = 1000;

// ═══════════════════════════════════════════════════════════════
// SENSOR HARDWARE (unchanged from the WiFi build — same board, same wiring)
// ═══════════════════════════════════════════════════════════════

const int I2C_SDA = 25;
const int I2C_SCL = 26;

const int MQ135_PIN = 34;  // ADC1_CH6
const int MQ136_PIN = 35;  // ADC1_CH7
const int MQ137_PIN = 32;  // ADC1_CH4

const float DIVIDER_UPPER_OHMS = 68000.0;    // MQ AOUT -> ADC node
const float DIVIDER_LOWER_OHMS = 100000.0;   // ADC node -> GND
const float VOLTAGE_DIVIDER_RATIO =
    (DIVIDER_UPPER_OHMS + DIVIDER_LOWER_OHMS) / DIVIDER_LOWER_OHMS;

const float ESP32_VREF      = 3.3;
const int   ADC_RESOLUTION  = 4095;
const int   ADC_SAMPLE_COUNT = 32;

const float MQ_MODULE_RL_OHMS   = 10000.0;
const float DIVIDER_BRANCH_OHMS = DIVIDER_UPPER_OHMS + DIVIDER_LOWER_OHMS;
const float EFFECTIVE_RL_OHMS =
    (MQ_MODULE_RL_OHMS * DIVIDER_BRANCH_OHMS) / (MQ_MODULE_RL_OHMS + DIVIDER_BRANCH_OHMS);

// Calibrated in clean air — carried over verbatim from the WiFi firmware.
const float MQ135_R0 = 193200.00;
const float MQ136_R0 = 85102.55;
const float MQ137_R0 = 51913.09;

const float MQ135_VOC_A = 110.47,  MQ135_VOC_B = -2.862;
const float MQ136_H2S_A = 44.947,  MQ136_H2S_B = -2.648;
const float MQ137_NH3_A = 102.2,   MQ137_NH3_B = -2.473;

// Temperature correction for MQ heater self-heating.
//
// The three MQ elements run their heaters continuously and sit close to the
// BME280 inside the same enclosure, so the part reads the enclosure rather than
// the air around the sample. Established against a reference thermometer placed
// in the box: reference 28.50 C, BME280 33.638 C (mean of 20 consecutive
// readings, spread 33.58-33.75).
//
// This is a single-point correction and is only valid near the ambient it was
// taken at. Self-heating scales with the heater-to-ambient difference, so this
// figure must be re-established if the enclosure is run at a materially
// different temperature.
const float TEMP_OFFSET_C = -5.14;

Adafruit_BME280 bme;
bool bmeReady = false;

// ═══════════════════════════════════════════════════════════════
// QUALITY LEVELS
// The server rejects anything outside this set with HTTP 400.
// ═══════════════════════════════════════════════════════════════

enum QualityLevel : uint8_t { Q_EXCELLENT = 0, Q_GOOD, Q_MODERATE, Q_POOR, Q_CRITICAL };
const char* const QUALITY_NAMES[] = { "EXCELLENT", "GOOD", "MODERATE", "POOR", "CRITICAL" };

// ═══════════════════════════════════════════════════════════════
// QUEUE
// ═══════════════════════════════════════════════════════════════

struct Reading {
    uint32_t seq;
    uint32_t uptimeMs;   // millis() at capture — monotonic within one boot
    uint32_t epoch;      // epoch seconds, 0 while the ESP has no clock
    uint32_t bootId;     // boot that captured it; guards the uptime maths
    float    temperature, humidity, pressure;
    float    mq135, mq136, mq137;
    uint8_t  quality;
    uint8_t  bmeOk;
};

Reading  queueBuf[QUEUE_CAPACITY];
uint16_t queueHead  = 0;   // oldest unacked
uint16_t queueCount = 0;

uint32_t nextSeq       = 1;
uint32_t seqHighWater  = 0;   // reserved-up-to value stored in NVS
uint32_t bootId        = 0;
uint32_t lastAckedSeq  = 0;

// Wall clock, supplied by the Pi. epochOffsetMs + millis() = epoch millis.
volatile bool     clockValid    = false;
volatile uint64_t epochOffsetMs = 0;

// Diagnostics
uint32_t lastSentSeq    = 0;   // highest seq actually put on the air
uint16_t connHandle     = BLE_HS_CONN_HANDLE_NONE;
volatile bool persistRequested = false;
uint32_t droppedCount   = 0;
uint32_t deliveredCount = 0;
uint32_t resendCount    = 0;

Preferences prefs;

unsigned long lastReadMs    = 0;
unsigned long lastSendMs    = 0;
unsigned long lastPersistMs = 0;
bool          queueDirty    = false;

// ═══════════════════════════════════════════════════════════════
// BLE STATE
// ═══════════════════════════════════════════════════════════════

NimBLEServer*         bleServer  = nullptr;
NimBLECharacteristic* dataChar   = nullptr;
NimBLECharacteristic* statusChar = nullptr;
volatile bool         piConnected  = false;
volatile bool         piSubscribed = false;

// ═══════════════════════════════════════════════════════════════
// NVS PERSISTENCE
// ═══════════════════════════════════════════════════════════════

void reserveSeqBlock() {
    seqHighWater += SEQ_BLOCK;
    prefs.putUInt("seq_hwm", seqHighWater);
}

uint32_t takeSeq() {
    // Sequence numbers start at 1, never 0. Zero is the "nothing acknowledged
    // yet" sentinel for lastAckedSeq, so a reading numbered 0 could never be
    // acknowledged (ackUpTo returns early on seq <= lastAckedSeq) and the node
    // would retransmit it forever. Only ever hit on a freshly erased NVS.
    if (nextSeq == 0) nextSeq = 1;
    if (nextSeq >= seqHighWater) reserveSeqBlock();
    return nextSeq++;
}

// Persist the unacked backlog so a power cut during an outage does not lose it.
void persistQueue(bool force = false) {
    if (!queueDirty && !force) return;
    if (!force && millis() - lastPersistMs < QUEUE_PERSIST_MIN_GAP_MS) return;

    uint16_t n = queueCount < QUEUE_PERSIST_MAX ? queueCount : QUEUE_PERSIST_MAX;
    if (n == 0) {
        prefs.remove("q_data");
        prefs.putUShort("q_len", 0);
        lastPersistMs = millis();
        queueDirty = false;
        Serial.println(F("[NVS] Checkpoint cleared (queue empty)"));
        return;
    }

    // Flatten the ring into a contiguous blob starting at the oldest entry.
    static Reading flat[QUEUE_PERSIST_MAX];
    for (uint16_t i = 0; i < n; i++) {
        flat[i] = queueBuf[(queueHead + i) % QUEUE_CAPACITY];
    }

    size_t want = (size_t)n * sizeof(Reading);
    size_t wrote = prefs.putBytes("q_data", flat, want);
    if (wrote != want) {
        // Record the failure rather than leaving a q_len that promises data
        // the blob does not contain -- that is what made restore silently
        // discard everything after the last wedge.
        prefs.putUShort("q_len", 0);
        lastPersistMs = millis();
        Serial.printf("[NVS] Checkpoint FAILED: wrote %u of %u bytes\n",
                      (unsigned)wrote, (unsigned)want);
        return;
    }
    prefs.putUShort("q_len", n);
    lastPersistMs = millis();
    queueDirty = false;
    Serial.printf("[NVS] Checkpointed %u of %u queued reading(s) (%u bytes)\n",
                  n, queueCount, (unsigned)want);
}

void restoreQueue() {
    uint16_t n = prefs.getUShort("q_len", 0);
    if (n == 0 || n > QUEUE_PERSIST_MAX) return;

    size_t expected = (size_t)n * sizeof(Reading);
    if (prefs.getBytesLength("q_data") != expected) {
        Serial.println(F("[NVS] Stored queue has an unexpected size — discarding"));
        prefs.remove("q_data");
        prefs.putUShort("q_len", 0);
        return;
    }
    prefs.getBytes("q_data", queueBuf, expected);
    queueHead  = 0;
    queueCount = n;

    // Drop anything numbered 0. Zero is the "nothing acknowledged yet"
    // sentinel, so such a reading can never be acknowledged and would sit at
    // the head of the queue blocking every reading behind it forever. Only
    // ever produced by a pre-fix build, but the queue survives reflashes.
    uint16_t dropped = 0;
    while (queueCount > 0 && queueBuf[queueHead].seq == 0) {
        queueHead = (queueHead + 1) % QUEUE_CAPACITY;
        queueCount--;
        dropped++;
    }
    if (dropped) {
        queueDirty = true;
        Serial.printf("[NVS] Discarded %u un-acknowledgeable reading(s) numbered 0\n",
                      dropped);
    }
    Serial.printf("[NVS] Restored %u reading(s) from before the reboot\n", queueCount);
}

// ═══════════════════════════════════════════════════════════════
// QUEUE OPERATIONS
// ═══════════════════════════════════════════════════════════════

void enqueue(const Reading& r) {
    if (queueCount == QUEUE_CAPACITY) {
        // Full: drop the oldest. At 3 s/reading this needs a 36-minute outage.
        queueHead = (queueHead + 1) % QUEUE_CAPACITY;
        queueCount--;
        droppedCount++;
        Serial.printf("[QUEUE] Full — dropped oldest (total dropped: %lu)\n",
                      (unsigned long)droppedCount);
    }
    queueBuf[(queueHead + queueCount) % QUEUE_CAPACITY] = r;
    queueCount++;
    queueDirty = true;

    if (queueCount >= QUEUE_PERSIST_THRESHOLD) persistQueue();
}

// Drop everything the Pi has confirmed it stored.
void ackUpTo(uint32_t seq) {
    if (seq <= lastAckedSeq) return;
    lastAckedSeq = seq;

    uint16_t removed = 0;
    while (queueCount > 0 && queueBuf[queueHead].seq <= seq) {
        queueHead = (queueHead + 1) % QUEUE_CAPACITY;
        queueCount--;
        removed++;
        deliveredCount++;
    }
    if (removed) {
        queueDirty = true;
        // Clear the in-flight marker. Without this the reading that just moved
        // to the head is judged "in flight" against the previous send's
        // timestamp, so it waits the full ACK timeout (4 s) before going out --
        // turning a backlog drain into one reading every four seconds.
        lastSendMs = 0;
        Serial.printf("[ACK] seq<=%lu confirmed — %u cleared, %u still queued\n",
                      (unsigned long)seq, removed, queueCount);
        // The backlog is gone; clear the flash copy so a reboot cannot resurrect it.
        if (queueCount == 0) persistQueue(true);
    }
}

// Once the Pi gives us the time, back-fill every reading captured this boot.
void resolveQueuedEpochs() {
    if (!clockValid) return;
    uint32_t fixed = 0;
    for (uint16_t i = 0; i < queueCount; i++) {
        Reading& r = queueBuf[(queueHead + i) % QUEUE_CAPACITY];
        if (r.epoch == 0 && r.bootId == bootId) {
            r.epoch = (uint32_t)((epochOffsetMs + r.uptimeMs) / 1000ULL);
            fixed++;
        }
    }
    if (fixed) {
        queueDirty = true;
        Serial.printf("[TIME] Back-filled timestamps for %lu queued reading(s)\n",
                      (unsigned long)fixed);
    }
}

// ═══════════════════════════════════════════════════════════════
// BLE CALLBACKS
// ═══════════════════════════════════════════════════════════════

class ServerCallbacks : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* srv, NimBLEConnInfo& info) override {
        piConnected = true;
        connHandle = info.getConnHandle();
        Serial.printf("[BLE] Pi connected (handle %u)\n", connHandle);
    }

    void onDisconnect(NimBLEServer* srv, NimBLEConnInfo& info, int reason) override {
        piConnected = false;
        piSubscribed = false;
        connHandle = BLE_HS_CONN_HANDLE_NONE;
        lastSendMs = 0;
        Serial.printf("[BLE] Pi disconnected (reason 0x%03X) — queueing locally\n", reason);
        persistRequested = true;   // loop() owns flash; see note above
        NimBLEDevice::startAdvertising();
    }

    void onMTUChange(uint16_t mtu, NimBLEConnInfo& info) override {
        Serial.printf("[BLE] MTU negotiated: %u bytes\n", mtu);
    }
};

class AckCallbacks : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* ch, NimBLEConnInfo& info) override {
        NimBLEAttValue v = ch->getValue();
        Serial.printf("[ACK] write: %u byte(s):", (unsigned)v.length());
        for (size_t i = 0; i < v.length() && i < 12; i++) Serial.printf(" %02X", v.data()[i]);
        Serial.println();

        if (v.length() != 4) {
            Serial.println(F("[ACK] Ignored: an ACK is exactly 4 bytes"));
            return;
        }
        uint32_t seq;
        memcpy(&seq, v.data(), 4);   // little-endian, matches struct.pack('<I')

        // Never trust an ACK for a sequence number we have not actually sent.
        // A stale or spurious write must not be able to discard queued data.
        if (seq > lastSentSeq) {
            Serial.printf("[ACK] Rejected seq %lu: nothing above %lu has been sent\n",
                          (unsigned long)seq, (unsigned long)lastSentSeq);
            return;
        }
        ackUpTo(seq);
    }
};

class TimeCallbacks : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* ch, NimBLEConnInfo& info) override {
        NimBLEAttValue v = ch->getValue();
        if (v.length() < 8) return;
        uint64_t epochMs;
        memcpy(&epochMs, v.data(), 8);

        // Offset rather than absolute time: millis() keeps ticking regardless,
        // so the clock cannot drift away from the sequence of readings.
        epochOffsetMs = epochMs - (uint64_t)millis();
        clockValid = true;
        Serial.printf("[TIME] Clock set from Pi: epoch %llu ms\n",
                      (unsigned long long)epochMs);
        resolveQueuedEpochs();
    }
};

class DataCallbacks : public NimBLECharacteristicCallbacks {
    void onSubscribe(NimBLECharacteristic* ch, NimBLEConnInfo& info, uint16_t subValue) override {
        piSubscribed = (subValue > 0);
        Serial.printf("[BLE] Pi %s notifications\n",
                      piSubscribed ? "subscribed to" : "unsubscribed from");
        if (piSubscribed) lastSendMs = 0;   // start draining immediately
    }
};

// ═══════════════════════════════════════════════════════════════
// SENSOR HELPERS (carried over unchanged — same math, same calibration)
// ═══════════════════════════════════════════════════════════════

float calculateRS(float voltage) {
    if (voltage <= 0) return 0;
    return ((5.0 - voltage) / voltage) * EFFECTIVE_RL_OHMS;
}

float calculatePPM(float rs, float a, float b, float r0) {
    if (rs <= 0) return 0;
    float ratio = rs / r0;
    return pow((ratio / a), (1.0 / b));
}

// The 68k/100k divider has a high source impedance. Discarding one conversion
// and averaging 32 suppresses ESP32 ADC mux/sample-and-hold noise.
int readFilteredADC(int pin) {
    analogRead(pin);
    delayMicroseconds(500);
    uint32_t sum = 0;
    for (int i = 0; i < ADC_SAMPLE_COUNT; i++) {
        sum += analogRead(pin);
        delayMicroseconds(250);
    }
    return (int)((sum + ADC_SAMPLE_COUNT / 2) / ADC_SAMPLE_COUNT);
}

bool readI2CRegister(uint8_t address, uint8_t reg, uint8_t& value) {
    Wire.beginTransmission(address);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom((int)address, 1) != 1) return false;
    value = Wire.read();
    return true;
}

void initBME280() {
    Serial.printf("[BME280] Probing I2C (SDA=GPIO%d SCL=GPIO%d)...\n", I2C_SDA, I2C_SCL);
    const uint32_t probeSpeeds[] = {10000, 50000, 100000};
    for (uint32_t speed : probeSpeeds) {
        Wire.setClock(speed);
        for (uint8_t address : {0x76, 0x77}) {
            Wire.beginTransmission(address);
            if (Wire.endTransmission() != 0) continue;

            uint8_t id = 0;
            if (readI2CRegister(address, 0xD0, id)) {
                Serial.printf("[BME280] ACK at 0x%02X, chip ID 0x%02X (%lu Hz)\n",
                              address, id, (unsigned long)speed);
                if (id == 0x58) {
                    Serial.println(F("[BME280] BMP280 silicon: temp/pressure only, no humidity"));
                }
            }
            if (id == 0x60 && bme.begin(address, &Wire)) {
                bmeReady = true;
                Wire.setClock(100000);
                Serial.printf("[BME280] Initialized at 0x%02X\n", address);
                return;
            }
        }
    }
    Wire.setClock(100000);
    bmeReady = false;
    Serial.println(F("[BME280] Not found — falling back to 25.0C / 60.0% / 1013.25 hPa"));
}

// ═══════════════════════════════════════════════════════════════
// CAPTURE
// ═══════════════════════════════════════════════════════════════

Reading captureReading() {
    Reading r{};
    r.seq      = takeSeq();
    r.uptimeMs = millis();
    r.bootId   = bootId;
    r.epoch    = clockValid
                 ? (uint32_t)((epochOffsetMs + (uint64_t)r.uptimeMs) / 1000ULL)
                 : 0;

    int adc135 = readFilteredADC(MQ135_PIN);
    int adc136 = readFilteredADC(MQ136_PIN);
    int adc137 = readFilteredADC(MQ137_PIN);

    float v135 = (adc135 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float v136 = (adc136 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;
    float v137 = (adc137 / (float)ADC_RESOLUTION) * ESP32_VREF * VOLTAGE_DIVIDER_RATIO;

    r.mq135 = calculatePPM(calculateRS(v135), MQ135_VOC_A, MQ135_VOC_B, MQ135_R0);
    r.mq136 = calculatePPM(calculateRS(v136), MQ136_H2S_A, MQ136_H2S_B, MQ136_R0);
    r.mq137 = calculatePPM(calculateRS(v137), MQ137_NH3_A, MQ137_NH3_B, MQ137_R0);

    if (bmeReady) {
        r.temperature = bme.readTemperature() + TEMP_OFFSET_C;
        r.humidity    = bme.readHumidity();
        r.pressure    = bme.readPressure() / 100.0F;
        r.bmeOk       = 1;
    } else {
        r.temperature = 25.0;
        r.humidity    = 60.0;
        r.pressure    = 1013.25;
        r.bmeOk       = 0;
    }

    // Thresholds unchanged from the WiFi firmware.
    bool fresh    = (r.mq135 < 600)  && (r.mq136 < 5)  && (r.mq137 < 50);
    bool good     = (r.mq135 < 800)  && (r.mq136 < 10) && (r.mq137 < 100);
    bool moderate = (r.mq135 < 1000) && (r.mq136 < 20) && (r.mq137 < 200);

    if (fresh)         r.quality = Q_EXCELLENT;
    else if (good)     r.quality = Q_GOOD;
    else if (moderate) r.quality = Q_MODERATE;
    else               r.quality = Q_CRITICAL;

    return r;
}

// ═══════════════════════════════════════════════════════════════
// TRANSMIT
// ═══════════════════════════════════════════════════════════════

// Short keys keep a full reading inside one notification (~244 usable bytes),
// so nothing has to be fragmented and reassembled.
void buildPayload(const Reading& r, char* out, size_t outSize) {
    StaticJsonDocument<256> doc;
    doc["q"]  = r.seq;
    doc["ag"] = (uint32_t)(millis() - r.uptimeMs);
    doc["ep"] = r.epoch;
    doc["t"]  = roundf(r.temperature * 100) / 100.0f;
    doc["h"]  = roundf(r.humidity    * 100) / 100.0f;
    doc["p"]  = roundf(r.pressure    * 100) / 100.0f;
    doc["c"]  = roundf(r.mq135 * 100) / 100.0f;
    doc["s"]  = roundf(r.mq136 * 100) / 100.0f;
    doc["n"]  = roundf(r.mq137 * 100) / 100.0f;
    doc["l"]  = QUALITY_NAMES[r.quality];
    doc["b"]  = r.bmeOk;
    if (r.bootId != bootId) doc["r"] = 1;   // survived a reboot; age is unusable
    serializeJson(doc, out, outSize);
}

// Send the oldest unacked reading. It stays queued until the Pi ACKs it, so
// this is a retransmit loop, not a fire-and-forget send.
void pumpQueue() {
    if (!piConnected || !piSubscribed || queueCount == 0) return;

    unsigned long now = millis();
    const Reading& oldest = queueBuf[queueHead];

    // Already in flight and still inside the ACK window — wait it out.
    bool inFlight = (oldest.seq > lastAckedSeq) && (lastSendMs != 0);
    unsigned long gap = inFlight ? ACK_TIMEOUT_MS : SEND_GAP_MS;
    if (lastSendMs != 0 && now - lastSendMs < gap) return;

    char payload[256];
    buildPayload(oldest, payload, sizeof(payload));
    size_t len = strlen(payload);

    bool sent = dataChar->notify((const uint8_t*)payload, len, connHandle);
    if (sent) {
        if (oldest.seq > lastSentSeq) lastSentSeq = oldest.seq;
        Serial.printf("[TX] %s seq %lu (%u bytes, %u queued)\n",
                      inFlight ? "re-sent" : "sent",
                      (unsigned long)oldest.seq, (unsigned)len, queueCount);
        if (inFlight) resendCount++;
        lastSendMs = now;
    } else {
        // Notify failed (buffers full / link busy) — retry on the next pass.
        Serial.printf("[TX] notify failed for seq %lu (%u bytes)\n",
                      (unsigned long)oldest.seq, (unsigned)len);
        lastSendMs = now - gap + SEND_GAP_MS;
    }
}

void updateStatus() {
    if (!statusChar) return;
    StaticJsonDocument<192> doc;
    doc["dev"]     = DEVICE_ID;
    doc["boot"]    = bootId;
    doc["queued"]  = queueCount;
    doc["acked"]   = lastAckedSeq;
    doc["sent"]    = deliveredCount;
    doc["resent"]  = resendCount;
    doc["dropped"] = droppedCount;
    doc["clock"]   = clockValid ? 1 : 0;
    doc["bme"]     = bmeReady ? 1 : 0;
    doc["up"]      = (uint32_t)(millis() / 1000);
    char buf[192];
    serializeJson(doc, buf, sizeof(buf));
    statusChar->setValue((uint8_t*)buf, strlen(buf));
}

// ═══════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println(F("\n=== Meat Quality Sensor Node — BLE-only ==="));

    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    Wire.begin(I2C_SDA, I2C_SCL);
    initBME280();

    // ── Restore state across the reboot ──
    prefs.begin("meatnode", false);
    bootId = prefs.getUInt("boot_id", 0) + 1;
    prefs.putUInt("boot_id", bootId);

    seqHighWater = prefs.getUInt("seq_hwm", 0);
    nextSeq = seqHighWater > 0 ? seqHighWater : 1;   // burn the rest of the old block
    reserveSeqBlock();
    restoreQueue();

    Serial.printf("[BOOT] boot #%lu, seq starts at %lu, %u reading(s) recovered\n",
                  (unsigned long)bootId, (unsigned long)nextSeq, queueCount);
    Serial.printf("[BOOT] queue capacity %u readings (%u min), free heap %lu bytes\n",
                  QUEUE_CAPACITY,
                  (unsigned)((uint32_t)QUEUE_CAPACITY * READ_INTERVAL_MS / 60000),
                  (unsigned long)ESP.getFreeHeap());

    // ── BLE peripheral ──
    NimBLEDevice::init(DEVICE_NAME);
    NimBLEDevice::setPower(9);  // +9 dBm
    NimBLEDevice::setMTU(247);     // one notification per reading, no fragmenting

    bleServer = NimBLEDevice::createServer();
    bleServer->setCallbacks(new ServerCallbacks());
    bleServer->advertiseOnDisconnect(true);

    NimBLEService* svc = bleServer->createService(SVC_UUID);

    dataChar = svc->createCharacteristic(CH_DATA_UUID, NIMBLE_PROPERTY::NOTIFY);
    dataChar->setCallbacks(new DataCallbacks());

    NimBLECharacteristic* ackChar = svc->createCharacteristic(
        CH_ACK_UUID, NIMBLE_PROPERTY::WRITE);
    ackChar->setCallbacks(new AckCallbacks());

    NimBLECharacteristic* timeChar = svc->createCharacteristic(
        CH_TIME_UUID, NIMBLE_PROPERTY::WRITE);
    timeChar->setCallbacks(new TimeCallbacks());

    statusChar = svc->createCharacteristic(CH_STAT_UUID, NIMBLE_PROPERTY::READ);

    svc->start();
    updateStatus();

    NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
    adv->addServiceUUID(SVC_UUID);
    adv->setName(DEVICE_NAME);
    adv->enableScanResponse(true);
    NimBLEDevice::startAdvertising();

    Serial.printf("[BLE] Advertising as '%s'\n", DEVICE_NAME);
}

// ═══════════════════════════════════════════════════════════════
// LOOP
// ═══════════════════════════════════════════════════════════════

void loop() {
    unsigned long now = millis();

    // ── Capture on schedule. Never gated on BLE state or on having a clock. ──
    if (now - lastReadMs >= READ_INTERVAL_MS) {
        lastReadMs = now;
        Reading r = captureReading();
        enqueue(r);

        Serial.printf("[READ] seq=%lu VOC=%.1f H2S=%.1f NH3=%.1f %.1fC %.1f%% -> %s "
                      "(queued %u, link %s)\n",
                      (unsigned long)r.seq, r.mq135, r.mq136, r.mq137,
                      r.temperature, r.humidity, QUALITY_NAMES[r.quality],
                      queueCount, piConnected ? "up" : "down");
        updateStatus();
    }

    // ── Drain the backlog, retransmitting anything still unacked. ──
    pumpQueue();

    // ── All flash writes happen here, never inside a BLE callback. ──
    if (persistRequested) {
        persistRequested = false;
        persistQueue(true);
    } else if (queueDirty && queueCount >= QUEUE_PERSIST_THRESHOLD) {
        persistQueue();
    }

    delay(10);
}
