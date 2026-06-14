#!/usr/bin/env python3
"""
Batch uploader for Raspberry Pi image synchronization.

Default behavior:
- Initializes the SQLite ledger if it does not exist.
- Checks whether /home/pi/pending_sync contains at least 10 MiB of data.
- Uploads pending images sequentially to the configured endpoint.
- Marks successfully uploaded images in SQLite and deletes local files.
- Stops immediately on network errors, timeouts, or non-200 responses.
- Sleeps 1.5 seconds after each success to protect the receiving server.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests


DEFAULT_PENDING_DIR = Path(os.getenv("PENDING_SYNC_DIR", "/home/pi/pending_sync"))
DEFAULT_DB_PATH = Path(os.getenv("SYNC_DB_PATH", "/home/pi/sync_state.db"))
DEFAULT_THRESHOLD_BYTES = 10 * 1024 * 1024
DEFAULT_UPLOAD_URL = os.getenv(
    "UPLOAD_URL",
    "https://iot-upload.kalobiral.com.bd/api/upload-image",
)
DEFAULT_API_KEY = os.getenv("UPLOAD_API_KEY", "")
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("SYNC_REQUEST_TIMEOUT_SECONDS", "60"))
DEFAULT_THROTTLE_SECONDS = float(os.getenv("UPLOAD_THROTTLE_SECONDS", "1.5"))
DEFAULT_UPLOAD_RETRIES = int(os.getenv("UPLOAD_RETRIES", "3"))
DEFAULT_UPLOAD_RETRY_DELAY_SECONDS = float(os.getenv("UPLOAD_RETRY_DELAY_SECONDS", "5"))


logger = logging.getLogger("sync")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def ensure_runtime_ready(db_path: Path, pending_dir: Path) -> None:
    pending_dir.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                capture_time DATETIME NOT NULL,
                upload_time DATETIME,
                status TEXT NOT NULL DEFAULT 'pending'
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_images_status_capture_time
            ON images(status, capture_time)
            """
        )
        connection.commit()


def calculate_total_directory_size(pending_dir: Path) -> int:
    total_bytes = 0
    for item in pending_dir.iterdir():
        if item.is_file() and not item.name.startswith("."):
            total_bytes += item.stat().st_size
    return total_bytes


def fetch_pending_rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            """
            SELECT id, filename, filepath, capture_time, upload_time, status
            FROM images
            WHERE status = 'pending'
              AND filename NOT LIKE '.%'
            ORDER BY capture_time ASC, id ASC
            """
        )
        return cursor.fetchall()


