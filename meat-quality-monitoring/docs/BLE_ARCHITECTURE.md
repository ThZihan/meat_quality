# BLE Ingest Architecture (branch `masterV4-ble-pi-ingest`)

The ESP32 has no WiFi. It talks only to the Raspberry Pi sitting ~10 inches
away over BLE, and the Pi owns the uplink to the cloud.

The previous design is preserved unchanged on **`masterV3-cloud-prodfix`**
(commit `8830c64`) and is the rollback target.

## Why

Before, data flowed:

```
ESP32 --WiFi/HTTPS--> cloud API --poll /history--> Pi --> SQLite --> dashboard
```

The server sat *upstream* of the Pi. If it was unreachable, nothing reached the
Pi even though both devices were sitting on the same bench, and the only buffer
was the ESP's 20-slot RAM queue — **60 seconds**, lost on reboot.

Now:

```
ESP32 --BLE--> Pi --> SQLite (durable) --> cloud API
                        |
                        +--> dashboard reads locally
```

The Pi is the system of record. The server is a backup. An outage anywhere
upstream costs latency, not data.

## Delivery guarantee

At-least-once on the wire, exactly-once in the database.

| Step | Where | Detail |
|------|-------|--------|
| 1 | ESP | Assigns a monotonic `uint32` sequence number, persisted in NVS |
| 2 | ESP | Notifies the **oldest un-acked** reading and keeps re-sending it |
| 3 | Pi | Writes the row to SQLite and commits |
| 4 | Pi | Queues it in `pending_sync` and commits |
| 5 | Pi | **Only then** writes `seq` to the ACK characteristic |
| 6 | ESP | Drops every queued reading with `seq <= acked` |

Step 5 coming last is the entire guarantee. An ACK always means "durably on
disk", never "received". A crash anywhere before it just causes a retransmit,
and the `UNIQUE` index on `sensor_readings.source_id` (`device_id:seq`)
absorbs the duplicate via `INSERT OR IGNORE`.

The Pi withholds the ACK for anything it could not decode or store — undecodable
notification, missing sequence number, database error. The ESP re-sends.

## Timestamps without NTP

No WiFi means no NTP. Two independent mechanisms cover the clock, and **neither
gates the send path** — the ESP captures and transmits on schedule whether or
not it ever learns the time.

1. **`ep`** — epoch seconds, non-zero only after the Pi pushes the clock to the
   TIME characteristic (on every connect, then every 5 minutes). The ESP stores
   an *offset* against `millis()`, so it also back-fills timestamps on readings
   already queued this boot.
2. **`ag`** — age in ms between capture and *this* transmission, from the ESP's
   monotonic uptime. Always valid, and recomputed on every retransmit.

The Pi prefers `ep`, else uses `pi_now - ag`. The chosen path is recorded in
`sensor_status.time_source` as `esp_clock`, `pi_clock_minus_age`, or
`arrival_after_reboot`.

The third case: a reading that survived an ESP reboot carries the `r` flag. Its
uptime came from a previous boot, so the age is meaningless and arrival time is
used instead. Only readings queued across a power cut are affected.

## Flash wear

The ESP queue lives in **RAM** (720 readings ≈ 36 minutes) and is checkpointed
to NVS only when the backlog suggests the Pi is genuinely gone
(`QUEUE_PERSIST_THRESHOLD = 20` readings ≈ 1 minute), rate-limited to one write
per minute, plus one immediate checkpoint on unexpected disconnect.

**During normal operation the firmware performs zero flash writes.** Sequence
numbers are reserved in blocks of 1000, costing one write per ~50 minutes.

Writing every reading to NVS instead would be ~28,800 writes/day and would wear
the flash out.

## Storage guard

The Pi holds the only copy of a reading between capture and upload, so it must
never fill the card. `storage_manager.py` enforces a **5 GiB floor**, reclaiming
to 6 GiB so it is not re-triggered every cycle. Reclaim order:

1. **Uploaded images** in `~/image_archive`, oldest first
2. **Rotated logs and old DB backups** (oversized live logs are truncated, not
   deleted, so services holding the fd keep writing)
3. **Synced rows** in `sensor_readings`, oldest first

The invariant: **nothing that has not reached the server is ever deleted.**

* Images still in `~/pending_sync` are never candidates — only `~/image_archive`.
* Row deletion is bounded by `get_unsynced_reading_floor()`, the lowest
  `sensor_readings.id` still queued for upload. Nothing at or above it is touched.
