#!/usr/bin/env python3
"""
Storage guard — keeps a floor of free disk space on the Pi.

The Pi now holds the only copy of a reading between capture and upload, so it
must never fill its card. This service enforces STORAGE_MIN_FREE_BYTES (5 GiB
by default) by reclaiming the OLDEST data first, on the principle that the
server holds the long-term archive and the Pi only needs the recent window.

Reclaim order, safest first:

    1. Uploaded images in the archive directory  (already on the server)
    2. Rotated logs and stale backups            (never data)
    3. Synced rows in sensor_readings            (already on the server)

The rule that makes this safe: **nothing that has not reached the server is
ever deleted.** Images still queued for upload and readings still sitting in
pending_sync are skipped no matter how tight space gets. If the floor cannot be
reached without touching un-uploaded data, the guard stops and says so loudly
rather than trading data for disk.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sqlite3
import signal
import sys
import time
from pathlib import Path
from typing import Iterator

import config
from db_manager import get_db_manager

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("storage_manager.log"), logging.StreamHandler()],
)
logger = logging.getLogger("storage_manager")

keep_running = True


def _signal_handler(signum, frame):
    global keep_running
    logger.info("Received signal %d, shutting down...", signum)
    keep_running = False


def free_bytes(path: str = "/") -> int:
    return shutil.disk_usage(path).free


def human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


# ---------------------------------------------------------------------------
# Stage 1 — uploaded image archive
# ---------------------------------------------------------------------------

def _oldest_first(directory: Path) -> Iterator[Path]:
    if not directory.is_dir():
        return iter(())
    files = [p for p in directory.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime)
    return iter(files)


def reclaim_archived_images(target: int) -> int:
    """Delete already-uploaded images, oldest first. Returns bytes reclaimed.

    Only touches IMAGE_ARCHIVE_DIR. Files still in PENDING_SYNC_DIR have not
    reached the server yet and are never candidates.
    """
    archive = Path(config.IMAGE_ARCHIVE_DIR)
    reclaimed = 0

    for path in _oldest_first(archive):
        if free_bytes() >= target:
            break
        try:
            size = path.stat().st_size
            path.unlink()
            reclaimed += size
            logger.info("Removed archived image %s (%s)", path.name, human(size))
        except OSError as e:
            logger.warning("Could not remove %s: %s", path, e)

    return reclaimed


# ---------------------------------------------------------------------------
# Stage 2 — logs and stale backups
# ---------------------------------------------------------------------------

def reclaim_logs(target: int) -> int:
    """Delete rotated logs and old DB backups. Never touches the live log."""
    reclaimed = 0
    here = Path(__file__).resolve().parent

    candidates: list[Path] = []
    candidates.extend(here.glob("*.log.*"))
    candidates.extend(here.glob("*.bak"))
    candidates.extend(Path(config.DB_BACKUP_DIR).glob("*.db")
                      if Path(config.DB_BACKUP_DIR).is_dir() else [])

    # Oversized live logs get truncated rather than deleted, so services holding
    # the file descriptor keep writing to a valid (now empty) file.
    for path in here.glob("*.log"):
        try:
            if path.stat().st_size > config.LOG_MAX_SIZE_MB * 1024 * 1024:
                size = path.stat().st_size
                with open(path, "w"):
                    pass
                reclaimed += size
                logger.info("Truncated oversized log %s (%s)", path.name, human(size))
        except OSError as e:
            logger.warning("Could not truncate %s: %s", path, e)

    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)
    for path in candidates:
        if free_bytes() >= target:
            break
        try:
            size = path.stat().st_size
            path.unlink()
            reclaimed += size
            logger.info("Removed %s (%s)", path.name, human(size))
        except OSError as e:
            logger.warning("Could not remove %s: %s", path, e)

    return reclaimed


# ---------------------------------------------------------------------------
# Stage 3 — synced database rows
# ---------------------------------------------------------------------------

def reclaim_database(target: int) -> int:
    """Delete the oldest readings that the server already holds.

    Two hard limits protect the data:
      * never at or above the lowest un-uploaded reading id, and
      * never below STORAGE_DB_MIN_ROWS rows in total.
    """
    db = get_db_manager()
    db_path = db.db_path
    start_size = Path(db_path).stat().st_size if Path(db_path).exists() else 0

    floor = db.get_unsynced_reading_floor()
    total = db.get_reading_count()

    if total <= config.STORAGE_DB_MIN_ROWS:
        logger.info("Database holds %d rows (floor is %d) — nothing to trim",
                    total, config.STORAGE_DB_MIN_ROWS)
        return 0

    deletable = total - config.STORAGE_DB_MIN_ROWS
    deleted_total = 0

    with sqlite3.connect(db_path) as conn:
        while free_bytes() < target and deleted_total < deletable and keep_running:
            batch = min(config.STORAGE_DB_PRUNE_BATCH, deletable - deleted_total)

            # Oldest-first, and strictly below anything still awaiting upload.
            if floor is not None:
                cursor = conn.execute(
                    """
                    DELETE FROM sensor_readings WHERE id IN (
                        SELECT id FROM sensor_readings
                        WHERE id < ? ORDER BY timestamp ASC LIMIT ?
                    )
                    """,
                    (floor, batch),
                )
            else:
                cursor = conn.execute(
                    """
                    DELETE FROM sensor_readings WHERE id IN (
                        SELECT id FROM sensor_readings ORDER BY timestamp ASC LIMIT ?
                    )
                    """,
                    (batch,),
                )

            if cursor.rowcount == 0:
                logger.warning(
                    "No further rows are safe to delete — everything remaining is "
                    "either un-uploaded or inside the %d-row floor",
                    config.STORAGE_DB_MIN_ROWS,
                )
                break

            deleted_total += cursor.rowcount
            conn.commit()
            logger.info("Deleted %d old reading(s), %d total this pass",
                        cursor.rowcount, deleted_total)

        # Clear out synced queue rows whose readings are gone.
        conn.execute(
            """
            DELETE FROM pending_sync
            WHERE sync_status = 'synced'
              AND local_reading_id NOT IN (SELECT id FROM sensor_readings)
            """
        )
        conn.commit()

    if deleted_total:
        _vacuum(db_path)

    end_size = Path(db_path).stat().st_size if Path(db_path).exists() else 0
    return max(0, start_size - end_size)


def _vacuum(db_path: str) -> None:
    """Return freed pages to the filesystem, but only if there is room to do it.

    VACUUM rebuilds the database into a temporary copy, so it briefly needs as
    much space again as the file occupies. Attempting it while nearly full is
    how a low-disk situation becomes a corrupt-database situation.
    """
    size = Path(db_path).stat().st_size
    if free_bytes() < size * 1.2:
        logger.warning(
            "Skipping VACUUM: needs ~%s free, only %s available. Deleted pages "
            "stay available for reuse, so writes continue normally.",
            human(size * 1.2), human(free_bytes()),
        )
        return
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("VACUUM")
        logger.info("VACUUM complete — database is now %s",
                    human(Path(db_path).stat().st_size))
    except sqlite3.Error as e:
        logger.error("VACUUM failed: %s", e)


# ---------------------------------------------------------------------------
# Stage 4 — last resort: un-uploaded images
# ---------------------------------------------------------------------------

def reclaim_unsent_images(target: int) -> int:
    """Delete the oldest images that have NOT reached the server yet.

    This is the only stage that discards data the server has never seen, and it
    exists because the alternative is worse. Images cost 1.22 MiB each while a
    sensor reading costs 676 bytes: one image is roughly 1,900 readings' worth
    of disk. If the uplink is down long enough, un-uploaded images fill the card,
    SQLite writes start failing, the BLE receiver stops acknowledging, and the
    node's own 36-minute buffer overflows -- losing the gas readings, which are
    the primary measurement, in order to preserve photographs.

    So when nothing else can reach the floor, the oldest images are sacrificed
    to keep sensor ingest alive. Set STORAGE_SACRIFICE_UNSENT_IMAGES=0 to refuse
    this and let the guard fail loudly instead.
    """
    if not config.STORAGE_SACRIFICE_UNSENT_IMAGES:
        logger.error(
            "Below the floor with only un-uploaded images left to reclaim, and "
            "STORAGE_SACRIFICE_UNSENT_IMAGES is off. Refusing to delete them. "
            "Sensor ingest WILL stop when the disk fills."
        )
        return 0

    pending_dir = Path(os.environ.get("PENDING_SYNC_DIR", "/home/zihan/pending_sync"))
    sync_db = Path(os.environ.get("SYNC_DB_PATH", "/home/zihan/sync_state.db"))
    reclaimed = 0
    removed = 0

    for path in _oldest_first(pending_dir):
        if free_bytes() >= target:
            break
        try:
            size = path.stat().st_size
            path.unlink()
            reclaimed += size
            removed += 1
            # Tell the image ledger, so sync.py does not keep trying to upload
            # a file that no longer exists.
            if sync_db.exists():
                with sqlite3.connect(sync_db) as conn:
                    conn.execute(
                        "UPDATE images SET status = 'discarded_low_disk' "
                        "WHERE filepath = ? AND status = 'pending'",
                        (str(path),),
                    )
                    conn.commit()
        except OSError as e:
            logger.warning("Could not remove %s: %s", path, e)

    if removed:
        logger.error(
            "LAST RESORT: discarded %d un-uploaded image(s) (%s) that the server "
            "never received, to keep sensor ingest alive. Check the uplink.",
            removed, human(reclaimed),
        )
    return reclaimed


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def enforce_image_budget(dry_run: bool = False) -> int:
    """Keep the image directories inside IMAGE_BUDGET_BYTES.

    Runs every pass, whatever the free space, so images can never grow into the
    room gas data needs. The two pipelines are independent in transport; this is
    what makes them independent in storage too.

    Uploaded images go first. Only if the budget is still exceeded are the
    oldest un-uploaded ones shed -- at that point the image uplink has been down
    long enough to bank a day of captures, and the alternative is letting them
    consume the whole card.
    """
    pending_dir = Path(os.environ.get("PENDING_SYNC_DIR", "/home/zihan/pending_sync"))
    archive_dir = Path(config.IMAGE_ARCHIVE_DIR)

    def dir_size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0

    used = dir_size(pending_dir) + dir_size(archive_dir)
    if used <= config.IMAGE_BUDGET_BYTES:
        return 0

    over = used - config.IMAGE_BUDGET_BYTES
    logger.warning("Images use %s, over the %s budget by %s — trimming",
                   human(used), human(config.IMAGE_BUDGET_BYTES), human(over))
    if dry_run:
        return 0

    reclaimed = 0
    # Uploaded copies first; the server already holds these.
    for path in _oldest_first(archive_dir):
        if reclaimed >= over:
            break
        try:
            size = path.stat().st_size
            path.unlink()
            reclaimed += size
        except OSError as e:
            logger.warning("Could not remove %s: %s", path, e)

    if reclaimed < over:
        shed = reclaim_unsent_images_by_bytes(pending_dir, over - reclaimed)
        reclaimed += shed

    logger.info("Reclaimed %s to stay inside the image budget", human(reclaimed))
    return reclaimed


def reclaim_unsent_images_by_bytes(pending_dir: Path, needed: int) -> int:
    """Shed the oldest un-uploaded images until `needed` bytes are freed."""
    if not config.STORAGE_SACRIFICE_UNSENT_IMAGES:
        logger.error(
            "Image budget exceeded with only un-uploaded images left and "
            "STORAGE_SACRIFICE_UNSENT_IMAGES is off. Not trimming."
        )
        return 0

    sync_db = Path(os.environ.get("SYNC_DB_PATH", "/home/zihan/sync_state.db"))
    reclaimed = 0
    removed = 0
    for path in _oldest_first(pending_dir):
        if reclaimed >= needed:
            break
        try:
            size = path.stat().st_size
            path.unlink()
            reclaimed += size
            removed += 1
            if sync_db.exists():
                with sqlite3.connect(sync_db) as conn:
                    conn.execute(
                        "UPDATE images SET status = 'discarded_over_budget' "
                        "WHERE filepath = ? AND status = 'pending'",
                        (str(path),),
                    )
                    conn.commit()
        except OSError as e:
            logger.warning("Could not remove %s: %s", path, e)

    if removed:
        logger.error(
            "Shed %d un-uploaded image(s) (%s) to stay inside the image budget. "
            "The image uplink has been down long enough to bank a day of "
            "captures — check it. Gas data is unaffected.",
            removed, human(reclaimed),
        )
    return reclaimed


def enforce(dry_run: bool = False) -> bool:
    """Bring free space back above the floor. Returns True if the floor holds."""
    # Images are capped on every pass, regardless of free space, so they cannot
    # grow into the space gas data needs.
    enforce_image_budget(dry_run)

    current = free_bytes()
    floor = config.STORAGE_MIN_FREE_BYTES
    target = config.STORAGE_TARGET_FREE_BYTES

    if current >= floor:
        logger.info("Free space %s is above the %s floor", human(current), human(floor))
        return True

    logger.warning("Free space %s has fallen below the %s floor — reclaiming to %s",
                   human(current), human(floor), human(target))

    if dry_run:
        logger.info("Dry run: no files or rows will be removed")
        return False

    total = 0
    for name, stage in (
        ("archived images", reclaim_archived_images),
        ("logs and backups", reclaim_logs),
        ("synced readings", reclaim_database),
        ("un-uploaded images (last resort)", reclaim_unsent_images),
    ):
        if free_bytes() >= target:
            break
        freed = stage(target)
        total += freed
        logger.info("Reclaimed %s from %s", human(freed), name)

    current = free_bytes()
    if current >= floor:
        logger.info("Recovered to %s free (reclaimed %s)", human(current), human(total))
        return True

    logger.error(
        "Could not reach the %s floor — %s free after reclaiming %s. What remains "
        "is un-uploaded sensor data, which is never deleted. Sensor ingest will "
        "stop when the disk fills; restore the uplink or free space manually.",
        human(floor), human(current), human(total),
    )
    return False


def report() -> None:
    db = get_db_manager()
    usage = shutil.disk_usage("/")
    queue = db.get_sync_queue_stats()
    pending_dir = Path(os.environ.get("PENDING_SYNC_DIR", "/home/zihan/pending_sync"))
    archive_dir = Path(config.IMAGE_ARCHIVE_DIR)

    def dir_size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0

    print(f"Disk           : {human(usage.used)} used / {human(usage.total)} total")
    print(f"Free           : {human(usage.free)}  (floor {human(config.STORAGE_MIN_FREE_BYTES)})")
    print(f"Status         : {'OK' if usage.free >= config.STORAGE_MIN_FREE_BYTES else 'BELOW FLOOR'}")
    print(f"Database       : {human(db.get_database_size())}, {db.get_reading_count()} readings")
    print(f"Upload queue   : {queue['pending']} pending, {queue['synced']} synced, {queue['failed']} parked")
    img_used = dir_size(pending_dir) + dir_size(archive_dir)
    print(f"Images pending : {human(dir_size(pending_dir))} in {pending_dir}")
    print(f"Images archived: {human(dir_size(archive_dir))} in {archive_dir}")
    print(f"Image budget   : {human(img_used)} of {human(config.IMAGE_BUDGET_BYTES)} "
          f"({100*img_used/config.IMAGE_BUDGET_BYTES:.1f}%)  "
          f"{'OK' if img_used <= config.IMAGE_BUDGET_BYTES else 'OVER'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep free disk space above the floor")
    parser.add_argument("--once", action="store_true", help="Run one check and exit")
    parser.add_argument("--dry-run", action="store_true", help="Report but delete nothing")
    parser.add_argument("--report", action="store_true", help="Print a storage summary and exit")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if args.report:
        report()
        return 0

    if args.once or args.dry_run:
        return 0 if enforce(dry_run=args.dry_run) else 1

    logger.info("Storage guard started — floor %s, target %s, every %.0f s",
                human(config.STORAGE_MIN_FREE_BYTES),
                human(config.STORAGE_TARGET_FREE_BYTES),
                config.STORAGE_CHECK_INTERVAL)

    while keep_running:
        try:
            enforce()
        except Exception:
            logger.exception("Storage check failed")

        slept = 0.0
        while keep_running and slept < config.STORAGE_CHECK_INTERVAL:
            time.sleep(1.0)
            slept += 1.0

    logger.info("Storage guard stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
