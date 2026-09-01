#!/usr/bin/env python3
"""
Cloud uploader — pushes locally-stored sensor readings to the server.

Second half of the reversed data flow. ble_receiver.py makes a reading durable
on the Pi and queues it in ``pending_sync``; this service drains that queue in
the background. The server is now a backup of the Pi rather than the other way
round, so an outage here costs latency and nothing else -- readings keep
arriving, keep being stored, and go out when the link returns.

Ordering is strictly oldest-first so the server's history fills in sequence,
and a row is only marked ``synced`` after the server confirms it. Rows that
fail repeatedly are parked as ``failed`` rather than retried forever; parked
rows keep both their payload and their ``sensor_readings`` row, so "failed"
means "stopped retrying", never "discarded".
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sqlite3
import sys
import time
from typing import Optional

import requests

import config
from db_manager import get_db_manager

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("cloud_uploader.log"), logging.StreamHandler()],
)
logger = logging.getLogger("cloud_uploader")

keep_running = True


def _signal_handler(signum, frame):
    global keep_running
    logger.info("Received signal %d, shutting down...", signum)
    keep_running = False


class CloudUploader:
    def __init__(self) -> None:
        self.db = get_db_manager()
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": config.SENSOR_API_KEY,
            "Content-Type": "application/json",
        })
        self.uploaded = 0
        self.failed = 0

    def _post(self, payload: dict) -> tuple[bool, bool]:
        """POST one reading.

        Returns (delivered, retryable). A 4xx other than 429 is the server
        telling us the payload itself is wrong -- retrying cannot fix that, so
        the row is parked immediately instead of blocking the queue behind it.
        """
        for attempt in range(1, config.CLOUD_UPLOAD_MAX_RETRIES + 1):
            try:
                resp = self.session.post(
                    config.SENSOR_API_BASE,
                    json=payload,
                    timeout=config.CLOUD_UPLOAD_TIMEOUT,
                )
            except requests.exceptions.RequestException as e:
                logger.warning("Upload attempt %d/%d failed: %s",
                               attempt, config.CLOUD_UPLOAD_MAX_RETRIES, e)
            else:
                if resp.status_code in (200, 201):
                    return True, False

                # Already on the server from an earlier partial run: the row is
                # delivered, not failed.
                if resp.status_code == 409:
                    logger.info("Server reports reading already present (409)")
                    return True, False

                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    logger.error("Server rejected payload with HTTP %d: %s",
                                 resp.status_code, resp.text[:200])
                    return False, False

                logger.warning("Upload attempt %d/%d got HTTP %d",
                               attempt, config.CLOUD_UPLOAD_MAX_RETRIES,
                               resp.status_code)

            if attempt < config.CLOUD_UPLOAD_MAX_RETRIES:
                time.sleep(config.SENSOR_API_RETRY_BASE_DELAY * attempt)

        return False, True

    def drain(self) -> int:
        """Upload one batch. Returns how many rows were delivered."""
        rows = self.db.fetch_pending_sync(limit=config.CLOUD_UPLOAD_BATCH)
        if not rows:
            return 0

        logger.info("Draining %d queued reading(s)", len(rows))
        delivered = 0

        for row in rows:
            if not keep_running:
                break
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                logger.error("Row %s holds unparseable JSON; parking it", row["id"])
                self.db.mark_sync_failed(row["id"], max_attempts=0)
                continue

            ok, retryable = self._post(payload)
            if ok:
                self.db.mark_sync_uploaded(row["id"])
                self.uploaded += 1
                delivered += 1
                time.sleep(config.CLOUD_UPLOAD_THROTTLE)
            elif retryable:
                # The server is unreachable, not unhappy. Leave the row exactly
                # as it is -- still 'pending', retry_count untouched -- and stop
                # the batch. Counting attempts here used to park rows as
                # 'failed' after 20 cycles (~5 minutes of downtime), and nothing
                # ever retries a parked row: a long outage silently stranded the
                # backlog. An unreachable server must cost latency, never data.
                logger.warning("Server unreachable; pausing this batch (queue intact)")
                break
            else:
                self.db.mark_sync_failed(row["id"], max_attempts=0)
                self.failed += 1

        return delivered

    def requeue_parked(self) -> int:
        """Return parked rows to the queue for another attempt.

        Only rows the server actively rejected reach 'failed'. A rejection can
        still be transient from the client's point of view -- an expired key, a
        server-side schema fix, a bad deploy -- so nothing stays parked forever.
        Orphans parked by --park-orphans are deliberately left alone.
        """
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE pending_sync
                SET sync_status = 'pending', retry_count = 0
                WHERE sync_status = 'failed'
                """
            )
            conn.commit()
            return cursor.rowcount

    def run_forever(self) -> None:
        logger.info("Cloud uploader started -> %s", config.SENSOR_API_BASE)
        if not config.SENSOR_API_KEY:
            logger.warning("SENSOR_API_KEY is empty; the server will likely reject uploads")

        last_requeue = time.monotonic()

        while keep_running:
            try:
                self.drain()
            except Exception:
                logger.exception("Upload cycle failed")

            if time.monotonic() - last_requeue >= config.CLOUD_REQUEUE_INTERVAL:
                requeued = self.requeue_parked()
                if requeued:
                    logger.info("Returned %d parked row(s) to the queue", requeued)
                last_requeue = time.monotonic()

            stats = self.db.get_sync_queue_stats()
            if stats["pending"] == 0:
                # Caught up: sleep the full interval.
                slept = 0.0
                while keep_running and slept < config.CLOUD_UPLOAD_INTERVAL:
                    time.sleep(0.5)
                    slept += 0.5
            else:
                time.sleep(1.0)

        logger.info("Cloud uploader stopped — uploaded=%d failed=%d",
                    self.uploaded, self.failed)


def park_orphans(older_than_days: int) -> int:
    """Park queued rows whose sensor_readings row no longer exists.

    These are leftovers from an earlier design: the reading they referenced was
    pruned long ago, and the ESP32 posted that era's data to the server
    directly, so re-sending would only create duplicates there. Parking keeps
    payload_json intact -- nothing is deleted, it just stops being retried.
    """
    db = get_db_manager()
    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE pending_sync
            SET sync_status = 'stale_orphan'
            WHERE sync_status = 'pending'
              AND created_at < datetime('now', ?)
              AND local_reading_id NOT IN (SELECT id FROM sensor_readings)
            """,
            (f"-{older_than_days} days",),
        )
        conn.commit()
        return cursor.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload stored readings to the cloud")
    parser.add_argument("--once", action="store_true",
                        help="Drain a single batch and exit")
    parser.add_argument("--park-orphans", type=int, metavar="DAYS",
                        help="Park queued rows older than DAYS whose reading is gone")
    parser.add_argument("--status", action="store_true",
                        help="Print queue counts and exit")
    parser.add_argument("--requeue-parked", action="store_true",
                        help="Return every parked row to the queue and exit")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if args.status:
        print(json.dumps(get_db_manager().get_sync_queue_stats(), indent=2))
        return 0

    if args.requeue_parked:
        n = CloudUploader().requeue_parked()
        logger.info("Returned %d parked row(s) to the queue", n)
        return 0

    if args.park_orphans is not None:
        parked = park_orphans(args.park_orphans)
        logger.info("Parked %d orphaned queue row(s) older than %d days",
                    parked, args.park_orphans)
        return 0

    uploader = CloudUploader()
    if args.once:
        uploader.drain()
        return 0

    uploader.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
