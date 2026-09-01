#include <Arduino.h>
#include <Wire.h>
#include <math.h>

namespace {

constexpr int I2C_SDA_PIN = 25;
constexpr int I2C_SCL_PIN = 26;
constexpr uint32_t I2C_FREQUENCY_HZ = 100000;
constexpr uint8_t AHT10_ADDRESS = 0x38;
constexpr uint8_t AHT10_ALTERNATE_ADDRESS = 0x39;

constexpr uint8_t AHT10_CMD_SOFT_RESET = 0xBA;
constexpr uint8_t AHT10_CMD_INITIALIZE[] = {0xE1, 0x08, 0x00};
constexpr uint8_t AHT10_CMD_MEASURE[] = {0xAC, 0x33, 0x00};
constexpr uint8_t AHT10_STATUS_BUSY = 0x80;
constexpr uint8_t AHT10_STATUS_CALIBRATED = 0x08;

constexpr uint8_t BOSCH_PRIMARY_ADDRESS = 0x76;
constexpr uint8_t BOSCH_ALTERNATE_ADDRESS = 0x77;
constexpr uint8_t BOSCH_LEGACY_CHIP_ID_REGISTER = 0xD0;
constexpr uint8_t BOSCH_BMP3XX_CHIP_ID_REGISTER = 0x00;

bool sensorReady = false;
uint32_t sampleNumber = 0;

const char* i2cErrorText(uint8_t error) {
    switch (error) {
        case 0: return "ACK";
        case 1: return "data too long";
        case 2: return "address NACK";
        case 3: return "data NACK";
        case 4: return "other error";
        case 5: return "timeout";
        default: return "unknown error";
    }
}

uint8_t probeAddress(uint8_t address) {
    Wire.beginTransmission(address);
    return Wire.endTransmission(true);
}

uint8_t scanBus() {
    uint8_t deviceCount = 0;
    Serial.println("\n[I2C SCAN] Scanning addresses 0x08 through 0x77...");

    for (uint8_t address = 0x08; address <= 0x77; ++address) {
        const uint8_t error = probeAddress(address);
        if (error == 0) {
            Serial.printf("  FOUND device at 0x%02X", address);
            if (address == AHT10_ADDRESS) {
                Serial.print("  <- expected AHT10 address");
            } else if (address == AHT10_ALTERNATE_ADDRESS) {
                Serial.print("  <- alternate AHT address");
            }
            Serial.println();
            ++deviceCount;
        } else if (error == 4 || error == 5) {
            Serial.printf("  Bus error at 0x%02X: %s (%u)\n",
                          address, i2cErrorText(error), error);
        }
        delay(2);
    }

    Serial.printf("[I2C SCAN] Complete: %u device(s) found.\n", deviceCount);
    return deviceCount;
}

bool readRegister(uint8_t address, uint8_t registerAddress, uint8_t& value) {
    Wire.beginTransmission(address);
    Wire.write(registerAddress);
    const uint8_t writeError = Wire.endTransmission(false);
    if (writeError != 0) {
        return false;
    }

    const size_t received = Wire.requestFrom(
        static_cast<uint16_t>(address), static_cast<size_t>(1), true);
    if (received != 1 || !Wire.available()) {
        return false;
    }

    value = Wire.read();
    return true;
}

const char* identifyBoschLegacyChip(uint8_t chipId) {
    switch (chipId) {
        case 0x55: return "BMP180/BMP085";
        case 0x56:
        case 0x57:
        case 0x58: return "BMP280";
        case 0x60: return "BME280";
        case 0x61: return "BME680/BME688";
        default: return "unknown/non-Bosch device";
    }
}

const char* identifyBoschBmp3xxChip(uint8_t chipId) {
    switch (chipId) {
        case 0x50: return "BMP388";
        case 0x60: return "BMP390";
        default: return "unknown/non-BMP3xx device";
    }
}

void identifyDeviceAtAddress(uint8_t address) {
    if (probeAddress(address) != 0) {
        return;
    }

    Serial.printf("\n[IDENTIFY] Testing device at 0x%02X...\n", address);

    uint8_t legacyChipId = 0;
    if (readRegister(address, BOSCH_LEGACY_CHIP_ID_REGISTER, legacyChipId)) {
        Serial.printf("[IDENTIFY] Register 0xD0 = 0x%02X -> %s\n",
                      legacyChipId, identifyBoschLegacyChip(legacyChipId));
    } else {
        Serial.println("[IDENTIFY] Could not read Bosch register 0xD0.");
    }

    uint8_t bmp3xxChipId = 0;
    if (readRegister(address, BOSCH_BMP3XX_CHIP_ID_REGISTER, bmp3xxChipId)) {
        Serial.printf("[IDENTIFY] Register 0x00 = 0x%02X -> %s\n",
                      bmp3xxChipId, identifyBoschBmp3xxChip(bmp3xxChipId));
    } else {
        Serial.println("[IDENTIFY] Could not read Bosch BMP3xx register 0x00.");
    }
}

bool writeBytes(const uint8_t* bytes, size_t length) {
    Wire.beginTransmission(AHT10_ADDRESS);
    Wire.write(bytes, length);
    const uint8_t error = Wire.endTransmission(true);
    if (error != 0) {
        Serial.printf("[AHT10] I2C write failed: %s (%u)\n",
                      i2cErrorText(error), error);
        return false;
    }
    return true;
}

bool readStatus(uint8_t& status) {
    const size_t received = Wire.requestFrom(
        static_cast<uint16_t>(AHT10_ADDRESS), static_cast<size_t>(1), true);
    if (received != 1 || !Wire.available()) {
        return false;
    }
    status = Wire.read();
    return true;
}

void printStatus(uint8_t status) {
    Serial.printf("0x%02X [busy=%s, calibrated=%s]",
                  status,
                  (status & AHT10_STATUS_BUSY) ? "yes" : "no",
                  (status & AHT10_STATUS_CALIBRATED) ? "yes" : "no");
}

bool initializeAHT10() {
    Serial.println("\n[AHT10] Probing expected address 0x38...");
    const uint8_t probeResult = probeAddress(AHT10_ADDRESS);
    if (probeResult != 0) {
        Serial.printf("[AHT10] FAIL: 0x38 did not acknowledge: %s (%u)\n",
                      i2cErrorText(probeResult), probeResult);

        const uint8_t alternateResult = probeAddress(AHT10_ALTERNATE_ADDRESS);
        if (alternateResult == 0) {
            Serial.println("[AHT10] NOTE: A device answered at alternate address 0x39.");
        }
        return false;
    }
    Serial.println("[AHT10] PASS: address 0x38 acknowledged.");

    Serial.println("[AHT10] Sending soft reset...");
    if (!writeBytes(&AHT10_CMD_SOFT_RESET, 1)) {
        return false;
    }
    delay(30);

    uint8_t status = 0;
    if (readStatus(status)) {
        Serial.print("[AHT10] Status after reset: ");
        printStatus(status);
        Serial.println();
    } else {
        Serial.println("[AHT10] FAIL: could not read status after reset.");
        return false;
    }

    if ((status & AHT10_STATUS_CALIBRATED) == 0) {
        Serial.println("[AHT10] Sensor is not calibrated; sending initialize command...");
        if (!writeBytes(AHT10_CMD_INITIALIZE, sizeof(AHT10_CMD_INITIALIZE))) {
            return false;
        }
        delay(20);
        if (!readStatus(status)) {
            Serial.println("[AHT10] FAIL: could not read status after initialization.");
            return false;
        }
        Serial.print("[AHT10] Status after initialization: ");
        printStatus(status);
        Serial.println();
    }

    if ((status & AHT10_STATUS_CALIBRATED) == 0) {
        Serial.println("[AHT10] WARNING: calibrated status bit is still clear.");
    }

    return true;
}

bool readAHT10(float& temperatureC, float& humidityPercent, uint8_t& status) {
    if (!writeBytes(AHT10_CMD_MEASURE, sizeof(AHT10_CMD_MEASURE))) {
        return false;
    }

    const uint32_t timeoutAt = millis() + 250;
    do {
        delay(10);
        if (!readStatus(status)) {
            return false;
        }
        if ((status & AHT10_STATUS_BUSY) == 0) {
            break;
        }
    } while (static_cast<int32_t>(timeoutAt - millis()) > 0);

    if (status & AHT10_STATUS_BUSY) {
        Serial.println("[AHT10] Measurement timed out while sensor remained busy.");
        return false;
    }

    uint8_t data[6] = {};
    const size_t received = Wire.requestFrom(
        static_cast<uint16_t>(AHT10_ADDRESS), sizeof(data), true);
    if (received != sizeof(data)) {
        Serial.printf("[AHT10] Expected 6 measurement bytes, received %u.\n",
                      static_cast<unsigned>(received));
        while (Wire.available()) {
            Wire.read();
        }
        return false;
    }

    for (size_t index = 0; index < sizeof(data); ++index) {
        data[index] = Wire.read();
    }
    status = data[0];

    const uint32_t rawHumidity =
        (static_cast<uint32_t>(data[1]) << 12) |
        (static_cast<uint32_t>(data[2]) << 4) |
        (static_cast<uint32_t>(data[3]) >> 4);
    const uint32_t rawTemperature =
        (static_cast<uint32_t>(data[3] & 0x0F) << 16) |
        (static_cast<uint32_t>(data[4]) << 8) |
        static_cast<uint32_t>(data[5]);

    humidityPercent = (static_cast<float>(rawHumidity) * 100.0f) / 1048576.0f;
    temperatureC = (static_cast<float>(rawTemperature) * 200.0f) / 1048576.0f - 50.0f;

    const bool plausible =
        isfinite(temperatureC) && isfinite(humidityPercent) &&
        temperatureC >= -40.0f && temperatureC <= 85.0f &&
        humidityPercent >= 0.0f && humidityPercent <= 100.0f;

    if (!plausible) {
        Serial.printf("[AHT10] Implausible decoded values: %.2f C, %.2f %%RH\n",
                      temperatureC, humidityPercent);
    }
    return plausible;
}

void printBusLevels() {
    Serial.printf("[I2C] Idle line levels: SDA=%s, SCL=%s\n",
                  digitalRead(I2C_SDA_PIN) ? "HIGH" : "LOW",
                  digitalRead(I2C_SCL_PIN) ? "HIGH" : "LOW");
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(1500);

    Serial.println("\n============================================================");
    Serial.println("ESP32 AHT10 I2C HARDWARE DIAGNOSTIC");
    Serial.println("============================================================");
    Serial.printf("Configured bus: SDA=GPIO%d, SCL=GPIO%d, frequency=%lu Hz\n",
                  I2C_SDA_PIN, I2C_SCL_PIN,
                  static_cast<unsigned long>(I2C_FREQUENCY_HZ));
    Serial.println("Expected AHT10 address: 0x38");

    const bool wireStarted = Wire.begin(
        I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQUENCY_HZ);
    Wire.setTimeOut(100);
    Serial.printf("[I2C] Controller initialization: %s\n",
                  wireStarted ? "PASS" : "FAIL");
    delay(100);
    printBusLevels();

    const uint8_t deviceCount = scanBus();
    if (deviceCount == 0) {
        Serial.println("[VERDICT] No I2C device detected. Check 3.3V, GND, SDA, and SCL wiring.");
    }

    identifyDeviceAtAddress(BOSCH_PRIMARY_ADDRESS);
    identifyDeviceAtAddress(BOSCH_ALTERNATE_ADDRESS);

    sensorReady = initializeAHT10();
    if (!sensorReady) {
        Serial.println("[VERDICT] AHT10 communication test FAILED.");
        Serial.println("The bus scan will repeat every 5 seconds for live wiring checks.");
    } else {
        Serial.println("[AHT10] Initialization complete; starting live measurements.");
    }
}

void loop() {
    if (!sensorReady) {
        delay(5000);
        printBusLevels();
        scanBus();
        sensorReady = initializeAHT10();
        return;
    }

    float temperatureC = NAN;
    float humidityPercent = NAN;
    uint8_t status = 0;
    ++sampleNumber;

    if (readAHT10(temperatureC, humidityPercent, status)) {
        Serial.printf("[SAMPLE %lu] PASS | Temperature: %.2f C | Humidity: %.2f %%RH | Status: ",
                      static_cast<unsigned long>(sampleNumber),
                      temperatureC, humidityPercent);
        printStatus(status);
        Serial.println();
    } else {
        Serial.printf("[SAMPLE %lu] FAIL: measurement read error.\n",
                      static_cast<unsigned long>(sampleNumber));
        sensorReady = false;
    }

    delay(2000);
}
