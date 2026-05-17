#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_AHTX0.h>

namespace {

constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t READ_INTERVAL_MS = 2000;
constexpr uint8_t AHT10_ADDRESS = 0x38;

Adafruit_AHTX0 aht;
bool sensorReady = false;
uint32_t lastReadMs = 0;

bool isDevicePresent(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

void scanI2CBus() {
  Serial.println("I2C scan started...");

  uint8_t foundDevices = 0;
  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("I2C device found at 0x");
      if (address < 16) {
        Serial.print('0');
      }
      Serial.println(address, HEX);
      foundDevices++;
    }
  }

  if (foundDevices == 0) {
    Serial.println("No I2C devices detected. Check VCC, GND, SDA, and SCL wiring.");
  } else {
    Serial.println("I2C scan finished.");
  }
}

void tryInitializeSensor() {
  Serial.println("Initializing AHT10/AHT20 sensor...");

  if (!isDevicePresent(AHT10_ADDRESS)) {
    Serial.println("AHT sensor was not found at I2C address 0x38.");
    sensorReady = false;
    return;
  }

  if (!aht.begin(&Wire)) {
    Serial.println("AHT sensor detected on I2C, but initialization failed.");
    sensorReady = false;
    return;
  }

  sensorReady = true;
  Serial.println("AHT sensor initialized successfully.");
}

void printSensorReading() {
  sensors_event_t humidity;
  sensors_event_t temperature;

  aht.getEvent(&humidity, &temperature);

  Serial.print("Temperature: ");
  Serial.print(temperature.temperature, 2);
  Serial.print(" °C | Humidity: ");
  Serial.print(humidity.relative_humidity, 2);
  Serial.println(" %RH");
}

}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1000);

  Serial.println();
  Serial.println("ESP32 AHT10 temperature/humidity test");
  Serial.println("Expected AHT I2C address: 0x38");
  Serial.println("Default ESP32 I2C pins: SDA=21, SCL=22");

  Wire.begin(SDA_PIN, SCL_PIN);
  scanI2CBus();
  tryInitializeSensor();
}

void loop() {
  if (!sensorReady) {
    Serial.println("Sensor not ready. Retrying initialization in 5 seconds...");
    delay(5000);
    tryInitializeSensor();
    return;
  }

  if (millis() - lastReadMs >= READ_INTERVAL_MS) {
    lastReadMs = millis();
    printSensorReading();
  }
}
