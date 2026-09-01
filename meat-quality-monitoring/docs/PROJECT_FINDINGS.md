# Project Findings and Engineering Insights

Raw, detailed record of everything learned building the IoT meat-freshness
monitoring system, intended as source material for later publication writing.
Not organised for reading flow — organised for completeness. Every number here
was measured on the actual hardware unless explicitly marked as an estimate or
a calculation.

Date of record: 2026-09-01. Repository: `github.com/ThZihan/meat_quality`.
Branches: `masterV3-cloud-prodfix` (WiFi/HTTP architecture, commit `8830c64`),
`masterV4-ble-pi-ingest` (BLE architecture, commit `3e7953d`).


## 1. Hardware inventory (exact)

**Edge node (sensor unit)**
- ESP32-WROOM-32 on a NodeMCU-32S board. PlatformIO board id `nodemcu-32s`.
- BLE MAC observed: `94:3C:C6:DA:E7:A2` (Espressif OUI 94:3C:C6).
- 4 MB SPI flash, 320 KB usable DRAM, dual-core Xtensa LX6 @ 240 MHz.
- USB-serial bridge: Silicon Labs CP210x, USB ID `10c4:ea60`.
- Bluetooth: BLE 4.2 (Bluedroid or NimBLE host; NimBLE used here).

**Gateway**
- Raspberry Pi 5 Model B Rev 1.0.
- Bluetooth controller `hci0`, BD address `2C:CF:67:08:94:62`, Bus: UART,
  ACL MTU 1021:8. Bluetooth 5.0 radio, shared 2.4 GHz front-end with WiFi.
- 29 GB SD card (`/dev/mmcblk0p2`), 28.7 GiB usable filesystem.
- Camera: Raspberry Pi Camera Module 3 (autofocus), driven via libcamera.

**Sensors**
- MQ-135 — VOC / CO2-equivalent, ADC1_CH6 on GPIO 34.
- MQ-136 — H2S, ADC1_CH7 on GPIO 35.
- MQ-137 — NH3, ADC1_CH4 on GPIO 32.
- BME280 — temperature / relative humidity / barometric pressure, I2C on
  SDA=GPIO 25, SCL=GPIO 26. Detected at address 0x76, chip ID 0x60.
  (Chip ID 0x58 would indicate BMP280 silicon: pressure/temperature only, no
  humidity. The firmware detects and reports this distinction explicitly,
  because the two parts are physically interchangeable on clone breakout
  boards and silently lack humidity.)

**Note on the BME280 readings in the current dataset:** measured ambient
temperature ranged 33.8–39.1 °C. This is *not* refrigerated storage; it is
open-bench ambient in a warm climate plus self-heating from the MQ sensor
heaters, which run continuously at ~150 mW each and sit physically close to
the BME280. For a spoilage study the BME280 must be thermally separated from
the MQ heater array or the temperature channel is measuring the enclosure, not
the sample. This is a genuine confound worth stating in a methods section.


## 2. Software stack (exact versions, for reproducibility)

**Gateway**
- Raspberry Pi OS / Debian GNU/Linux 13 (trixie), kernel
  `6.12.47+rpt-rpi-2712` aarch64.
- Python 3.13.5 (project venv).
- BlueZ 5.82 (`bluetoothd`), D-Bus GATT API.
- bleak 3.0.2, dbus-fast 5.0.22 (BLE client stack).
- streamlit 1.53.1, pandas 2.3.3, numpy 2.4.2, plotly 6.5.2,
  requests 2.32.5, Pillow 12.1.0.
- SQLite via Python stdlib `sqlite3`.

**Edge node**
- PlatformIO Core 6.1.19, platform `espressif32@6.7.0`, framework `arduino`.
- NimBLE-Arduino ^2.2.3 (2.x API — `NimBLEConnInfo`-based callbacks).
- ArduinoJson ^6.21.0.
- Adafruit BME280 ^2.2.4, Adafruit BusIO ^1.14.5.
- Stock ESP32 partition table (`default.csv`): nvs 0x5000 (20 KiB),
  otadata 0x2000, app0 0x140000 (1.25 MiB), app1 0x140000,
  spiffs 0x160000, coredump 0x10000.

**Final firmware footprint (BLE build):**
- RAM 94,604 / 327,680 bytes = 28.9 % static.
- Flash 626,941 / 1,310,720 bytes = 47.8 %.

For comparison, the WiFi/HTTP firmware on `masterV3` carried WiFi.h,
HTTPClient, WiFiClientSecure (TLS), WebServer, DNSServer and an EEPROM
credential store plus a ~460-line SoftAP configuration portal. Dropping all of
that and adding NimBLE was close to footprint-neutral in flash while freeing
the code budget for the persistent queue. NimBLE rather than the bundled
Bluedroid stack was a deliberate choice: Bluedroid is substantially larger in
both flash and RAM, and the RAM headroom is what the reading queue consumes.


## 3. Gas sensing subsystem — circuit and math

**Signal conditioning.** The MQ modules output 0–5 V on AOUT; the ESP32 ADC is
0–3.3 V. A resistive divider scales it:

- R_upper = 68 kΩ (AOUT → ADC node)
- R_lower = 100 kΩ (ADC node → GND)
- divider ratio = (68k + 100k) / 100k = 1.68
- 100 nF capacitor at the ADC node for stabilisation

The divider is *not* electrically free: it loads the module's own load
resistor. The firmware accounts for this with an effective load resistance,
which matters for any RS computation and is a detail commonly omitted:

```
R_L(module)   = 10 kΩ
R_divider     = 68k + 100k = 168 kΩ
R_L(effective)= (10k × 168k) / (10k + 168k) = 9.438 kΩ
```

Using the nominal 10 kΩ instead of 9.438 kΩ introduces a ~6 % systematic error
in RS, which propagates through the power law below with exponent ~1/b
(b ≈ −2.5 to −2.9), i.e. roughly 2–2.4 % in ppm. Small, but it is a
reproducible bias, not noise.

**ADC sampling.** The 68k/100k divider presents a high source impedance to the
ESP32 SAR ADC, which is known for mux and sample-and-hold artefacts. Mitigation
implemented:
- one throwaway conversion after channel switch (discards the S/H residue from
  the previously selected channel),
- 500 µs settle, then 32 averaged conversions at 250 µs spacing,
- 12-bit resolution (`ADC_RESOLUTION` 4095), 11 dB attenuation.

**Conversion to concentration.**

