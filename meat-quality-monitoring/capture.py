  #!/usr/bin/env python3
"""
Continuous image capture service for Raspberry Pi.

Default behavior:
- Requests one high-resolution image every 30 seconds from the local Camera
  Module 3 feed server at http://127.0.0.1:5000/capture_highres.
- The feed server safely pauses streaming, performs the LED-assisted IMX708
  capture with autofocus, and resumes the live feed.
- Saves files to /home/pi/pending_sync/.
- Inserts a ledger record into SQLite with status='pending'.
- Keeps running even if capture or database operations fail.

Optional CLI flags are included only to support safe validation outside a
physical Raspberry Pi camera environment.
"""

from __future__ import annotations

import argparse
import logging
import os
import shlex
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from camera_config import (
    LED_BRIGHT_THRESHOLD,
    LED_DARK_THRESHOLD,
    LED_DUMMY_CAPTURE_HEIGHT,
    LED_DUMMY_CAPTURE_QUALITY,
    LED_DUMMY_CAPTURE_TIMEOUT_MS,
    LED_DUMMY_CAPTURE_WIDTH,
    LED_GPIO_PIN,
    LED_MAX_PWM,
    LED_MIN_PWM,
    LED_PWM_FREQUENCY,
    LED_PWM_STEP,
    LED_SETTLE_TIME,
    LED_THROTTLE_INTERVAL,
)
from led_controller import cleanup_led, get_led_controller
from light_detector import (
    LightDetectorConfig,
    analyze_brightness_from_jpeg,
    brightness_to_pwm,
)


DEFAULT_PENDING_DIR = Path(os.getenv("PENDING_SYNC_DIR", "/home/pi/pending_sync"))
DEFAULT_DB_PATH = Path(os.getenv("SYNC_DB_PATH", "/home/pi/sync_state.db"))
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_SIMULATED_IMAGE_SIZE = 1_500_000
DEFAULT_CAPTURE_URL = os.getenv(
    "CAMERA_CAPTURE_URL",
    "http://127.0.0.1:5000/capture_highres",
).strip()
DEFAULT_CAPTURE_HTTP_TIMEOUT_SECONDS = float(
    os.getenv("CAMERA_CAPTURE_HTTP_TIMEOUT", "30")
)


logger = logging.getLogger("capture")

led_controller = None
light_detector_config = LightDetectorConfig(
    dark_threshold=LED_DARK_THRESHOLD,
    bright_threshold=LED_BRIGHT_THRESHOLD,
    min_pwm=LED_MIN_PWM,
    max_pwm=LED_MAX_PWM,
    throttle_interval=LED_THROTTLE_INTERVAL,
    pwm_step=LED_PWM_STEP,
)
last_led_update_time: float | None = None


def get_capture_led_controller():
    """Lazily initialize the LED only for direct-camera capture mode.

    Coordinated captures are sent to the feed server, which already owns GPIO
    18 and performs the complete LED-assisted sequence. Avoiding eager GPIO
    initialization prevents the timed client from competing with that server.
    """
    global led_controller
    if led_controller is None:
        led_controller = get_led_controller(LED_GPIO_PIN, LED_PWM_FREQUENCY)
    return led_controller


def get_default_camera_command_template() -> str:
    env_command = os.getenv("CAMERA_COMMAND_TEMPLATE")
    if env_command:
        return env_command

    if shutil.which("libcamera-still"):
        return "libcamera-still -n -o {output}"

    if shutil.which("rpicam-still"):
        return "rpicam-still -n -o {output}"

    return "libcamera-still -n -o {output}"


DEFAULT_CAMERA_COMMAND_TEMPLATE = get_default_camera_command_template()


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


