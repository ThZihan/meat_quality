#!/usr/bin/env python3
"""
IoT Meat Monitor — Raspberry Pi Background Client

Runs as a systemd service. Implements the full data recovery strategy:
  1. Reads the last timestamp/ID cursor from a local bookmark file
  2. On startup: catches up on all missed readings via /history
  3. During normal operation: polls recent /history every 5 seconds
  4. Updates bookmark after each successfully processed reading
  5. Retries with exponential backoff on failures

Data flow:
  ESP32 → Remote API → This client → Local SQLite DB → Dashboard reads DB

  ⚠ SUPERSEDED ON THIS BRANCH — do not run alongside ble_receiver.py.

  The ESP32 no longer has WiFi and no longer posts to the server, so polling
  /history returns nothing new: this service has no work left to do. The flow
  is now the reverse:

      ESP32 → BLE → ble_receiver.py → Local SQLite DB → cloud_uploader.py → API

  Running both at once actively corrupts the history. Readings ingested over
  BLE are keyed "ESP32-MeatMonitor:<seq>", while the same readings fetched back
  from the server are keyed by the server's own id. The UNIQUE index on
  source_id cannot see that those are the same measurement, so every reading
  would be stored twice under two different keys.

  The guard in main() enforces that. Kept for reference and for rolling back to
  the WiFi/HTTP architecture on masterV3-cloud-prodfix.
"""

import logging
import os
import signal
import sys
import time

import config
from api_client import load_bookmark, catch_up, poll_current

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("meat_monitor_client.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# Graceful shutdown
keep_running = True


def _signal_handler(signum, frame):
    global keep_running
    logger.info("Received signal %d, shutting down...", signum)
    keep_running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def main():
    # Refuse to start unless someone has deliberately opted in. See the module
    # docstring: concurrently with ble_receiver.py this duplicates every reading.
    if os.environ.get("MEAT_MONITOR_ALLOW_POLLING") != "1":
        logger.error(
            "This poller is superseded by ble_receiver.py on this branch and "
            "will duplicate every reading if both run. Set "
            "MEAT_MONITOR_ALLOW_POLLING=1 to override (only makes sense if the "
            "ESP32 is running the WiFi firmware from masterV3-cloud-prodfix)."
        )
        return 1

    logger.info("=" * 50)
    logger.info("Meat Monitor Pi Client Starting")
    logger.info("=" * 50)
    logger.info("API base: %s", config.SENSOR_API_BASE)
    logger.info("Poll interval: %ds", config.SENSOR_API_POLL_INTERVAL)
    logger.info("Bookmark file: %s", config.BOOKMARK_FILE)

    # 1. Load bookmark
    bookmark = load_bookmark()
    logger.info("Bookmark: %s", bookmark)

    # 2. Catch up on any missed readings
    try:
        bookmark = catch_up(bookmark)
    except Exception as e:
        # A temporary API outage at startup must not terminate the service.
        logger.error("Initial catch-up failed; entering poll mode: %s", e)

    # 3. Enter normal polling mode
    logger.info(
        "Entering normal poll mode (every %ds)", config.SENSOR_API_POLL_INTERVAL
    )
    consecutive_failures = 0

    while keep_running:
        try:
            new_bookmark = poll_current(bookmark)

            if new_bookmark != bookmark:
                bookmark = new_bookmark
            # A normal return means the API poll succeeded, even if there was
            # no reading newer than the bookmark.
            consecutive_failures = 0

        except Exception as e:
            logger.error("Error in poll cycle: %s", e)
            consecutive_failures += 1

        if consecutive_failures >= config.SENSOR_API_CATCHUP_FAILURE_THRESHOLD:
            logger.warning(
                "%d consecutive failures. Re-running catch-up...",
                consecutive_failures,
            )
            try:
                bookmark = load_bookmark()
                bookmark = catch_up(bookmark)
                consecutive_failures = 0
            except Exception as e:
                logger.error("Catch-up retry failed: %s", e)
                # Avoid hammering a failed endpoint with catch-up every cycle.
                consecutive_failures = 0

        time.sleep(config.SENSOR_API_POLL_INTERVAL)

    logger.info("Meat Monitor Pi Client stopped.")


if __name__ == "__main__":
    sys.exit(main() or 0)