```
V_node = (adc / 4095) × 3.3 × 1.68
RS     = ((5.0 − V_node) / V_node) × R_L(effective)
ppm    = ((RS / R0) / a) ^ (1 / b)
```

**Calibrated clean-air R0 values (this specific unit):**
- MQ-135: R0 = 193,200.00 Ω
- MQ-136: R0 = 85,102.55 Ω
- MQ-137: R0 = 51,913.09 Ω

**Power-law coefficients (from datasheet curve fits):**
- MQ-135 VOC: a = 110.47, b = −2.862
- MQ-136 H2S: a = 44.947, b = −2.648
- MQ-137 NH3: a = 102.2,  b = −2.473

R0 is per-unit and drifts with sensor age and humidity; it must be
re-established after any hardware change. The firmware previously carried a
`sensor_status.mq_calibration = "required_after_hardware_change"` marker for
exactly this reason. **For publication this is the single weakest link in the
measurement chain** — MQ-series metal-oxide sensors are cross-sensitive
(MQ-135 responds to NH3, benzene, alcohol, smoke; MQ-136 responds to NH3 and
CO as well as H2S), and the firmware itself computes multiple candidate gases
from the same MQ-135 and MQ-136 elements using different (a, b) pairs. Any
claim that a channel measures a *specific* gas needs either a reference
instrument or a controlled gas exposure to defend.


## 4. Freshness classification thresholds

Two independent threshold sets exist in the system and they do not agree. This
is worth documenting because it is a real inconsistency in the codebase.

**Edge (firmware, 5 labels, emitted per reading):**

```
EXCELLENT : VOC < 600  AND H2S < 5   AND NH3 < 50
GOOD      : VOC < 800  AND H2S < 10  AND NH3 < 100
MODERATE  : VOC < 1000 AND H2S < 20  AND NH3 < 200
CRITICAL  : otherwise
```

`POOR` exists in the enum but is unreachable in the current logic — the
firmware falls straight from MODERATE to CRITICAL. Worth either fixing or
dropping before publishing the state machine.

**Gateway (config.py, per-channel bands used by the dashboard):**

```
H2S : fresh < 10,  warning 10–50,   critical > 50    ppm
NH3 : fresh < 25,  warning 25–100,  critical > 100   ppm
VOC : fresh < 600, warning 600–1000, critical > 1000 ppm
Temp: optimal 0–4 °C, warning > 10 °C, critical > 15 °C
RH  : optimal 60–80 %, warning < 50 % or > 90 %
```

The firmware's H2S "fresh" bound is 5 ppm; the gateway's is 10 ppm. The
firmware's NH3 fresh bound is 50 ppm; the gateway's is 25 ppm. These were
derived at different times from the reference paper
(`IoT_Based_Meat_Freshness_Classification_Using_Deep_Learning.pdf`) and never
reconciled. A five-level edge label is also mapped down to four dashboard
states via `QUALITY_LEVEL_MAP` (EXCELLENT/GOOD → SAFE, MODERATE → WARNING,
POOR → SPOILED, CRITICAL → CRITICAL), so the pipeline has a 5 → 4 lossy
projection in it.

**Server-side constraint discovered empirically:** the cloud API rejects
quality labels outside {EXCELLENT, GOOD, MODERATE, POOR, CRITICAL} with HTTP
400. An earlier firmware emitted FAIR and SPOILED and was silently failing to
upload. This is recorded in the code comments and is a good example of an
integration constraint that only surfaces in production.


## 5. Architecture V1 (WiFi/HTTP) and why it was replaced

**Topology.**

```
ESP32 --WiFi/HTTPS--> cloud API --HTTPS poll /history--> Raspberry Pi --> SQLite --> Streamlit dashboard
```

The ESP32 held WiFi credentials in EEPROM, exposed a SoftAP captive portal for
provisioning, obtained wall-clock time over NTP, and POSTed JSON directly to
`https://meat-monitor.kalobiral.com.bd/api/meat-data` with TLS. The Pi ran
`meat_monitor_client.py`, which polled the server's `/history` endpoint every
5 s, kept a bookmark file of the last seen reading id, and mirrored new rows
into a local SQLite database that the dashboard read.

**The structural defect.** The cloud server sat *upstream* of the Pi. The Pi
could not obtain data that the server had not received, even though the ESP32
and the Pi were on the same bench, metres apart. Server or internet outage =
no data reached the Pi at all.

**The buffer was inadequate to cover this.** The ESP32's offline queue was
`MAX_QUEUE = 20` entries in RAM, drained 3 per cycle. At a 3 s sampling
interval that is **60 seconds** of protection, and it was volatile — a reboot
lost it. Beyond 60 s the firmware shifted the ring and dropped the oldest
entry, incrementing a `queueDropCount` that nothing acted on.

**Additional coupling problems observed in V1:**
- Timestamps depended on NTP, which depended on WiFi. With no WiFi the
  firmware fell back to the literal string `1970-01-01T00:00:00Z`. Since the
  Pi's de-duplication and bookmarking keyed on timestamps, this was corrupting.
- Deduplication used a server-assigned `source_id`. The Pi could therefore only
  identify a reading *after* the server had accepted it.
- The server's numeric ids could reset on a database restore, which the client
  had to defend against with a 24-hour lookback window
  (`SENSOR_API_RECOVERY_LOOKBACK_HOURS`) — complexity caused purely by the
  server being the source of identity.

**Conclusion for a paper:** the failure was architectural, not implementational.
Placing the wide-area link between the sensor and the first durable store makes
system availability a function of WAN availability. This is a common and
under-discussed anti-pattern in IoT reference designs, which typically draw
"device → cloud → dashboard" without asking what holds the data when the middle
link is down.


## 6. Architecture V2 (BLE) — design

**Topology.**

```
ESP32 --BLE--> Raspberry Pi --> SQLite (durable) --> cloud API
                                     |
                                     +--> Streamlit dashboard (reads locally)
```

The Pi becomes the system of record; the server becomes a backup. The
separation distance is ~10 inches (25 cm), well inside BLE range, so the radio
link is not a limiting factor — measured RSSI −13 to −40 dBm, typically −31 to
−33 dBm.

**Design consequences of removing WiFi from the node entirely:**
1. No NTP. Solved by two independent mechanisms (§8) rather than by adding an
   RTC, which would have been the obvious hardware answer but adds a part, a
   battery, and a failure mode.
2. No server-assigned identity. The node assigns its own monotonic sequence
   numbers, so identity exists from the moment of capture.