* A hard floor of 10,000 rows survives regardless.
* If the floor cannot be reached without touching un-uploaded data, the guard
  **stops and logs an error** rather than trading data for disk.

`VACUUM` is skipped when free space is under 1.2× the database size — VACUUM
rebuilds into a temporary copy, and running it while nearly full is how a
low-disk situation becomes a corrupt-database one. Deleted pages stay available
for reuse, so writes continue normally either way.

## Images

`sync.py` used to `unlink()` each image on successful upload. It now **moves it
to `~/image_archive`**. The Pi keeps its own copy for as long as there is room,
and the storage guard reclaims that archive oldest-first only under pressure.

## Services

| Unit | Role |
|------|------|
| `meat-monitor-ble-receiver` | ESP32 → BLE → SQLite. **The ingest path** |
| `meat-monitor-cloud-uploader` | SQLite → server, drains `pending_sync` |
| `meat-monitor-storage-guard` | Enforces the 5 GiB floor |
| `pi-image-capture` / `pi-image-sync` | Camera capture and image upload |
| `meat-monitor-dashboard` / `pi-camera-feed` / `meat-monitor-latest-view` | Web UIs |

The BLE receiver depends on `bluetooth.service`, **not** on the network — ingest
must survive a total network outage.

`meat-monitor-client.service` (the old poller) is superseded. It now refuses to
start without `MEAT_MONITOR_ALLOW_POLLING=1`, because running it alongside the
BLE receiver stores every reading twice: once keyed `ESP32-MeatMonitor:<seq>`
and once keyed by the server's id, which the `source_id` index cannot recognise
as the same measurement.

## GATT profile

Service `19859e41-e7f2-41cc-b771-2b33ce845fb2`, advertised as `MeatNode`.

| Characteristic | UUID | Direction | Payload |
|---|---|---|---|
| DATA | `0a09c96d-…a695` | notify, ESP→Pi | compact JSON, one reading |
| ACK | `8b4d8427-…b4ea` | write, Pi→ESP | `uint32` LE, highest durable seq |
| TIME | `fc8acb7e-…5092` | write, Pi→ESP | `uint64` LE, epoch ms |
| STATUS | `33db1a8b-…ef01` | read, Pi←ESP | JSON diagnostics |

Payload keys are one or two characters so a full reading fits in a single
notification at the negotiated 247-byte MTU — no fragmentation, no reassembly.
The definitions live in `ble_protocol.py` and must stay byte-identical to the
`#define`s in the firmware.

## Operating

```bash
# Storage and queue summary
./venv/bin/python storage_manager.py --report

# What is waiting to go to the server
./venv/bin/python cloud_uploader.py --status

# Check the reclaim logic without deleting anything
./venv/bin/python storage_manager.py --dry-run

# Watch ingest live
journalctl -u meat-monitor-ble-receiver -f
```

Sequence-number gaps in `source_id` are normal: a reboot burns the remainder of
the current 1000-block. Gaps mean "the ESP restarted", not "readings were lost".

## Deploying

One-time host setup (Bluetooth ships soft-blocked on this image):

```bash
sudo rfkill unblock bluetooth          # persisted by systemd-rfkill
sudo sed -i 's/^#AutoEnable=true/AutoEnable=true/' /etc/bluetooth/main.conf
sudo systemctl restart bluetooth
hciconfig hci0                         # expect: UP RUNNING
```

Python dependency:

```bash
./venv/bin/pip install bleak
```

Firmware — the node must be flashed with the BLE build before the Pi has
anything to receive:

```bash
cd ../meat_quality_Air_data_ESP_Node/ESP_sensor_node
~/.platformio/penv/bin/pio run --target upload
~/.platformio/penv/bin/pio device monitor      # expect: [BLE] Advertising as 'MeatNode'
```

Services:

```bash
sudo cp deploy/meat-monitor-{ble-receiver,cloud-uploader,storage-guard}.service \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl disable --now meat-monitor-client     # superseded poller
sudo systemctl enable --now meat-monitor-ble-receiver \
                            meat-monitor-cloud-uploader \
                            meat-monitor-storage-guard
```

Optional but recommended once the node's MAC is known — pin it in `.env` so the
Pi can never attach to a look-alike advertiser:

```bash
BLE_DEVICE_ADDRESS=AA:BB:CC:DD:EE:FF
```

### Rolling back

