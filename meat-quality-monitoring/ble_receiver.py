#!/usr/bin/env python3
"""
BLE ingest service — receives sensor readings from the ESP32 over BLE.

Replaces the old meat_monitor_client.py polling loop. The data flow used to be

    ESP32 -> cloud API -> Pi polls /history -> SQLite -> dashboard

which meant a server outage stopped data reaching the Pi at all, with only the
ESP's 60-second RAM queue standing in between. It is now

    ESP32 -> BLE -> Pi -> SQLite -> cloud_uploader.py -> cloud API

so the Pi holds the authoritative copy and the server is merely a backup.

Delivery guarantee
------------------
The ESP re-sends the oldest un-acknowledged reading until this service
acknowledges it by sequence number. The ordering below is the whole guarantee,
and it is deliberate:

    1. write the row to SQLite and commit
    2. queue it in pending_sync and commit
    3. only then write the ACK back to the ESP

An ACK therefore always means "durably on disk". Crash anywhere before step 3
and the ESP simply re-sends -- the UNIQUE index on source_id absorbs the
duplicate. Reverse steps 1 and 3 and a Pi crash would silently lose readings.

Clock
-----
The ESP has neither an RTC nor NTP. This service pushes wall-clock time on
every connect and periodically thereafter, but that is an optimization: each
reading also carries the age in ms since it was captured, so a reading taken
before the ESP ever learned the time still lands with an accurate timestamp.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import struct
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

import ble_protocol as proto
import config
from db_manager import get_db_manager

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("ble_receiver.log"), logging.StreamHandler()],
)
logger = logging.getLogger("ble_receiver")

keep_running = True


def _signal_handler(signum, frame):
    global keep_running
    logger.info("Received signal %d, shutting down...", signum)
    keep_running = False


class ReadingSink:
    """Turns a BLE notification into a durable row, then reports what to ACK."""

    def __init__(self) -> None:
        self.db = get_db_manager()
        self.device_id = config.BLE_DEVICE_ID
        self.link_rssi: Optional[int] = None
        self.stored = 0
        self.duplicates = 0
        self.last_seq: Optional[int] = None
        self.last_notification = time.monotonic()

    # -- timestamp reconstruction -------------------------------------

    def _resolve_timestamp(self, payload: dict) -> tuple[datetime, str]:
        """Work out when the reading was actually captured.

        Three cases, in descending order of confidence:

        * The ESP had the clock we pushed it -> use its epoch directly.
        * No clock, but the reading was captured this boot -> subtract the age
          the ESP reports from our own clock.
        * The reading survived an ESP reboot ('r' flag) -> its uptime is from a
          previous boot and the age is meaningless, so fall back to arrival
          time and say so.
        """
        now = datetime.now(timezone.utc)

        epoch = int(payload.get(proto.F_EPOCH, 0) or 0)
        if epoch > 0:
            return datetime.fromtimestamp(epoch, tz=timezone.utc), "esp_clock"

        if payload.get(proto.F_RESUMED):
            return now, "arrival_after_reboot"

        age_ms = int(payload.get(proto.F_AGE_MS, 0) or 0)
        return now - timedelta(milliseconds=age_ms), "pi_clock_minus_age"

    # -- persistence ---------------------------------------------------

    def _store(self, payload: dict) -> Optional[int]:
        """Insert the reading and queue it for upload. Returns the seq on success.

        Runs on a worker thread: sqlite3 calls are blocking and must not stall
        the BLE event loop while a backlog is draining.
        """
        seq = int(payload[proto.F_SEQ])
        timestamp, time_source = self._resolve_timestamp(payload)
        received_at = datetime.now(timezone.utc)
        source_id = proto.make_source_id(self.device_id, seq)

        quality = str(payload.get(proto.F_QUALITY, "UNKNOWN"))
        if quality not in proto.VALID_QUALITY_LEVELS:
            logger.warning("seq=%d carries unknown quality level %r", seq, quality)

        sensor_status = {
            "bme280": "ok" if payload.get(proto.F_BME_OK) else "not_detected",
            "link": "ble",
            "time_source": time_source,
            "pressure": payload.get(proto.F_PRESSURE),
        }

        row_id = self.db.insert_sensor_reading({
            "timestamp": timestamp,
            "received_at": received_at,
            "device_id": self.device_id,
            "source_id": source_id,
            "temperature": float(payload.get(proto.F_TEMPERATURE, 0.0)),
            "humidity": float(payload.get(proto.F_HUMIDITY, 0.0)),
            "mq135_co2": float(payload.get(proto.F_MQ135, 0.0)),
            "mq136_h2s": float(payload.get(proto.F_MQ136, 0.0)),
            "mq137_nh3": float(payload.get(proto.F_MQ137, 0.0)),
            "quality_level": quality,
            # The node has no WiFi any more; this column now carries BLE RSSI so
            # the dashboard's signal display keeps working.
            "wifi_rssi": self.link_rssi,
            "sensor_status": sensor_status,
        })

        if row_id == 0:
            # UNIQUE(source_id) rejected it: a retransmit of something we already
            # hold. Already durable, so it is safe to ACK.
            self.duplicates += 1
            logger.debug("seq=%d already stored (retransmit)", seq)
            return seq

        # Queue for the cloud in the SAME call, before the ACK goes out. A row
        # in sensor_readings but not in pending_sync would never be backed up.
        # This raises if it cannot be queued, which propagates out of handle()
        # and withholds the ACK, so the node keeps its copy and re-sends.
        sync_id = self.db.enqueue_pending_sync(row_id, self._api_payload(
            timestamp, quality, payload, sensor_status
        ))
        if not sync_id:
            raise RuntimeError(
                f"reading {row_id} stored but not queued for upload; refusing to ACK"
            )
        self.stored += 1
        return seq

    def _api_payload(self, timestamp, quality, payload, sensor_status) -> dict:
        """Build the server's expected body, matching the old ESP32 HTTP shape."""
        return {
            "device_id": self.device_id,
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sensors": {
                "temperature": float(payload.get(proto.F_TEMPERATURE, 0.0)),
                "humidity": float(payload.get(proto.F_HUMIDITY, 0.0)),
                "pressure": float(payload.get(proto.F_PRESSURE, 0.0)),
                "mq135_co2": float(payload.get(proto.F_MQ135, 0.0)),
                "mq136_h2s": float(payload.get(proto.F_MQ136, 0.0)),
                "mq137_nh3": float(payload.get(proto.F_MQ137, 0.0)),
            },
            "quality": {"level": quality},
            "wifi_rssi": self.link_rssi,
            "sensor_status": sensor_status,
        }

    async def handle(self, raw: bytes) -> Optional[int]:
        """Decode one notification. Returns the seq to ACK, or None to skip."""
        self.last_notification = time.monotonic()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            # Never ACK something we could not read -- the ESP will re-send it.
            logger.error("Undecodable notification (%d bytes): %s", len(raw), e)
            return None

        if proto.F_SEQ not in payload:
            logger.error("Notification without a sequence number: %r", payload)
            return None

        try:
            seq = await asyncio.to_thread(self._store, payload)
        except Exception:
            logger.exception("Failed to store seq=%s; withholding ACK",
                             payload.get(proto.F_SEQ))
            return None

        self.last_seq = seq
        return seq