3. No provisioning portal needed. ~460 lines of SoftAP/DNS/captive-portal code
   deleted, plus the EEPROM credential store.
4. The node's `wifi_rssi` field became meaningless; it now carries BLE link
   RSSI, keeping the dashboard's signal display working. Recorded in
   `sensor_status.link = "ble"` so the provenance is explicit in the data.


## 7. BLE protocol specification

**GATT profile.** Service UUID `19859e41-e7f2-41cc-b771-2b33ce845fb2`,
advertised under local name `MeatNode`. The Pi matches on service UUID first
and falls back to name, so a stray advertiser called "MeatNode" cannot be
mistaken for the sensor. An optional `BLE_DEVICE_ADDRESS` pins the MAC.

| Characteristic | UUID | Properties | Direction | Payload |
|---|---|---|---|---|
| DATA | `0a09c96d-05e0-495f-a8c4-2fb19c75a695` | NOTIFY | node → Pi | compact JSON, one reading |
| ACK | `8b4d8427-af8d-4979-b233-6e1d95eab4ea` | WRITE | Pi → node | uint32 LE, cumulative sequence |
| TIME | `fc8acb7e-b802-4f11-8dce-58212ff25092` | WRITE | Pi → node | uint64 LE, epoch milliseconds |
| STATUS | `33db1a8b-1226-49cb-9dfb-2eeab1d3ef01` | READ | Pi ← node | JSON diagnostics |

**Wire format.** Single-character keys so a full reading fits one ATT
notification without fragmentation:

```json
{"q":4000,"ag":188708,"ep":1788266426,"t":35.79,"h":68.36,"p":1002.29,
 "c":8.58,"s":4.25,"n":1.66,"l":"EXCELLENT","b":1}
```

- `q` uint32 sequence number
- `ag` uint32 age in ms between capture and *this* transmission
- `ep` uint32 epoch seconds, 0 when the node has no clock
- `t`/`h`/`p` temperature °C / relative humidity % / pressure hPa
- `c`/`s`/`n` MQ-135 VOC / MQ-136 H2S / MQ-137 NH3, ppm
- `l` quality label string
- `b` 1 if the BME280 answered, else 0
- `r` present and 1 if the reading survived a node reboot

Observed payload sizes 146–163 bytes. Negotiated ATT MTU 247, giving 244 usable
bytes, so every reading is a single notification.

**Node-side queue.**
- `QUEUE_CAPACITY` 1200 readings in RAM = 1 hour at 3 s (≈53 KB).
- `QUEUE_PERSIST_MAX` 128 readings checkpointed to NVS = 5,632 bytes.
- `QUEUE_PERSIST_THRESHOLD` 20 — checkpointing only begins once the backlog
  suggests a real outage.
- `QUEUE_PERSIST_MIN_GAP_MS` 60,000 — at most one flash write per minute.
- `ACK_TIMEOUT_MS` 4000, `SEND_GAP_MS` 60.
- `SEQ_BLOCK` 1000 — sequence numbers are reserved from NVS in blocks.


## 8. The delivery guarantee, stated precisely

**Claim:** at-least-once on the wire, exactly-once in the database.

**Mechanism.** The ordering is the entire guarantee:

1. Node assigns a monotonic uint32 sequence number, persisted in NVS.
2. Node notifies the *oldest un-acknowledged* reading and keeps re-sending it.
3. Pi writes the row to SQLite and commits.
4. Pi inserts the corresponding upload job into `pending_sync` and commits.
5. **Only then** does the Pi write the sequence number to the ACK
   characteristic.
6. Node drops every queued reading with `seq <= acked`.

Step 5 coming last is what makes an acknowledgement mean "durably on disk"
rather than "received". A crash at any point before step 5 causes a
retransmission, which the `UNIQUE` index on `sensor_readings.source_id`
absorbs via `INSERT OR IGNORE`. `source_id` is `"<device_id>:<seq>"`, stable
across retransmits by construction.

**The Pi withholds the ACK on:** undecodable payload, missing sequence number,
SQLite insert failure, and failure to enqueue the upload job. Each of these
leaves the reading in the node's queue for retransmission.

**Cumulative acknowledgement.** ACKs are TCP-style: writing sequence N clears
everything `<= N`. They are batched at `BLE_ACK_INTERVAL` (1 s) rather than
sent per reading. This was originally a per-reading ACK and was changed for
robustness reasons documented in §10 — a backlog drain now costs one GATT
write per second instead of one per reading.

**Sequence number sentinel collision (a real bug, worth reporting).** Sequence
numbers must start at 1, never 0, because 0 is also the initial value of
`lastAckedSeq`, and `ackUpTo()` begins `if (seq <= lastAckedSeq) return;`. A
reading numbered 0 can therefore never be acknowledged; it pins the head of the
queue and blocks every reading behind it indefinitely. This is only reachable
on freshly-erased NVS — that is, on *every new deployment* — which makes it a
particularly nasty class of bug: invisible in development on a device that has
been running a while, guaranteed on a factory-fresh unit. `restoreQueue()` also
now discards any seq-0 entry it finds, because the queue survives reflashes.


## 9. Timestamping without an RTC or NTP

The node has neither. Two mechanisms cover it, and critically **neither gates
the sampling or transmission path** — the node captures and transmits on
schedule whether or not it ever learns the time.

**Mechanism A — pushed clock (`ep`).** The Pi writes epoch milliseconds to the
TIME characteristic. The node stores an *offset* against `millis()` rather than
an absolute time, so the derived clock cannot drift away from the monotonic
ordering of readings. On receiving the clock the node also back-fills `ep` for
every reading already queued *from the current boot* (`resolveQueuedEpochs()`),
guarded by a boot id so that readings carried across a reboot are not given
timestamps derived from a previous boot's uptime.

**Mechanism B — age-since-capture (`ag`).** Every transmission carries the
elapsed milliseconds between capture and that transmission, from the monotonic
uptime counter. The Pi computes `timestamp = pi_now − ag`. This is recomputed
on every retransmission, so it stays correct no matter how long a reading sat
in the queue.

**Resolution policy on the Pi**, recorded per-row in
`sensor_status.time_source`:
- `esp_clock` — `ep` was non-zero, used directly.
- `pi_clock_minus_age` — no node clock, reconstructed as `pi_now − ag`.
- `arrival_after_reboot` — reading carried the `r` flag; its uptime is from a
  previous boot so `ag` is meaningless, and arrival time is used.

**Empirical distribution in the current dataset (3,172 rows):**
`esp_clock` 1,209 · `pi_clock_minus_age` 655 · `arrival_after_reboot` 5.