def mark_uploaded(db_path: Path, image_id: int) -> None:
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE images
            SET status = 'uploaded', upload_time = ?
            WHERE id = ?
            """,
            (upload_time, image_id),
        )
        connection.commit()


def mark_missing(db_path: Path, image_id: int) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE images SET status = 'missing' WHERE id = ?",
            (image_id,),
        )
        connection.commit()


def upload_single_image(
    db_path: Path,
    row: sqlite3.Row,
    upload_url: str,
    api_key: str,
    timeout_seconds: int,
    throttle_seconds: float,
    upload_retries: int,
    retry_delay_seconds: float,
) -> bool:
    file_path = Path(row["filepath"])

    if not file_path.exists():
        logger.error(
            "File missing for pending ledger row id=%s, marking as missing: %s",
            row["id"],
            file_path,
        )
        mark_missing(db_path, row["id"])
        return True

    headers = {"x-api-key": api_key}

    response = None
    for attempt in range(1, upload_retries + 1):
        try:
            with file_path.open("rb") as file_handle:
                response = requests.post(
                    upload_url,
                    headers=headers,
                    files={"image": (row["filename"], file_handle, "image/jpeg")},
                    timeout=(10, timeout_seconds),
                )
        except requests.exceptions.RequestException as error:
            logger.warning(
                "Upload request failed for %s (attempt %d/%d): %s",
                file_path,
                attempt,
                upload_retries,
                error,
            )
            response = None
        else:
            if response.status_code in (200, 201):
                break

            logger.warning(
                "Upload failed for %s with status %s (attempt %d/%d) and body: %s",
                file_path,
                response.status_code,
                attempt,
                upload_retries,
                response.text[:500],
            )

            # Retry transient server-side failures; do not retry deterministic
            # client-side failures such as 400/401/404.
            if response.status_code < 500:
                return False

        if attempt < upload_retries:
            time.sleep(retry_delay_seconds * attempt)

    if response is None or response.status_code not in (200, 201):
        logger.error("Upload failed permanently for %s", file_path)
        return False

    mark_uploaded(db_path, row["id"])

    try:
        file_path.unlink()
    except OSError as error:
        logger.error("Uploaded row id=%s but could not delete %s: %s", row["id"], file_path, error)
    else:
        logger.info("Uploaded and deleted %s", file_path)

    time.sleep(throttle_seconds)
    return True


def run_sync(
    db_path: Path,
    pending_dir: Path,
    threshold_bytes: int,
    upload_url: str,
    api_key: str,
    timeout_seconds: int,
    throttle_seconds: float,
    upload_retries: int,
    retry_delay_seconds: float,
) -> int:
    ensure_runtime_ready(db_path, pending_dir)

    total_bytes = calculate_total_directory_size(pending_dir)
    logger.info("Pending directory size: %d bytes", total_bytes)

    if total_bytes < threshold_bytes:
        logger.info(
            "Threshold not met (%d < %d). Exiting without upload.",
            total_bytes,
            threshold_bytes,
        )
        return 0

    pending_rows = fetch_pending_rows(db_path)
    if not pending_rows:
        logger.info("Threshold met but no pending ledger rows were found. Exiting.")
        return 0

    logger.info("Starting upload of %d pending image(s)", len(pending_rows))

    for row in pending_rows:
        success = upload_single_image(
            db_path=db_path,
            row=row,
            upload_url=upload_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            throttle_seconds=throttle_seconds,
            upload_retries=upload_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        if not success:
            logger.error(
                "Upload failed for row id=%s; leaving it pending and stopping "
                "this cycle so a future timer run can retry safely.",
                row["id"],
            )
            return 1

    logger.info("Sync cycle completed successfully.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch upload Raspberry Pi images")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite ledger")
    parser.add_argument(
        "--pending-dir",
        type=Path,
        default=DEFAULT_PENDING_DIR,
        help="Directory containing pending images",
    )
    parser.add_argument(
        "--threshold-bytes",
        type=int,
        default=DEFAULT_THRESHOLD_BYTES,
        help="Minimum pooled bytes required before uploads start",
    )
    parser.add_argument(
        "--upload-url",
        default=DEFAULT_UPLOAD_URL,
        help="HTTP endpoint that receives multipart image uploads",
    )
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key for x-api-key header")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Read timeout used during upload requests",
    )
    parser.add_argument(
        "--throttle-seconds",
        type=float,
        default=DEFAULT_THROTTLE_SECONDS,
        help="Delay after every successful upload",
    )
    parser.add_argument(
        "--upload-retries",
        type=int,
        default=DEFAULT_UPLOAD_RETRIES,
        help="Number of upload attempts per image before leaving it pending",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=DEFAULT_UPLOAD_RETRY_DELAY_SECONDS,
        help="Base backoff delay between transient upload retries",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    return run_sync(
        db_path=args.db_path,
        pending_dir=args.pending_dir,
        threshold_bytes=args.threshold_bytes,
        upload_url=args.upload_url,
        api_key=args.api_key,
        timeout_seconds=args.timeout_seconds,
        throttle_seconds=args.throttle_seconds,
        upload_retries=args.upload_retries,
        retry_delay_seconds=args.retry_delay_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