async def _find_node() -> Optional[BLEDevice]:
    """Locate the sensor node, preferring an explicit MAC pin.

    Matching on the service UUID rather than the name alone means a random
    nearby advertiser called 'MeatNode' cannot be mistaken for the sensor.
    """
    if config.BLE_DEVICE_ADDRESS:
        logger.info("Scanning for pinned address %s", config.BLE_DEVICE_ADDRESS)
        return await BleakScanner.find_device_by_address(
            config.BLE_DEVICE_ADDRESS, timeout=config.BLE_SCAN_TIMEOUT
        )

    seen_rssi: dict[str, int] = {}

    def match(device: BLEDevice, adv: AdvertisementData) -> bool:
        uuids = {u.lower() for u in (adv.service_uuids or [])}
        if proto.SERVICE_UUID.lower() in uuids:
            seen_rssi[device.address] = adv.rssi
            return True
        if adv.local_name == config.BLE_DEVICE_NAME:
            seen_rssi[device.address] = adv.rssi
            return True
        return False

    device = await BleakScanner.find_device_by_filter(
        match, timeout=config.BLE_SCAN_TIMEOUT
    )
    if device is not None:
        _find_node.last_rssi = seen_rssi.get(device.address)
    return device


_find_node.last_rssi = None


async def _push_time(client: BleakClient, lock: asyncio.Lock) -> None:
    """Hand the ESP our wall clock. Failure here must never stop ingest.

    Takes the shared write lock: BlueZ does not tolerate two GATT writes racing
    on one connection. A clock push overlapping an ACK write drops the link
    about two seconds later, which looked exactly like a radio problem.
    """
    if not config.BLE_PUSH_CLOCK:
        logger.debug("Clock push disabled; timestamps come from age-since-capture")
        return
    epoch_ms = int(time.time() * 1000)
    try:
        async with lock:
        # response=True is required, not a preference. Write-without-response
        # goes through BlueZ's AcquireWrite file-descriptor path, which hangs
        # against this peripheral and takes the whole link down with it
        # (measured: no write = stable, write-with-response = stable,
        # write-without-response = TimeoutError and disconnect).
            await client.write_gatt_char(
                proto.CHAR_TIME_UUID, struct.pack("<Q", epoch_ms), response=True
            )
        logger.info("Pushed clock to node: %d ms", epoch_ms)
    except Exception as e:
        # The node keeps sending regardless; timestamps just fall back to
        # arrival-time-minus-age, which is accurate anyway.
        logger.warning("Could not push clock to node (ingest unaffected): %s", e)