All three paths are exercised in real data, which is useful for a paper: the
provenance of every timestamp is recorded in the row itself rather than assumed.

**Validation of mechanism B.** Injected a synthetic reading with `ag = 30000`
and confirmed it was stored exactly 30 s before its arrival time
(arrival 09:45:57, stored 09:45:27). Mechanism B is therefore accurate to
within the Pi's own clock accuracy plus BLE transmission latency (tens of ms),
which is far below the 3 s sampling interval.

**Insight worth stating:** the pushed clock turned out to be *unnecessary* and
is now disabled by default (§10). The age-based reconstruction is sufficient
and strictly more robust, because it has no dependence on a successful GATT
write. A node with no RTC, no NTP and no clock at all still produces correctly
timestamped data as long as the gateway knows the time. This is a cheap and
generalisable technique for battery/cost-constrained sensor nodes.


## 10. Flash-wear analysis

Naively checkpointing the queue on every reading would be 1 write per 3 s =
28,800 writes/day. NVS wear-levels across its partition but the underlying
flash is rated on the order of 10^5 erase cycles per sector; at that rate a
20 KiB partition is being cycled hard enough to matter within months.

**Design adopted:**
- The queue lives in RAM. NVS is a crash-safety checkpoint, not the store.
- Checkpointing only starts once `queueCount >= 20` (≈1 minute of backlog,
  i.e. evidence the Pi is actually gone), rate-limited to one write per minute,
  plus one immediate checkpoint on unexpected disconnect.
- **During normal operation — Pi connected, backlog empty — the firmware
  performs zero flash writes.**
- Sequence numbers are handed out from pre-reserved blocks of 1000, costing one
  NVS write per ~50 minutes rather than one per reading. A reboot burns the
  remainder of the current block, so sequence numbers have gaps across reboots.
  This is harmless — the invariant needed is uniqueness and monotonicity, not
  contiguity — but it is worth noting explicitly because gaps in `source_id`
  look like data loss to an analyst and are not.


## 11. BlueZ ↔ NimBLE interoperability — the main empirical contribution

This is the most transferable result from the project. Bringing a
straightforwardly-specified GATT protocol up on real hardware took far longer
than writing it, and every obstacle presented identically at the symptom level:
"BLE is flaky, the link keeps dropping." The underlying causes were unrelated
to radio conditions — RSSI was −31 dBm throughout, at 25 cm separation.

Test platform for all of the below: Pi 5 / BlueZ 5.82 / bleak 3.0.2 /
dbus-fast 5.0.22 against ESP32-WROOM-32 / NimBLE-Arduino 2.2.x.

### 11.1 Notification delivery is robust; GATT writes are not

Measured behaviour, each row a controlled trial holding everything else fixed:

| Pattern | Result |
|---|---|
| Subscribe, never write | **Stable.** Held connection, streamed continuously |
| Write **with** response, after subscribing | **Stable** |
| Write **without** response (`response=False`) | `TimeoutError`, link dies |
| Write **before** `start_notify` | Notifications never delivered at all |
| One ACK write per reading (sustained) | `GATT Protocol Error: Unlikely Error` (ATT 0x0E), disconnect |
| Two concurrent writes on one connection | Link drops ≈2 s later |

Longest clean run with writes minimised: a single connection held for the full
80 s test window, 50+ notifications, `stored=51 duplicates=5`, zero
disconnects. Under a per-reading ACK regime the same hardware managed **one
reading per connection** before tearing down.

**Four design rules follow, all load-bearing in the final implementation:**

1. **Every write uses `response=True`.** Write-without-response routes through
   BlueZ's `AcquireWrite` file-descriptor path, which hangs against this
   peripheral and takes the link down with it. This is counter-intuitive:
   write-without-response is the "lighter" operation and the obvious choice for
   a high-rate ACK channel.
2. **Subscribe before writing anything.** Issuing a write before `StartNotify`
   leaves BlueZ silently never delivering notifications for the entire
   connection — the peripheral transmits (confirmed on its serial console) and
   the central's callback never fires. No error is raised anywhere.
3. **Acknowledge cumulatively and rate-limit.** One write per second clearing
   everything up to a sequence number, instead of one write per reading.
4. **Serialise all GATT writes behind a single lock.** Two writes racing on one
   connection dropped the link ≈2 s later.

Additionally: **never issue a GATT write from inside a notification callback.**
The callback runs on BlueZ's D-Bus dispatch path; writing from there deadlocks
it. The final implementation has the notification callback do nothing but
`queue.put_nowait(bytes(raw))`, with a separate worker task performing storage
and acknowledgement.

### 11.2 MTU reporting is misleading

`bleak`'s `client.mtu_size` reported **23** (the ATT default) while the
peripheral's `onMTUChange` callback reported a negotiated **247**, and BlueZ's
own D-Bus characteristic properties showed `MTU: 247`. bleak emits
`UserWarning: Using default MTU value. Call _acquire_mtu() ...` — the value is
"unqueried", not "negotiated to 23". Considerable time was spent designing
around a 20-byte payload limit that did not exist. Trust the peripheral's
negotiated value or BlueZ's `MTU` property, not the client library's default.

### 11.3 BlueZ caches the GATT database per device, and does not invalidate it

BlueZ stores a resolved copy of each peer's attribute table under
`/var/lib/bluetooth/<adapter>/cache/<device>`. **Any firmware change that
alters the characteristic layout invalidates this cache, and BlueZ does not
detect the change.** Stale handle mappings produced a *phantom acknowledgement*:
the peripheral logged `[ACK] seq<=1004 confirmed — 1 cleared` for a write the
gateway had never issued, silently discarding a queued reading.

This is a data-integrity failure caused entirely by host-side caching, and it
is invisible from the application. Mitigation now in the firmware: the ACK
handler rejects any write that is not exactly 4 bytes, and rejects any sequence
number above the highest actually transmitted (`lastSentSeq`) — a stale or
spurious write can no longer discard queued data. Operational mitigation after
any GATT profile change:

```
bluetoothctl remove <NODE_MAC>
sudo rm -rf /var/lib/bluetooth/<ADAPTER_MAC>/cache/<NODE_MAC>
sudo systemctl restart bluetooth
```

### 11.4 Disconnect reason codes (NimBLE encoding)

NimBLE reports `BLE_HS_ERR_HCI_BASE = 0x200` plus the HCI error:
- `0x208` → HCI 0x08 = supervision timeout (link genuinely lost)
- `0x213` → HCI 0x13 = remote user terminated (the *gateway* ended it)