def generate_output_path(pending_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = pending_dir / f"img_{timestamp}.jpg"

    counter = 1
    while candidate.exists():
        candidate = pending_dir / f"img_{timestamp}_{counter:02d}.jpg"
        counter += 1

    return candidate


def build_capture_command(
    output_path: Path,
    command_template: str,
    *,
    width: int | None = None,
    height: int | None = None,
    timeout_ms: int | None = None,
    quality: int | None = None,
) -> list[str]:
    """Build the still-capture command while preserving the configured template."""
    command = shlex.split(command_template.format(output=shlex.quote(str(output_path))))
    executable = Path(command[0]).name if command else ""

    if executable in {"libcamera-still", "rpicam-still"}:
        if width is not None and "--width" not in command:
            command.extend(["--width", str(width)])
        if height is not None and "--height" not in command:
            command.extend(["--height", str(height)])
        if timeout_ms is not None and "-t" not in command and "--timeout" not in command:
            command.extend(["-t", str(timeout_ms)])
        if quality is not None and "-q" not in command and "--quality" not in command:
            command.extend(["-q", str(quality)])

    return command


def capture_with_libcamera(
    output_path: Path,
    command_template: str,
    *,
    width: int | None = None,
    height: int | None = None,
    timeout_ms: int | None = None,
    quality: int | None = None,
) -> None:
    command = build_capture_command(
        output_path,
        command_template,
        width=width,
        height=height,
        timeout_ms=timeout_ms,
        quality=quality,
    )
    logger.info("Capturing image with command: %s", " ".join(command))
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    )

    if completed.stdout.strip():
        logger.info("libcamera stdout: %s", completed.stdout.strip())

    if completed.stderr.strip():
        logger.info("libcamera stderr: %s", completed.stderr.strip())


def capture_from_feed_server(
    output_path: Path,
    capture_url: str,
    timeout_seconds: float,
) -> None:
    """Request a coordinated high-resolution capture from the live server.

    The Camera Module 3 feed server owns the IMX708 device. Its high-resolution
    endpoint pauses ``rpicam-vid``, performs the autofocus/LED-assisted still,
    and restarts the feed. Using the endpoint avoids two independent processes
    racing for the same camera.
    """
    logger.info("Requesting coordinated camera capture from %s", capture_url)
    http_request = urllib_request.Request(
        capture_url,
        headers={
            "Accept": "image/jpeg",
            "User-Agent": "meat-monitor-timed-capture/1.0",
        },
    )

    # Both systemd units start in parallel. If the timed client boots before
    # Flask has bound port 5000, wait briefly instead of failing the iteration.
    feed_startup_attempts = 30
    for attempt in range(1, feed_startup_attempts + 1):
        try:
            with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
                status_code = getattr(response, "status", response.getcode())
                content_type = response.headers.get_content_type()
                image_bytes = response.read()
            break
        except urllib_error.HTTPError as error:
            if error.code == 409 and attempt < feed_startup_attempts:
                # Another high-resolution capture is still running on the
                # feed server (for example after a service restart overlapped
                # a cycle). Wait for it to finish instead of failing.
                error.read(4096)
                logger.warning(
                    "Camera busy with another high-resolution capture (HTTP 409); retrying in 5s"
                )
                time.sleep(5)
                continue
            detail = error.read(4096).decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Camera feed server returned HTTP {error.code}: {detail or error.reason}"
            ) from error
        except urllib_error.URLError as error:
            if isinstance(error.reason, ConnectionRefusedError) and attempt < feed_startup_attempts:
                logger.warning(
                    "Camera feed server not ready (attempt %d/%d); retrying in 2s",
                    attempt,
                    feed_startup_attempts,
                )
                time.sleep(2)
                continue
            raise RuntimeError(f"Could not reach camera feed server: {error.reason}") from error
        except TimeoutError as error:
            raise RuntimeError(
                f"Camera feed server timed out after {timeout_seconds:.1f} seconds"
            ) from error
    else:
        raise RuntimeError(
            "Camera feed server did not become ready in time"
        )

    if status_code != 200:
        raise RuntimeError(f"Camera feed server returned HTTP {status_code}")
    if content_type != "image/jpeg":
        raise RuntimeError(
            f"Camera feed server returned unexpected content type {content_type!r}"
        )
    if (
        len(image_bytes) < 1000
        or not image_bytes.startswith(b"\xff\xd8")
        or not image_bytes.rstrip().endswith(b"\xff\xd9")
    ):
        raise RuntimeError(
            f"Camera feed server returned invalid JPEG data ({len(image_bytes)} bytes)"
        )

    temporary_path = output_path.with_name(f".{output_path.name}.part")
    try:
        temporary_path.write_bytes(image_bytes)
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    logger.info(
        "Coordinated Camera Module 3 capture saved: %s (%d bytes)",
        output_path,
        len(image_bytes),
    )


