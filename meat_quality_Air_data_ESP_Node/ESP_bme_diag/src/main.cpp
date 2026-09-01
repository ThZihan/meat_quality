#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <esp_system.h>

constexpr int SDA_PIN = 25;
constexpr int SCL_PIN = 26;
constexpr uint8_t BME_ADDRESS_PRIMARY = 0x76;
constexpr uint8_t BME_ADDRESS_SECONDARY = 0x77;

Adafruit_BME280 bme;
bool bmeReady = false;
uint8_t activeAddress = 0;
unsigned long lastTestMs = 0;

const char* resetReasonName(esp_reset_reason_t reason) {
    switch (reason) {
        case ESP_RST_POWERON: return "POWERON";
        case ESP_RST_EXT: return "EXTERNAL";
        case ESP_RST_SW: return "SOFTWARE";
        case ESP_RST_PANIC: return "PANIC";
        case ESP_RST_INT_WDT: return "INT_WDT";
        case ESP_RST_TASK_WDT: return "TASK_WDT";
        case ESP_RST_WDT: return "OTHER_WDT";
        case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
        case ESP_RST_BROWNOUT: return "BROWNOUT";
        case ESP_RST_SDIO: return "SDIO";
        default: return "UNKNOWN";
    }
}

bool readRegister(uint8_t address, uint8_t reg, uint8_t& value) {
    Wire.beginTransmission(address);
    Wire.write(reg);
    uint8_t error = Wire.endTransmission(false);
    if (error != 0) return false;
    if (Wire.requestFrom(address, (uint8_t)1) != 1) return false;
    value = Wire.read();
    return true;
}

void printLineTest() {
    Wire.end();
    delay(10);

    pinMode(SDA_PIN, INPUT);
    pinMode(SCL_PIN, INPUT);
    delay(10);
    int floatingSda = digitalRead(SDA_PIN);
    int floatingScl = digitalRead(SCL_PIN);

    pinMode(SDA_PIN, INPUT_PULLDOWN);
    pinMode(SCL_PIN, INPUT_PULLDOWN);
    delay(10);
    int pulldownSda = digitalRead(SDA_PIN);
    int pulldownScl = digitalRead(SCL_PIN);

    pinMode(SDA_PIN, INPUT_PULLUP);
    pinMode(SCL_PIN, INPUT_PULLUP);
    delay(10);
    int pullupSda = digitalRead(SDA_PIN);
    int pullupScl = digitalRead(SCL_PIN);

    Serial.printf("[LINES] GPIO%d/SDA floating=%s pulldown=%s pullup=%s | ",
                  SDA_PIN,
                  floatingSda ? "HIGH" : "LOW",
                  pulldownSda ? "HIGH" : "LOW",
                  pullupSda ? "HIGH" : "LOW");
    Serial.printf("GPIO%d/SCL floating=%s pulldown=%s pullup=%s\n",
                  SCL_PIN,
                  floatingScl ? "HIGH" : "LOW",
                  pulldownScl ? "HIGH" : "LOW",
                  pullupScl ? "HIGH" : "LOW");

    if (!pullupSda || !pullupScl) {
        Serial.println(F("[LINES] FAIL: one or both pins are externally held LOW or damaged"));
    } else {
        Serial.println(F("[LINES] PASS: both pins can idle HIGH"));
    }

    Wire.begin(SDA_PIN, SCL_PIN, 100000);
    Wire.setTimeOut(25);
}

uint8_t probeAddress(uint8_t address) {
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();
    Serial.printf("[PROBE] 0x%02X -> %s (Wire error %u)\n",
                  address, error == 0 ? "ACK" : "NACK", error);
    return error;
}

void detectAndReadBME() {
    bmeReady = false;
    activeAddress = 0;

    uint8_t addresses[] = {BME_ADDRESS_PRIMARY, BME_ADDRESS_SECONDARY};
    for (uint8_t address : addresses) {
        if (probeAddress(address) != 0) continue;

        uint8_t chipId = 0;
        if (!readRegister(address, 0xD0, chipId)) {
            Serial.printf("[CHIP] 0x%02X ACKed but chip-ID read failed\n", address);
            continue;
        }

        Serial.printf("[CHIP] address=0x%02X chip_id=0x%02X\n", address, chipId);
        if (chipId != 0x60) {
            Serial.println(F("[CHIP] Not BME280 silicon (expected ID 0x60)"));
            continue;
        }

        if (!bme.begin(address, &Wire)) {
            Serial.println(F("[BME280] Chip found but Adafruit initialization failed"));
            continue;
        }

        bmeReady = true;
        activeAddress = address;
        Serial.printf("[BME280] READY at 0x%02X\n", activeAddress);
        break;
    }

    if (!bmeReady) {
        Serial.println(F("[BME280] NOT DETECTED"));
        return;
    }

    float temperature = bme.readTemperature();
    float humidity = bme.readHumidity();
    float pressure = bme.readPressure() / 100.0F;
    Serial.printf("[VALUES] temperature=%.2f C humidity=%.2f %% pressure=%.2f hPa\n",
                  temperature, humidity, pressure);
}

void runTest() {
    Serial.println(F("\n========== ISOLATED BME280 TEST =========="));
    printLineTest();
    detectAndReadBME();
    Serial.println(F("=========================================="));
}

void setup() {
    Serial.begin(115200);
    delay(1500);
    Serial.println(F("\nESP32 ISOLATED GPIO25/GPIO26 + BME280 DIAGNOSTIC"));
    Serial.printf("[BOOT] reset=%s (%d), cpu=%u MHz, heap=%u bytes\n",
                  resetReasonName(esp_reset_reason()),
                  (int)esp_reset_reason(),
                  getCpuFrequencyMhz(),
                  ESP.getFreeHeap());
    runTest();
    lastTestMs = millis();
}

void loop() {
    if (millis() - lastTestMs >= 3000) {
        lastTestMs = millis();
        runTest();
    }
}