Distinguishing these was essential: 0x213 pointed at the Pi/BlueZ side and
redirected the investigation away from radio conditions, which is where a
"flaky BLE" symptom naturally sends you first.

### 11.5 Residual behaviour, stated honestly

Under sustained load the link still re-establishes roughly every 30 s. This
costs a few seconds of latency and produces occasional duplicates, both absorbed
by the protocol: nothing leaves the node's queue until acknowledged, and
duplicates collapse on `UNIQUE(source_id)`. Measured throughput comfortably
exceeds the 3 s production rate — 79 readings ingested in a 180 s window while
the node generated 60 — so backlogs drain rather than grow. The root cause of
the residual churn was not isolated and remains an open question (§16).


## 12. Non-BLE environmental obstacles

### 12.1 ModemManager corrupts ESP32 serial diagnostics

ModemManager probes newly-appearing serial devices with AT commands and toggles
DTR/RTS. On an ESP32 that asserts the auto-reset circuit. Symptoms: apparently
impossible serial data rates (measured 38–62 KB/s on a 115200 baud line whose
ceiling is 11.5 KB/s), truncated and interleaved log lines, boot banners never
appearing, and resets that made the device look like it was crash-looping.

This cost significant investigation time because it corrupted the *diagnostic
channel itself* — every attempt to observe the firmware produced misleading
evidence. Fix, shipped as `deploy/99-esp32-ignore-modemmanager.rules`:

```
ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ENV{ID_MM_DEVICE_IGNORE}="1"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ENV{ID_MM_PORT_IGNORE}="1"
```

**Secondary lesson:** an unread serial port accumulates a large kernel TTY
buffer. Opening it later and reading immediately returns stale backlog, which
looks like a live flood. Any diagnostic reader must drain to quiescence before
treating what it sees as current. Several apparently-contradictory observations
during debugging were this artefact.

### 12.2 Bluetooth ships soft-blocked

On this image `rfkill` had Bluetooth soft-blocked at boot; `hci0` showed DOWN
despite `bluetooth.service` being active. Required once:

```
sudo rfkill unblock bluetooth       # persisted by systemd-rfkill
sudo sed -i 's/^#AutoEnable=true/AutoEnable=true/' /etc/bluetooth/main.conf
```

The unblock persists via `/var/lib/systemd/rfkill/` (verified: saved state 0).

### 12.3 NVS partition sizing silently bounds the persistent queue

The stock ESP32 partition table allocates `nvs` 0x5000 = 20,480 bytes. The
originally-designed 720-reading checkpoint is 31,680 bytes — larger than the
partition. `Preferences::putBytes()` failed, **returned 0, and the code did not
check it**, while `q_len` was still written, so the recorded length promised
data the blob did not contain. `restoreQueue()` then found a size mismatch and
discarded everything. Eventually the node wedged completely — no serial output
at all, not even the 3 s sampling line.

Attempted fix: custom partition table with 64 KiB NVS, no OTA slots, 3 MiB app.
**This made it worse** — the application reset before producing any output,
`rst:0x3 (SW_RESET)` in a tight loop at ~36 resets/second. The custom table was
not pursued further; the supported configuration is the stock table with a
bounded checkpoint.

Final design: `QUEUE_PERSIST_MAX = 128` readings = 5,632 bytes, comfortably
inside the stock partition, with the return value of `putBytes` checked and
`q_len` zeroed on failure so a partial write can never masquerade as a good
checkpoint.

**Generalisable lesson:** on ESP32, the persistent-storage budget is a
partition-table constant that most projects never revisit, and the failure mode
of exceeding it is silent rather than exceptional.

### 12.4 Flash writes must not happen inside BLE callbacks

NVS writes disable the flash cache for tens of milliseconds. Performing one
inside the NimBLE disconnect callback stalls the host task. Restructured so
`loop()` owns every flash write; callbacks set a flag.


## 13. Defects found during hardware bring-up

Recorded because the *class* of each is more interesting than the instance.
Every one of these was invisible in code review and only appeared on hardware.

1. **Sequence-number sentinel collision** (§8). Class: a sentinel value
   colliding with a legitimate value in the same domain. Only reachable on a
   factory-fresh device.
2. **Silent NVS overflow** (§12.3). Class: unchecked return value on a resource
   whose limit is defined outside the source file.
3. **GATT write instability** (§11.1). Class: protocol-level assumption
   (writes are cheap and safe) invalidated by a specific stack pairing.
4. **Flash write inside a radio callback** (§12.4). Class: blocking operation
   in a latency-sensitive callback context.
5. **ACK did not clear the in-flight marker.** After an ACK cleared the queue
   head, the *new* head was judged "in flight" against the previous send's
   timestamp, so it waited the full 4 s ACK timeout. A backlog therefore
   drained at one reading per four seconds instead of ~16 per second. Class:
   stale state after a state transition. Symptom looked like poor throughput,
   not a bug.
6. **`pending_sync` table never created by the schema initialiser.** It existed
   in the live database only as a leftover from an older schema. On a fresh
   install, `enqueue_pending_sync` would fail and readings would be stored
   locally but never uploaded. Class: schema drift between a long-lived
   deployment and a clean install — the deployed system worked, a new one would
   not.
7. **Transient upload failures permanently parked rows.** A network error
   counted against `CLOUD_UPLOAD_MAX_ATTEMPTS = 20`; after ~5 minutes of
   downtime rows were marked `failed`, and the fetch query only ever selected
   `pending`. Nothing retried a parked row. Class: conflating "retryable" with
   "failed", plus a terminal state with no exit.
8. **`enqueue_pending_sync` swallowed its own failure and returned 0.** A
   reading could land in `sensor_readings`, fail to be queued for upload, and
   still be acknowledged — so the node discarded its only other copy of a
   reading the server would never see. Class: error suppression at a durability
   boundary.
9. **Storage guard would not delete un-uploaded images**, so a long uplink
   outage would fill the card, stall SQLite, stop acknowledgements, and
   overflow the node's buffer — losing gas readings in order to preserve
   photographs. Class: a local invariant ("never delete unsent data") producing
   a globally worse outcome.

Numbers 6–9 were found by working through "what happens if X fails" as an
explicit exercise rather than by testing, which is itself a finding: **the
durability bugs were not reachable by normal testing, only by adversarial
reasoning about the failure envelope.**


## 14. Storage economics — measured

