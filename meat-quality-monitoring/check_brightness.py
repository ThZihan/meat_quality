#!/usr/bin/env python3
"""
Brightness Checker - Fetches a frame from the running camera feed
and reports the mean brightness (0-255 scale).

Usage:
    # Single reading
    python3 check_brightness.py

    # Monitor for N seconds (1 reading per second)
    python3 check_brightness.py --duration 15

    # Custom server URL
    python3 check_brightness.py --url http://192.168.1.100:5000/capture
"""

import sys
import time
import argparse

sys.path.insert(0, ".")

from light_detector import analyze_brightness_from_jpeg
from camera_config import LED_DARK_THRESHOLD, LED_BRIGHT_THRESHOLD

try:
    import urllib.request
except ImportError:
    print("urllib not available")
    sys.exit(1)

# Thresholds imported from camera_config.py (single source of truth)
DARK_THRESHOLD = LED_DARK_THRESHOLD
BRIGHT_THRESHOLD = LED_BRIGHT_THRESHOLD


def classify(brightness: float) -> str:
    """Classify brightness reading against configured thresholds."""
    if brightness < DARK_THRESHOLD:
        return "DARK (LED ON)"
    elif brightness > BRIGHT_THRESHOLD:
        return "BRIGHT (LED OFF)"
    else:
        return "HYSTERESIS (unchanged)"


def fetch_brightness(url: str) -> float:
    """Fetch a JPEG frame from the camera feed and return its brightness."""
    resp = urllib.request.urlopen(url)
    jpeg_bytes = resp.read()
    return analyze_brightness_from_jpeg(jpeg_bytes)


def main():
    parser = argparse.ArgumentParser(description="Check brightness from camera feed")
    parser.add_argument(
        "--url",
        default="http://localhost:5000/capture",
        help="Camera feed capture endpoint URL (default: http://localhost:5000/capture)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Monitor duration in seconds (0 = single reading, default: 0)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between readings during monitoring (default: 1.0)",
    )
    args = parser.parse_args()

    # --- Single reading mode ---
    if args.duration <= 0:
        brightness = fetch_brightness(args.url)
        print(f"Brightness: {brightness:.2f}  |  {classify(brightness)}")
        return

    # --- Continuous monitoring mode ---
    readings = []
    start = time.time()
    header = f"{'Time':>6}s  {'Brightness':>10}  {'Status':<20}"
    print(header)
    print("-" * len(header))

    while time.time() - start < args.duration:
        try:
            brightness = fetch_brightness(args.url)
            elapsed = time.time() - start
            readings.append(brightness)
            print(f"{elapsed:6.1f}s  {brightness:10.2f}  {classify(brightness):<20}")
        except Exception as e:
            print(f"{time.time() - start:6.1f}s  ERROR: {e}")

        time.sleep(args.interval)

    print("-" * len(header))
    if readings:
        print(
            f"Min: {min(readings):.2f}  "
            f"Max: {max(readings):.2f}  "
            f"Avg: {sum(readings) / len(readings):.2f}  "
            f"Samples: {len(readings)}"
        )


if __name__ == "__main__":
    main()
