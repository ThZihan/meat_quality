"""
BLE protocol shared between the ESP32 sensor node and the Raspberry Pi.

Transport
---------
The ESP32 is the GATT *peripheral*, the Pi is the *central*. The ESP has no
WiFi at all: BLE is its only link. Because the Pi may be busy, rebooting, or
out of range, the ESP treats every reading as un-delivered until the Pi
acknowledges it by sequence number.

Delivery guarantee
------------------
At-least-once on the wire, exactly-once in the database:

  1. ESP assigns each reading a monotonic uint32 ``seq`` (persisted in NVS).
  2. ESP notifies the oldest un-acked reading and keeps re-sending it.
  3. Pi commits the row to SQLite, and only THEN writes ``seq`` to the ACK
     characteristic. An ACK therefore never outruns durability.
  4. ESP drops every queued reading with ``seq <= acked``.

Duplicates from a retransmit collapse on ``sensor_readings.source_id``, which
carries a UNIQUE index and is written with INSERT OR IGNORE.

Timestamps (never blocks sending)
---------------------------------
There is no NTP on the ESP. Two independent mechanisms cover the clock, and
neither one gates the send path:

  * ``ep`` -- epoch seconds, non-zero only once the Pi has pushed the time via
    the TIME characteristic. The ESP stores an offset and keeps producing
    readings whether or not that ever happens.
  * ``ag`` -- age in milliseconds between capture and this transmission,
    derived from the ESP's monotonic uptime. Always valid.

The Pi prefers ``ep`` and falls back to ``pi_now - ag``. A reading captured
while the ESP had no clock still lands with an accurate timestamp.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# GATT UUIDs -- must stay byte-identical to the values in the ESP firmware
# (meat_quality_Air_data_ESP_Node/ESP_sensor_node/src/main.cpp)
# ---------------------------------------------------------------------------

SERVICE_UUID = "19859e41-e7f2-41cc-b771-2b33ce845fb2"

# ESP -> Pi. One sensor reading per notification, compact JSON (see below).
CHAR_DATA_UUID = "0a09c96d-05e0-495f-a8c4-2fb19c75a695"

# Pi -> ESP. uint32 little-endian: highest seq durably stored by the Pi.
CHAR_ACK_UUID = "8b4d8427-af8d-4979-b233-6e1d95eab4ea"

# Pi -> ESP. uint64 little-endian: current UTC epoch in milliseconds.
CHAR_TIME_UUID = "fc8acb7e-b802-4f11-8dce-58212ff25092"

# Pi <- ESP (read). JSON: queue depth, drop count, uptime, clock state.
CHAR_STATUS_UUID = "33db1a8b-1226-49cb-9dfb-2eeab1d3ef01"

# Advertised name. The Pi filters on the service UUID first and falls back to
# this, so a stray BLE device cannot be mistaken for the sensor node.
DEVICE_NAME = "MeatNode"

# ---------------------------------------------------------------------------
# Compact payload field names
#
# Kept to one or two characters so a full reading fits inside a single BLE
# notification (~244 usable bytes at the negotiated MTU) with no fragmentation.
# ---------------------------------------------------------------------------

F_SEQ = "q"          # uint32  sequence number
F_AGE_MS = "ag"      # uint32  capture-to-transmit age in ms
F_EPOCH = "ep"       # uint32  epoch seconds, 0 when the ESP has no clock
F_TEMPERATURE = "t"  # float   degrees C
F_HUMIDITY = "h"     # float   percent RH
F_PRESSURE = "p"     # float   hPa
F_MQ135 = "c"        # float   VOC / CO2 ppm
F_MQ136 = "s"        # float   H2S ppm
F_MQ137 = "n"        # float   NH3 ppm
F_QUALITY = "l"      # string  EXCELLENT|GOOD|MODERATE|POOR|CRITICAL
F_BME_OK = "b"       # int     1 when the BME280 answered, else 0
F_RESUMED = "r"      # int     1 when the reading survived an ESP reboot

# Quality levels the ESP firmware is allowed to emit. The server rejects
# anything outside this set with HTTP 400, which is why FAIR/SPOILED are gone.
VALID_QUALITY_LEVELS = ("EXCELLENT", "GOOD", "MODERATE", "POOR", "CRITICAL")


def make_source_id(device_id: str, seq: int) -> str:
    """Build the dedup key for a reading.

    ``seq`` is monotonic per ESP boot-lifetime and persisted in NVS, so
    ``device:seq`` is stable across retransmits -- which is exactly what the
    UNIQUE index on ``sensor_readings.source_id`` needs to collapse duplicates.
    """
    return f"{device_id}:{seq}"