This turned out to be one of the more useful quantitative results, because it
inverts an intuition: the "small" data stream is negligible and the "supporting"
data stream dominates completely.

**Method.** Marginal cost measured by inserting 3,000 synthetic readings into a
fresh SQLite database (reading row + queued upload payload + indexes) and
dividing by count. Measuring against the live database would have been wrong —
it carries free pages from earlier deletions and reports ~11,876 B/reading,
a 17× overestimate.

**Results.**

| Stream | Unit cost | Per hour | Per day | Per 72 h |
|---|---|---|---|---|
| Sensor readings (3 s interval) | 676 B | 792 KiB | 19 MiB | **56 MiB** |
| Camera images (30 s interval) | 1.22 MiB | 146 MiB | 3.4 GiB | **10.3 GiB** |

**One image costs the same disk as ≈1,900 sensor readings** — roughly 95
minutes of gas sensing. The image stream is 189× the sensor stream over 72
hours.

Consequences:
- Sensor data alone would run for **years** on a 29 GB card. It is never the
  storage constraint and does not need aggressive retention policy.
- With the image uplink working, images upload and archived copies are
  reclaimed; the system runs indefinitely.
- With the image uplink down, images consume the free space above the 5 GiB
  floor in **≈41 hours** (5.8 GiB headroom ÷ 3.4 GiB/day).

**Design response — hard budget for storage isolation.** The two pipelines are
already independent in transport (§15). The SD card was their only shared
resource, so images now carry `IMAGE_BUDGET_BYTES` (4 GiB), enforced on every
storage-guard pass *independently of the free-space floor*. Images self-limit
long before the disk is threatened, so gas data always has room regardless of
how long the image uplink is down. Validated: with a 50 MiB test budget against
220 MiB of images, the guard reclaimed 171 MiB from the uploaded archive and
left every un-uploaded image untouched.

**Reclaim order** (`storage_manager.py`), safest first:
1. Uploaded images in the archive (server already holds them)
2. Rotated logs and old database backups (oversized live logs are *truncated*,
   not deleted, so services holding the file descriptor keep writing)
3. Synced `sensor_readings` rows, oldest first
4. Oldest un-uploaded images — last resort, `STORAGE_SACRIFICE_UNSENT_IMAGES`

**Invariant:** un-uploaded *sensor* data is never deleted. Row deletion is
bounded below by `get_unsynced_reading_floor()`, the lowest `sensor_readings.id`
still queued for upload, with a hard floor of 10,000 rows retained regardless.
If the space floor cannot be reached without touching un-uploaded sensor data,
the guard stops and logs an error rather than trading data for disk.

**Justification for stage 4** (deleting data the server has never seen — the
only such stage, and it needs defending): letting the card fill stops SQLite
writes, which stops acknowledgements, which overflows the node's 1-hour buffer
and loses gas readings — the primary measurement — in order to preserve
photographs. Sacrificing the oldest images is strictly the better outcome. It
is configurable off, in which case the guard fails loudly instead.

**`VACUUM` safety.** VACUUM rebuilds the database into a temporary copy and
briefly needs as much free space again as the file occupies. Running it while
nearly full is how a low-disk condition becomes a corrupt database. The guard
skips VACUUM when free space is under 1.2× the database size; deleted pages
remain available for reuse, so writes continue normally either way.

**Validation of the reclaim invariants.** Under simulated total disk exhaustion
(`free_bytes` stubbed to 0, forcing every stage), with 60 readings of which the
newest 15 were un-uploaded, 6 archived images and 3 pending images:

```
[PASS] uploaded images reclaimed            (6 → 0)
[PASS] NOT-yet-uploaded images untouched    (3 → 3)
[PASS] every unsynced reading survived      (15/15, ids 46–60)
[PASS] nothing at/above the unsynced floor deleted
[PASS] min-rows floor respected
[PASS] oldest deleted first                 (ids 1–45 removed)
```

The guard also correctly refused to continue and logged
`No further rows are safe to delete`, and correctly skipped VACUUM for lack of
space.


## 15. Pipeline independence

Gas data and image data share nothing in transport:

| | Gas data | Images |
|---|---|---|
| Producer | ESP32 over BLE → `ble_receiver.py` | `capture.py`, 30 s interval |
| Queue | `pending_sync` table (SQLite) | `sync_state.db` ledger |
| Uploader | `meat-monitor-cloud-uploader` (continuous) | `pi-image-sync.timer` (1 min) |
| Endpoint | `meat-monitor.kalobiral.com.bd/api/meat-data` | `iot-upload.kalobiral.com.bd/api/upload-image` |

Separate processes, queues, endpoints and retry logic. One being blocked,
throttled or offline has no effect on the other. The only coupling was the
shared SD card, addressed by the image budget in §14.

**Image retention change.** `sync.py` previously called `unlink()` on each
image after a successful upload. It now *moves* the file to `~/image_archive`,
so the Pi keeps its own copy until space actually runs short, and the storage
guard reclaims that archive oldest-first only under pressure. Name collisions
in the archive are resolved with a numeric suffix rather than overwriting.


## 16. Failure-mode analysis

| Failure | System behaviour | Data lost |
|---|---|---|
| Server / internet down | Readings keep arriving over BLE and are stored locally; `pending_sync` grows; uploader retries indefinitely and never parks a row for a network error | **None**, until disk fills |
| Server rejects payload (4xx) | Row parked as `failed` so it cannot block the queue; parked rows automatically returned to the queue every 30 min | **None** |
| Server rate-limits (429) | Treated as retryable; batch pauses, resumes next cycle; uploads throttled 0.4 s apart to avoid provoking it | **None** |
| BLE link drops | Node retains every un-acknowledged reading, replays on reconnect; duplicates collapse on `UNIQUE(source_id)` | **None** |
| Pi down / receiver stopped | Node buffers 1 hour in RAM, oldest 128 checkpointed to NVS | **None under 1 h**; oldest shed beyond |
| Pi power cut | Everything committed to SQLite survives; node holds unacknowledged readings and re-sends | **None** |
| ESP power cut | NVS checkpoint restores oldest 128 readings | Un-checkpointed remainder of RAM queue |
| SQLite write fails (disk full) | `insert_sensor_reading` raises → ACK withheld → node retains and re-sends; ingest stalls rather than silently dropping | **None** while node buffer holds |
| Both powered off | — | Everything during the outage; nothing was powered to record it |

**Verified rather than asserted:**