def set_led_duty_cycle(duty_cycle: float, *, record_update: bool = True) -> float:
    """Set the shared LED duty cycle for service captures."""
    global last_led_update_time
    controller = get_capture_led_controller()
    previous_duty = controller.duty_cycle
    controller.set_brightness(duty_cycle)
    if record_update and abs(controller.duty_cycle - previous_duty) > 0.001:
        last_led_update_time = time.monotonic()
    return controller.duty_cycle


def capture_with_led_assistance(output_path: Path, command_template: str) -> None:
    """Capture using strict preliminary-analysis-final sequencing.

    Sequence:
    1. Preliminary/dummy temporary capture.
    2. Evaluate light from that real captured image.
    3. Set LED PWM duty cycle using shared mapping logic.
    4. Short settle delay when illumination is enabled.
    5. Final capture to the requested output path.
    6. Immediate LED off in ``finally``.
    """
    dummy_output_path = output_path.parent / f".{output_path.stem}_light_probe{output_path.suffix}"

    try:
        set_led_duty_cycle(0.0)

        logger.info("Starting preliminary light-analysis capture: %s", dummy_output_path)
        capture_with_libcamera(
            dummy_output_path,
            command_template,
            width=LED_DUMMY_CAPTURE_WIDTH,
            height=LED_DUMMY_CAPTURE_HEIGHT,
            timeout_ms=LED_DUMMY_CAPTURE_TIMEOUT_MS,
            quality=LED_DUMMY_CAPTURE_QUALITY,
        )

        dummy_bytes = dummy_output_path.read_bytes()
        if len(dummy_bytes) < 100:
            raise RuntimeError("Preliminary capture returned empty or invalid image")

        brightness = analyze_brightness_from_jpeg(dummy_bytes)
        target_duty, _ = brightness_to_pwm(
            brightness=brightness,
            config=light_detector_config,
            current_duty=get_capture_led_controller().duty_cycle,
            last_update_time=last_led_update_time,
        )

        logger.info(
            "Preliminary light analysis brightness=%.1f -> LED duty=%.2f",
            brightness,
            target_duty,
        )
        set_led_duty_cycle(target_duty)

        if target_duty > 0.0 and LED_SETTLE_TIME > 0:
            time.sleep(LED_SETTLE_TIME)

        logger.info("Starting final capture after LED settle: %s", output_path)
        capture_with_libcamera(output_path, command_template)
    finally:
        try:
            set_led_duty_cycle(0.0)
        except Exception as cleanup_error:
            logger.debug("Failed to turn LED off after capture: %s", cleanup_error)

        if dummy_output_path.exists():
            try:
                dummy_output_path.unlink()
            except OSError as cleanup_error:
                logger.debug(
                    "Failed to remove dummy capture %s: %s",
                    dummy_output_path,
                    cleanup_error,
                )


def create_simulated_image(output_path: Path, image_size_bytes: int) -> None:
    logger.info("Creating simulated image at %s (%d bytes)", output_path, image_size_bytes)
    if image_size_bytes < 4:
        image_size_bytes = 4

    payload = b"\xff\xd8" + (b"\x00" * (image_size_bytes - 4)) + b"\xff\xd9"
    output_path.write_bytes(payload)