```bash
git checkout masterV3-cloud-prodfix
cd ../meat_quality_Air_data_ESP_Node/ESP_sensor_node && \
  ~/.platformio/penv/bin/pio run --target upload      # reflash the WiFi firmware
sudo systemctl disable --now meat-monitor-ble-receiver \
                             meat-monitor-cloud-uploader
sudo systemctl enable --now meat-monitor-client
```

Both firmwares write to the same `sensor_readings` table with the same
`device_id`, so history stays continuous across a switch in either direction.

## Field notes — things that actually broke

Everything below was found by bringing this up on real hardware (Pi 5 + BlueZ
5.82 + bleak 3.0.2 + ESP32-WROOM-32 + NimBLE 2.x). They are recorded because
each one presents as "BLE is flaky" and none is obvious from the symptom.

### ModemManager corrupts the serial console

ModemManager probes any new serial device with AT commands and toggles
DTR/RTS, which resets the ESP32 and shredded every diagnostic capture. Fixed by
`/etc/udev/rules.d/99-esp32-ignore-modemmanager.rules`, which tags the CP210x
bridge with `ID_MM_DEVICE_IGNORE`. Without it, serial output is unusable.

### BlueZ caches the GATT database per device

BlueZ stores a resolved copy of the attribute table under
`/var/lib/bluetooth/<adapter>/cache/<device>`. **Any firmware change that alters
the characteristic layout invalidates it, and BlueZ does not notice.** Stale
handles produced a phantom ACK — a write the Pi never made, which discarded a
queued reading. After changing the GATT profile:

```bash
bluetoothctl remove <NODE_MAC>
sudo rm -rf /var/lib/bluetooth/<ADAPTER_MAC>/cache/<NODE_MAC>
sudo systemctl restart bluetooth
```

### GATT writes are the fragile half of this link

Notification delivery is solid; writes are not. Measured on this hardware:

| Pattern | Result |
|---|---|
| Subscribe, never write | Stable, streams continuously |
| Write **with** response, after subscribing | Stable |
| Write **without** response (`response=False`) | `TimeoutError`, link dies |
| Write **before** `start_notify` | Notifications never delivered at all |
| One ACK write per reading | `GATT Protocol Error: Unlikely Error`, disconnect |

That shaped three decisions in `ble_receiver.py`, all load-bearing:

1. **Every write uses `response=True`.** The write-without-response path goes
   through BlueZ's `AcquireWrite` file descriptor and hangs.
2. **Subscribe first, write second.** Writing before `StartNotify` silently
   kills notification delivery for the whole connection.
3. **ACKs are cumulative and rate-limited** (`BLE_ACK_INTERVAL`, 1 s). One write
   clears every reading up to that sequence number, so a backlog drain costs one
   write per second instead of one per reading.

Writes are also serialised behind a single `asyncio.Lock`: two concurrent GATT
writes on one connection drop the link about two seconds later.

`BLE_PUSH_CLOCK` defaults to **off** for the same reason — see config.py. It
costs nothing, because timestamps are reconstructed from age-since-capture.

### Sequence numbers must start at 1

Zero is the "nothing acknowledged yet" value of `lastAckedSeq`, and `ackUpTo()`
returns early on `seq <= lastAckedSeq`. A reading numbered 0 can therefore never
be acknowledged; it sits at the head of the queue and blocks everything behind
it forever. Only reachable on a freshly erased NVS, which is exactly what a new
deployment has. `restoreQueue()` also discards any seq-0 entry it finds.

### The NVS partition bounds the checkpoint

The stock partition table gives `nvs` 0x5000 (20 KiB). The full 720-reading
queue is 31 KiB, so `putBytes` failed silently, `q_len` promised data the blob
did not contain, and the node eventually wedged with no serial output at all.
`QUEUE_PERSIST_MAX` is now 128 readings (5,632 bytes) and the write result is
checked. A custom partition table with a larger NVS was tried and made the app
reset before producing any output (`rst:0x3 SW_RESET` in a tight loop), so the
stock table plus a bounded checkpoint is the supported configuration.

### Current behaviour

The link re-establishes every ~30 s under sustained load. That costs a few
seconds of latency and produces the occasional duplicate, both of which the
protocol absorbs: nothing leaves the node's queue until it is acknowledged, and
duplicates collapse on `UNIQUE(source_id)`. Measured throughput comfortably
exceeds the 3-second production rate, so the backlog drains rather than grows.
Reconnect churn is a known rough edge, not a data-loss path.