- *Outage recovery, gas pipeline.* Uploader stopped for 90 s while ingest
  continued, building a 34-reading backlog. On restart: 34 → 18 → 7 → **0
  within 45 s**, `parked=0`. Nothing lost, rate limit respected.
- *Retry persistence.* 25 consecutive drain cycles against a black-hole
  endpoint (`127.0.0.1:9`, connection refused): all 5 test rows remained
  `pending` with `retry_count=0`, nothing parked. Prior to the fix they would
  have been parked as `failed` after 20 cycles and never retried.
- *Disk-full ACK withholding.* By code path — `insert_sensor_reading` raises,
  the exception propagates out of `handle()`, the ACK is withheld. Not
  exercised against a genuinely full disk.


## 17. Quantitative results and dataset characteristics

**Operational totals at time of record:**
- 3,172 total readings in the gateway database; **1,869 ingested over BLE**
  (remainder from the earlier WiFi/HTTP polling path).
- 1,877 readings uploaded to the server; 0 pending, 0 parked at steady state.
- 2,286 images uploaded; 2 pending.
- Image ledger spans 2026-06-14 to 2026-09-01.

**Throughput.** In a 180 s window the gateway ingested 79 readings while the
node generated 60 — i.e. it drained backlog concurrently with live capture.
Under systemd over a 90 s window: readings 1,535 → 1,617 (+82), server-synced
144 → 254 (+110), pending falling 88 → 60. The uploader outpaces ingest.

**Deduplication in practice.** `stored=51 duplicates=5` over one 80 s session —
duplicates arise from reconnection overlap and were absorbed silently by the
UNIQUE index, exactly as designed. This is direct evidence the exactly-once
property holds under real reconnection churn.

**Measured sensor ranges across the dataset:**
- Temperature 33.8–39.1 °C
- Relative humidity 53.9–79.5 %
- MQ-135 VOC 5.6–8.7 ppm
- MQ-136 H2S 2.9–4.4 ppm
- MQ-137 NH3 1.4–3.1 ppm

**Critical caveat for any publication use.** Quality label distribution is
**100 % EXCELLENT across all 3,172 readings**. There is no class variation
whatsoever. This dataset is a *systems validation* dataset — it demonstrates
that the pipeline transports, timestamps, deduplicates, stores and uploads
correctly — and it is **not** a spoilage dataset. It contains no meat, no
spoilage progression, and no ground-truth labels. Gas concentrations sit near
clean-air baseline throughout, which is consistent with sensors idling in
ambient laboratory air.

Nothing about classification accuracy, threshold validity, sensor
discrimination or freshness prediction can be claimed from this data. Those
claims require a separate experiment with actual samples, controlled storage
temperature, a spoilage time course, and independent ground truth (microbial
plate counts, TVB-N, or trained sensory panel).

**BLE link quality.** RSSI −13 to −40 dBm, typically −31 to −33 dBm, at ~25 cm.
Negotiated ATT MTU 247. Payload 146–163 bytes, single notification each.


## 18. Deployment and operations

**systemd units (all enabled at boot; verified `enabled`/`active`):**

| Unit | Role |
|---|---|
| `meat-monitor-ble-receiver` | ESP32 → BLE → SQLite. The ingest path |
| `meat-monitor-cloud-uploader` | SQLite → server, drains `pending_sync` |
| `meat-monitor-storage-guard` | Enforces 5 GiB floor and 4 GiB image budget |
| `pi-image-capture` | Camera capture, 30 s interval |
| `pi-image-sync.timer` | Image upload, 1 min, `Persistent=true` |
| `meat-monitor-dashboard` | Streamlit, port 8502 |
| `meat-monitor-latest-view` | Latest-image view, port 8600 |
| `pi-camera-feed` | Live camera feed, port 5000 |

The BLE receiver depends on `bluetooth.service`, deliberately **not** on the
network — ingest must survive a total network outage. `Persistent=true` on the
image timer means missed runs are caught up after downtime.

`meat-monitor-client` (the old V1 poller) is disabled and now refuses to start
without `MEAT_MONITOR_ALLOW_POLLING=1`. Running it alongside the BLE receiver
would store every reading twice under two different `source_id` values — once
keyed `ESP32-MeatMonitor:<seq>` from BLE, once keyed by the server's own id
from the polling path — which the UNIQUE index cannot recognise as the same
measurement. This is a good example of a de-duplication scheme being valid only
within a single identity domain.

**Unattended display.** `deploy/meat-monitor-display.sh`, installed to
`~/.config/autostart/`, opens both pages at login with no manual step. It runs
via `lxsession-xdg-autostart`, which the labwc Wayland session starts (see
`/etc/xdg/labwc/autostart`). It waits for each server to answer before opening
the browser. Two implementation notes worth recording:
- Chromium exits immediately if it cannot find the compositor, so the script
  must export `XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY` and `DISPLAY` — an autostart
  context can inherit a minimal environment.
- A duplicate-launch guard using bare `pgrep -f <profile-path>` matches the
  shell running the script itself, because the path appears in its own command
  line. The guard must verify the matched process is actually Chromium by
  reading `/proc/<pid>/comm`. (The same self-matching trap bit `pkill` several
  times during debugging — worth a footnote in any methods section that
  describes shell-based process management.)

**Configuration surface** (all environment-overridable, `config.py`):
`BLE_DEVICE_NAME`, `BLE_DEVICE_ADDRESS`, `BLE_ACK_INTERVAL` (1.0 s),
`BLE_IDLE_TIMEOUT` (60 s), `BLE_PUSH_CLOCK` (default off),
`BLE_RECONNECT_MIN/MAX_DELAY` (2/30 s), `CLOUD_UPLOAD_INTERVAL` (15 s),
`CLOUD_UPLOAD_BATCH` (50), `CLOUD_UPLOAD_THROTTLE` (0.4 s),
`CLOUD_REQUEUE_INTERVAL` (1800 s), `STORAGE_MIN_FREE_BYTES` (5 GiB),
`STORAGE_TARGET_FREE_BYTES` (6 GiB), `STORAGE_DB_MIN_ROWS` (10,000),
`IMAGE_BUDGET_BYTES` (4 GiB), `STORAGE_SACRIFICE_UNSENT_IMAGES` (on).


## 19. Limitations and threats to validity

State these explicitly in any write-up.

1. **No spoilage data.** §17. The dataset validates the system, not the
   science. All labels are EXCELLENT; there is no class variation, no meat, and
   no ground truth.
2. **MQ sensor cross-sensitivity is unaddressed.** The same MQ-135 and MQ-136
   elements are used to compute multiple gas concentrations with different
   coefficient pairs. Without a reference instrument or controlled gas
   exposure, per-gas claims are not defensible.