def insert_ledger_row(db_path: Path, output_path: Path, capture_time: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO images (filename, filepath, capture_time, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (output_path.name, str(output_path), capture_time),
        )
        connection.commit()


def capture_once(
    db_path: Path,
    pending_dir: Path,
    command_template: str,
    simulate: bool,
    simulated_image_size: int,
    capture_url: str | None = None,
    capture_http_timeout: float = DEFAULT_CAPTURE_HTTP_TIMEOUT_SECONDS,
) -> Path:
    ensure_runtime_ready(db_path, pending_dir)
    output_path = generate_output_path(pending_dir)
    capture_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if simulate:
            create_simulated_image(output_path, simulated_image_size)
        elif capture_url:
            capture_from_feed_server(
                output_path=output_path,
                capture_url=capture_url,
                timeout_seconds=capture_http_timeout,
            )
        else:
            capture_with_led_assistance(output_path, command_template)

        insert_ledger_row(db_path, output_path, capture_time)
        logger.info("Captured and recorded image: %s", output_path)
        return output_path

    except Exception:
        if output_path.exists():
            try:
                output_path.unlink()
                logger.warning("Removed orphaned file after failed ledger write: %s", output_path)
            except OSError as cleanup_error:
                logger.error("Failed to remove orphaned file %s: %s", output_path, cleanup_error)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuous Raspberry Pi image capture")
    parser.add_argument("--once", action="store_true", help="Capture a single image and exit")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Seconds between captures in continuous mode",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite ledger database",
    )
    parser.add_argument(
        "--pending-dir",
        type=Path,
        default=DEFAULT_PENDING_DIR,
        help="Directory where captured images are stored before sync",
    )
    parser.add_argument(
        "--camera-command-template",
        default=DEFAULT_CAMERA_COMMAND_TEMPLATE,
        help="Command template used for subprocess capture; must include {output}",
    )
    parser.add_argument(
        "--capture-url",
        default=DEFAULT_CAPTURE_URL,
        help=(
            "Camera feed-server capture endpoint. Defaults to the local Module 3 "
            "high-resolution endpoint. Pass an empty value with --direct-camera "
            "to use rpicam-still directly."
        ),
    )
    parser.add_argument(
        "--capture-http-timeout",
        type=float,
        default=DEFAULT_CAPTURE_HTTP_TIMEOUT_SECONDS,
        help="HTTP timeout in seconds for coordinated feed-server captures",
    )
    parser.add_argument(
        "--direct-camera",
        action="store_true",
        help="Bypass the feed server and invoke rpicam-still directly",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Write a simulated image instead of calling libcamera-still",
    )
    parser.add_argument(
        "--simulate-size-bytes",
        type=int,
        default=DEFAULT_SIMULATED_IMAGE_SIZE,
        help="Size of the simulated image used with --simulate",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    capture_url = None if args.direct_camera else args.capture_url.strip() or None

    try:
        if capture_url is None and "{output}" not in args.camera_command_template and not args.simulate:
            raise ValueError("--camera-command-template must contain the {output} placeholder")

        if not args.simulate:
            if capture_url:
                logger.info(
                    "Using coordinated Camera Module 3 endpoint %s (interval %.1fs)",
                    capture_url,
                    args.interval,
                )
            else:
                logger.info("Using direct camera command mode (interval %.1fs)", args.interval)

        if args.once:
            try:
                capture_once(
                    db_path=args.db_path,
                    pending_dir=args.pending_dir,
                    command_template=args.camera_command_template,
                    simulate=args.simulate,
                    simulated_image_size=args.simulate_size_bytes,
                    capture_url=capture_url,
                    capture_http_timeout=args.capture_http_timeout,
                )
                return 0
            except Exception as error:
                logger.exception("Single capture failed: %s", error)
                return 1

        while True:
            try:
                capture_once(
                    db_path=args.db_path,
                    pending_dir=args.pending_dir,
                    command_template=args.camera_command_template,
                    simulate=args.simulate,
                    simulated_image_size=args.simulate_size_bytes,
                    capture_url=capture_url,
                    capture_http_timeout=args.capture_http_timeout,
                )
            except Exception as error:
                logger.exception("Capture loop iteration failed: %s", error)

            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Capture service interrupted, shutting down")
        return 0
    finally:
        if led_controller is not None:
            try:
                led_controller.turn_off()
            except Exception:
                pass
            cleanup_led()


if __name__ == "__main__":
    raise SystemExit(main())