async def _session(device: BLEDevice, sink: ReadingSink) -> None:
    """One connected session: subscribe, ACK everything, return on disconnect."""
    disconnected = asyncio.Event()
    established = False

    def on_disconnect(_client: BleakClient) -> None:
        # Bleak also fires this for connection attempts that never succeeded,
        # which would otherwise fill the log with noise during a retry storm.
        if established:
            logger.warning("Node disconnected")
        disconnected.set()

    async with BleakClient(
        device,
        disconnected_callback=on_disconnect,
        timeout=config.BLE_CONNECT_TIMEOUT,
    ) as client:
        established = True
        logger.info("Connected to %s", device.address)
        sink.link_rssi = _find_node.last_rssi

        # Notifications are handed to a worker rather than processed inline.
        # A GATT write issued from inside a notification callback deadlocks
        # BlueZ's D-Bus dispatch and takes the link down a couple of seconds
        # later, so the callback must do nothing but hand the bytes off.
        inbox: asyncio.Queue[bytes] = asyncio.Queue()
        write_lock = asyncio.Lock()   # serialises every GATT write on this link

        received = 0

        def on_data(_char: BleakGATTCharacteristic, raw: bytearray) -> None:
            nonlocal received
            received += 1
            if received <= 3 or received % 50 == 0:
                logger.info("Notification #%d (%d bytes)", received, len(raw))
            inbox.put_nowait(bytes(raw))

        # Cumulative acknowledgement, TCP-style. ackUpTo() on the node drops
        # every reading with seq <= the value written, so one ACK covers a whole
        # batch and there is no need to write once per reading. That matters:
        # GATT writes are the fragile part of this link (BlueZ answered a
        # per-reading ACK storm with "Unlikely Error" and dropped the
        # connection), so the fewer of them the better.
        durable_seq = 0     # highest seq committed to SQLite
        acked_seq = 0       # highest seq the node has been told about

        async def store_worker() -> None:
            nonlocal durable_seq
            while True:
                raw = await inbox.get()
                try:
                    seq = await sink.handle(raw)
                    if seq is not None and seq > durable_seq:
                        durable_seq = seq
                except Exception:
                    logger.exception("Failed to store a reading")
                finally:
                    inbox.task_done()

        async def ack_worker() -> None:
            nonlocal acked_seq
            while True:
                await asyncio.sleep(config.BLE_ACK_INTERVAL)
                if durable_seq <= acked_seq:
                    continue
                seq = durable_seq   # everything up to here is on disk
                try:
                    async with write_lock:
                        await client.write_gatt_char(
                            proto.CHAR_ACK_UUID, struct.pack("<I", seq), response=True
                        )
                    acked_seq = seq
                    logger.debug("Acknowledged through seq=%d", seq)
                except Exception as e:
                    # Without an ACK the node keeps the readings and re-sends
                    # them. They are already safe here, so this costs
                    # duplicates, never data.
                    logger.warning("ACK through seq=%d failed: %s", seq, e)

        worker = asyncio.gather(store_worker(), ack_worker())

        await client.start_notify(proto.CHAR_DATA_UUID, on_data)
        logger.info("Subscribed — receiving readings")

        # The clock push happens AFTER subscribing, deliberately. Writing to a
        # characteristic before StartNotify leaves BlueZ never delivering the
        # notifications at all -- the node transmits, the callback never fires,
        # and the link drops a couple of seconds later. Subscribing first also
        # means no reading sent during setup can be missed.
        await _push_time(client, write_lock)

        sink.last_notification = time.monotonic()
        last_time_sync = time.monotonic()
        last_report = time.monotonic()

        while keep_running and not disconnected.is_set():
            await asyncio.sleep(1.0)
            now = time.monotonic()

            # A link that stops delivering but never reports a disconnect is a
            # zombie; drop it so the reconnect loop can rebuild it.
            if now - sink.last_notification > config.BLE_IDLE_TIMEOUT:
                logger.error(
                    "No readings for %.0f s — dropping the link to force a reconnect",
                    now - sink.last_notification,
                )
                break

            if now - last_time_sync >= config.BLE_TIME_SYNC_INTERVAL:
                await _push_time(client, write_lock)
                last_time_sync = now

            if now - last_report >= 60:
                queue = sink.db.get_sync_queue_stats()
                logger.info(
                    "stored=%d duplicates=%d last_seq=%s | upload queue: "
                    "%d pending, %d synced, %d parked",
                    sink.stored, sink.duplicates, sink.last_seq,
                    queue["pending"], queue["synced"], queue["failed"],
                )
                last_report = now

        worker.cancel()
        try:
            # Collect the cancellation so it is not reported as an unretrieved
            # task exception on shutdown.
            await worker
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await client.stop_notify(proto.CHAR_DATA_UUID)
        except Exception:
            pass


async def main_loop() -> None:
    sink = ReadingSink()
    delay = config.BLE_RECONNECT_MIN_DELAY

    logger.info("BLE ingest starting — looking for %r (service %s)",
                config.BLE_DEVICE_NAME, proto.SERVICE_UUID)

    while keep_running:
        try:
            device = await _find_node()
            if device is None:
                logger.warning("Node not found; retrying in %.0f s", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, config.BLE_RECONNECT_MAX_DELAY)
                continue

            logger.info("Found node at %s (RSSI %s dBm)",
                        device.address, _find_node.last_rssi)
            await _session(device, sink)
            # A clean session means the radio path is good; reset the backoff so
            # a node reboot is picked up in seconds rather than half a minute.
            delay = config.BLE_RECONNECT_MIN_DELAY

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Session failed (%s); retrying in %.0f s", e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, config.BLE_RECONNECT_MAX_DELAY)

    logger.info("BLE ingest stopped — stored=%d duplicates=%d",
                sink.stored, sink.duplicates)


def main() -> int:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