3. **R0 calibration is single-point and drifts.** Established once in ambient
   air, per unit, with no humidity or temperature compensation. MQ sensors are
   strongly humidity-dependent; measured RH spanned 53.9–79.5 % in this dataset
   alone.
4. **BME280 thermally coupled to the MQ heaters.** Measured 33.8–39.1 °C is
   enclosure temperature, not sample temperature (§1).
5. **Threshold sets are inconsistent** between firmware and gateway, and
   `POOR` is unreachable (§4).
6. **Single node, single gateway, single site.** No replication, no
   multi-device concurrency testing. BLE was tested with one peripheral;
   `CONFIG_BT_NIMBLE_MAX_CONNECTIONS=1`.
7. **Short observation window.** Continuous operation measured in hours, not
   the 72 h target. The 72 h storage projections are calculated from measured
   per-unit costs, not observed.
8. **Residual BLE reconnection churn** (~30 s) is not root-caused (§11.5). It
   is not a data-loss path but it is an unexplained behaviour, which is a
   legitimate weakness to disclose.
9. **Disk-full behaviour verified by code path, not by filling a disk.**
10. **Power-cut recovery verified by configuration audit** (all units enabled,
    rfkill state persisted, `AutoEnable=true`), **not by an actual power cut.**
11. **BLE findings are specific to this stack pairing.** BlueZ 5.82 / bleak
    3.0.2 / NimBLE 2.2.x. They may not generalise to other central stacks
    (Android, iOS, Windows) or to Bluedroid on the peripheral side. Worth
    framing as "observed on this widely-used Linux stack" rather than as
    universal BLE behaviour.
12. **Single-server dependency.** The cloud endpoint is one host with no
    failover; "backed up" means one remote copy.


## 20. What is defensible to claim, and what is not

**Defensible from this work:**
- An architecture in which the gateway, not the cloud, is the point of
  durability, with a stated and mechanised delivery guarantee.
- A store-and-forward protocol over BLE GATT with cumulative acknowledgement,
  and the ordering argument that makes an ACK mean "durably stored".
- Timestamp reconstruction on a node with no RTC and no NTP, via
  age-since-capture, with per-row provenance recorded — and the empirical
  observation that the pushed-clock mechanism proved unnecessary.
- Flash-wear-aware persistence: zero flash writes in steady state.
- Measured storage economics showing a 189× asymmetry between image and sensor
  streams, and a budget-based isolation mechanism derived from it.
- The BlueZ/NimBLE interoperability findings (§11) with the measurement table.
  This is genuinely useful to other practitioners and is, in my judgement, the
  most publishable single contribution.
- A catalogue of durability defects reachable only by adversarial reasoning
  about the failure envelope, not by testing (§13).

**Not defensible without further work:**
- Any classification accuracy, sensitivity, specificity or ROC figure.
- Any claim that the thresholds correctly separate fresh from spoiled meat.
- Any claim about shelf-life prediction or correlation with microbial load.
- Any per-gas quantitative accuracy claim.
- Any claim of 72 h continuous validated operation (projected, not observed).
- Any general claim about "BLE reliability" beyond this stack pairing.


## 21. Open questions and future work

1. **Root-cause the ~30 s reconnection churn.** Candidate hypotheses not yet
   eliminated: connection-parameter negotiation, WiFi/BLE coexistence on the
   Pi 5's shared 2.4 GHz front-end (WiFi is active for the uplink), NimBLE
   host-task starvation during `analogRead` bursts (32 samples × 3 channels
   ≈ 26 ms per cycle), or BlueZ state degradation over many reconnect cycles.
   A `btmon` HCI capture correlated against the node's serial log across a
   disconnect would settle it.
2. **Test whether the GATT-write instability reproduces with Bluedroid** on the
   peripheral, and with other centrals. This determines whether §11 is a NimBLE
   issue, a BlueZ issue, or an interaction.
3. **Run the actual spoilage experiment.** Controlled temperature, real
   samples, time course, independent ground truth. Everything scientific
   depends on this.
4. **Humidity and temperature compensation for MQ readings**, and periodic
   R0 re-baselining.
5. **Thermally isolate the BME280** from the MQ heater array.
6. **Reconcile the two threshold sets** and either implement or remove `POOR`.
7. **Verify power-cut recovery with a real power cut**, and disk-full behaviour
   by actually filling a disk.
8. **Extend the node buffer.** 1,200 readings (1 h) is the current limit;
   2,400 overflowed DRAM by 22,832 bytes. A more compact on-node record (scaled
   16-bit integers instead of floats — ~26 B/reading versus 44 B) would roughly
   double capacity within the same RAM.
9. **Multi-node scaling.** Currently one peripheral, one connection. Several
   nodes per gateway changes the BLE scheduling picture substantially.
10. **Second backup destination**, so "backed up" is not one remote host.


## 22. Reproducibility checklist

- Repository `github.com/ThZihan/meat_quality`, branch
  `masterV4-ble-pi-ingest`, commit `3e7953d`. V1 architecture preserved intact
  at `masterV3-cloud-prodfix`, commit `8830c64`, for direct comparison.
- Change scope V1 → V2: 29 files, +2,861 / −991 lines. Firmware `main.cpp`
  went from ~1,525 lines (WiFi/HTTP/portal) to a BLE-only implementation.
- Exact versions in §2. GATT UUIDs in §7 — these must stay byte-identical
  between `ble_protocol.py` and the firmware `#define`s; the Python module
  carries a comment saying so.
- Host prerequisites: `rfkill unblock bluetooth`, `AutoEnable=true` in
  `/etc/bluetooth/main.conf`, the ModemManager udev rule (§12.1),
  `pip install bleak`.
- Sensor calibration constants in §3 are **per-unit** and must be
  re-established on different hardware.
- Additional detail in `docs/BLE_ARCHITECTURE.md` (architecture, field notes,
  failure-mode table, deployment and rollback procedure).

**A note on method, possibly worth a paragraph in a paper.** The largest single
time cost in this project was not design or implementation — it was that the
diagnostic channel itself was compromised (§12.1), so early evidence actively
misled. Several hours were spent pursuing a phantom "serial flood" and an
"impossible data rate" that were artefacts of ModemManager interference and
kernel TTY buffering. The general lesson: when a system misbehaves in ways that
seem physically impossible (a 115200 baud line delivering 62 KB/s), suspect the
instrument before the system.
