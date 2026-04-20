#!/usr/bin/env python3
"""
Live Camera Feed Server using Flask
Provides MJPEG streaming from Raspberry Pi Camera Module 3 at localhost/camera_feed
Uses rpicam-vid for streaming (libcamera stack) with autofocus support
"""

import logging
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, Generator, Dict, Any
from flask import Flask, Response, render_template, request

# Import camera configuration
from camera_config import (
    CameraFeedConfig,
    CameraCaptureConfig,
    DEFAULT_FEED_CONFIG,
    DEFAULT_CAPTURE_CONFIG,
    RESOLUTION_PRESETS,
    FPS_PRESETS,
    RPICAM_VID_CMD,
    RPICAM_STILL_CMD,
    MAX_BUFFER_SIZE,
    BUFFER_READ_SIZE,
    PROCESS_TERMINATION_TIMEOUT,
    MAX_CONSECUTIVE_ERRORS,
    JPEG_START_MARKER,
    JPEG_END_MARKER,
    MULTIPART_BOUNDARY,
    LED_GPIO_PIN,
    LED_PWM_FREQUENCY,
    LED_DARK_THRESHOLD,
    LED_BRIGHT_THRESHOLD,
    LED_MIN_PWM,
    LED_MAX_PWM,
    LED_THROTTLE_INTERVAL,
    LED_PWM_STEP,
    LED_ANALYSIS_INTERVAL,
    LED_DUMMY_CAPTURE_WIDTH,
    LED_DUMMY_CAPTURE_HEIGHT,
    LED_DUMMY_CAPTURE_QUALITY,
    LED_DUMMY_CAPTURE_TIMEOUT_MS,
    LED_SETTLE_TIME,
)
from led_controller import cleanup_led, get_led_controller
from light_detector import (
    LightDetectorConfig,
    analyze_brightness_from_jpeg,
    brightness_to_pwm,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global camera process
camera_process: Optional[subprocess.Popen] = None
camera_lock = threading.Lock()
shutdown_event = threading.Event()

# Global shared frame buffer for capture requests
latest_frame: Optional[bytes] = None
frame_lock = threading.Lock()

# Global LED / light-monitor state
led_lock = threading.Lock()
led_controller = get_led_controller(LED_GPIO_PIN, LED_PWM_FREQUENCY)
light_detector_config = LightDetectorConfig(
    dark_threshold=LED_DARK_THRESHOLD,
    bright_threshold=LED_BRIGHT_THRESHOLD,
    min_pwm=LED_MIN_PWM,
    max_pwm=LED_MAX_PWM,
    throttle_interval=LED_THROTTLE_INTERVAL,
    pwm_step=LED_PWM_STEP,
)
last_led_update_time: Optional[float] = None
last_light_analysis_time: float = 0.0


class CameraError(Exception):
    """Base exception for camera-related errors"""
    pass


class CameraInitializationError(CameraError):
    """Exception raised when camera initialization fails"""
    pass


class CameraProcessError(CameraError):
    """Exception raised when camera process encounters an error"""
    pass


def check_rpicam_available() -> bool:
    """
    Check if rpicam-vid is available on the system
    
    Returns:
        True if rpicam-vid is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["which", RPICAM_VID_CMD],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error(f"Error checking {RPICAM_VID_CMD} availability: {e}")
        return False


def get_led_duty_cycle() -> float:
    """Return the current LED PWM duty cycle."""
    with led_lock:
        return led_controller.duty_cycle


def set_led_duty_cycle(duty_cycle: float, *, record_update: bool = True) -> float:
    """Set LED PWM duty cycle and optionally record the update timestamp."""
    global last_led_update_time
    with led_lock:
        previous_duty = led_controller.duty_cycle
        logger.info(
            "LED debug: applying duty request=%.2f previous=%.2f available=%s record_update=%s",
            duty_cycle,
            previous_duty,
            led_controller.available,
            record_update,
        )
        led_controller.set_brightness(duty_cycle)
        if record_update and abs(led_controller.duty_cycle - previous_duty) > 0.001:
            last_led_update_time = time.monotonic()
        logger.info(
            "LED debug: controller duty after apply=%.2f last_update_time_set=%s",
            led_controller.duty_cycle,
            record_update and abs(led_controller.duty_cycle - previous_duty) > 0.001,
        )
        return led_controller.duty_cycle


def update_led_from_jpeg(jpeg_bytes: bytes) -> Dict[str, Any]:
    """Analyse a JPEG frame and update LED PWM using shared mapping logic."""
    brightness = analyze_brightness_from_jpeg(jpeg_bytes)
    current_duty = get_led_duty_cycle()
    target_duty, changed = brightness_to_pwm(
        brightness=brightness,
        config=light_detector_config,
        current_duty=current_duty,
        last_update_time=last_led_update_time,
    )

    last_update_age = (
        None
        if last_led_update_time is None
        else time.monotonic() - last_led_update_time
    )
    logger.info(
        "LED debug: brightness=%.1f current=%.2f target=%.2f changed=%s available=%s last_update_age=%s",
        brightness,
        current_duty,
        target_duty,
        changed,
        led_controller.available,
        "none" if last_update_age is None else f"{last_update_age:.2f}s",
    )

    if changed:
        set_led_duty_cycle(target_duty)

    return {
        'brightness': brightness,
        'current_duty': current_duty,
        'target_duty': target_duty,
        'changed': changed,
    }


def build_still_capture_command(
    config: CameraCaptureConfig,
    output_target: str,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    quality: int = 95,
    timeout_ms: Optional[int] = None,
) -> list[str]:
    """Build an `rpicam-still` command for JPEG capture."""
    cmd = [
        RPICAM_STILL_CMD,
        "-t", str(timeout_ms or config.timeout),
        "-o", output_target,
        "--width", str(width or config.width),
        "--height", str(height or config.height),
        "--nopreview",
        "--quality", str(quality),
        "--encoding", "jpg",
    ]

    if config.iso > 0:
        cmd.extend(["--immediate", "--gain", str(max(1, config.iso // 100))])

    cmd.extend(["--autofocus-mode", config.autofocus_mode.value])
    cmd.extend(["--autofocus-range", config.autofocus_range.value])
    cmd.extend(["--autofocus-speed", config.autofocus_speed.value])

    if config.autofocus_trigger:
        cmd.extend(["--autofocus-trigger", config.autofocus_trigger])

    return cmd


def pause_live_feed_for_capture() -> None:
    """Stop the live feed process so still capture can use the camera."""
    global camera_process
    old_camera_process: Optional[subprocess.Popen] = None

    with camera_lock:
        old_camera_process = camera_process
        camera_process = None

    if old_camera_process is not None:
        try:
            if old_camera_process.poll() is None:
                old_camera_process.terminate()
                old_camera_process.wait(timeout=PROCESS_TERMINATION_TIMEOUT)
            logger.info("Live feed paused successfully")
        except subprocess.TimeoutExpired:
            logger.warning("Camera process did not terminate gracefully, killing")
            old_camera_process.kill()
            old_camera_process.wait()
        except Exception as e:
            logger.error(f"Error pausing live feed: {e}")

    time.sleep(0.5)


def restart_live_feed_after_capture() -> None:
    """Restart the live feed after a still capture attempt."""
    try:
        get_camera_process()
        logger.info("Live feed restarted successfully")
    except Exception as e:
        logger.error(f"Failed to restart live feed: {e}")


def get_camera_process(config: CameraFeedConfig = DEFAULT_FEED_CONFIG) -> Optional[subprocess.Popen]:
    """
    Get or initialize the rpicam-vid process for continuous capture
    
    Args:
        config: Camera configuration object
        
    Returns:
        The camera subprocess or None if initialization failed
        
    Raises:
        CameraInitializationError: If camera cannot be initialized
    """
    global camera_process
    
    with camera_lock:
        if camera_process is None or camera_process.poll() is not None:
            try:
                cmd = config.get_rpicam_args()
                
                logger.info(f"Starting camera with config: {config.frame_width}x{config.frame_height} @ {config.frame_rate}fps")
                logger.debug(f"Command: {' '.join(cmd)}")
                
                camera_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=10**8
                )
                
                # Give camera time to initialize
                time.sleep(0.5)
                
                # Check if process is still running
                if camera_process.poll() is not None:
                    stderr = camera_process.stderr.read().decode('utf-8', errors='ignore')
                    raise CameraInitializationError(f"Camera process exited immediately: {stderr}")
                
                logger.info(f"Camera started successfully: PID {camera_process.pid}")
                logger.info(f"Autofocus: mode={config.autofocus_mode.value}, range={config.autofocus_range.value}, speed={config.autofocus_speed.value}")
                
            except FileNotFoundError as e:
                logger.error(f"{RPICAM_VID_CMD} not found: {e}")
                raise CameraInitializationError(
                    f"{RPICAM_VID_CMD} not found. Please install libcamera-apps: sudo apt install libcamera-apps"
                )
            except Exception as e:
                logger.error(f"Failed to start camera: {e}")
                raise CameraInitializationError(f"Failed to start camera: {e}")
        
        return camera_process


def find_jpeg_markers(data: bytes, start_pos: int = 0) -> Optional[Tuple[int, int]]:
    """
    Find JPEG start (0xFFD8) and end (0xFFD9) markers in data
    
    Args:
        data: Byte data to search for JPEG markers
        start_pos: Position to start searching from
        
    Returns:
        Tuple of (start, end) positions or None if markers not found
    """
    # Find JPEG start marker
    start = data.find(JPEG_START_MARKER, start_pos)
    if start == -1:
        return None
    
    # Find JPEG end marker after start
    end = data.find(JPEG_END_MARKER, start + 2)
    if end == -1:
        return None
    
    return (start, end + 2)  # Include the end marker


def generate_frames(config: CameraFeedConfig = DEFAULT_FEED_CONFIG) -> Generator[bytes, None, None]:
    """
    Generator function that yields MJPEG frames from rpicam-vid
    Properly formats as multipart HTTP response
    
    Args:
        config: Camera configuration object
        
    Yields:
        Multipart formatted MJPEG frames
        
    Raises:
        CameraProcessError: If camera process encounters an error
    """
    try:
        proc = get_camera_process(config)
        if proc is None:
            logger.error("Camera process is None")
            return
        
        buffer = b''
        consecutive_errors = 0
        max_consecutive_errors = MAX_CONSECUTIVE_ERRORS
        
        while not shutdown_event.is_set():
            try:
                # Read data from rpicam-vid
                data = proc.stdout.read(BUFFER_READ_SIZE)
                if not data:
                    if proc.poll() is not None:
                        logger.warning("Camera process terminated, restarting...")
                        consecutive_errors += 1
                        
                        if consecutive_errors >= max_consecutive_errors:
                            raise CameraProcessError("Camera process terminated too many times")
                        
                        global camera_process
                        camera_process = None
                        proc = get_camera_process(config)
                        if proc is None:
                            logger.error("Failed to restart camera process")
                            break
                        buffer = b''
                        continue
                    else:
                        # Process still running but no data, wait a bit
                        time.sleep(0.01)
                        continue
                
                consecutive_errors = 0  # Reset error counter on successful read
                buffer += data
                
                # Extract complete JPEG frames from buffer
                while True:
                    result = find_jpeg_markers(buffer)
                    if result is None:
                        # No complete frame found, keep accumulating
                        # Limit buffer size to prevent memory issues
                        if len(buffer) > MAX_BUFFER_SIZE:
                            logger.warning("Buffer too large, clearing")
                            buffer = b''
                        break
                    
                    start, end = result
                    jpeg_frame = buffer[start:end]
                    
                    # Update shared frame buffer for capture requests (thread-safe)
                    with frame_lock:
                        global latest_frame
                        latest_frame = jpeg_frame

                    global last_light_analysis_time
                    now = time.monotonic()
                    if now - last_light_analysis_time >= LED_ANALYSIS_INTERVAL:
                        last_light_analysis_time = now
                        led_state = update_led_from_jpeg(jpeg_frame)
                        if led_state['changed']:
                            logger.info(
                                "Live light monitor: brightness=%.1f -> LED duty=%.2f",
                                led_state['brightness'],
                                led_state['target_duty'],
                            )
                    
                    # Remove the processed frame from buffer
                    buffer = buffer[end:]
                    
                    # Yield frame as part of multipart response
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg_frame + b'\r\n')
                    
            except GeneratorExit:
                logger.info("Stream closed by client")
                break
            except Exception as e:
                logger.error(f"Error in frame generation loop: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    raise CameraProcessError(f"Too many consecutive errors: {e}")
                time.sleep(0.1)
                
    except CameraProcessError as e:
        logger.error(f"Camera process error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating frames: {e}")
        raise CameraProcessError(f"Unexpected error: {e}")


@app.route('/')
def index() -> str:
    """
    Render the camera feed page
    
    Returns:
        Rendered HTML template
    """
    return render_template('camera_feed.html',
                          frame_width=DEFAULT_FEED_CONFIG.frame_width,
                          frame_height=DEFAULT_FEED_CONFIG.frame_height)


@app.route('/video_feed')
def video_feed() -> Response:
    """
    Video streaming route
    Returns a multipart response with MJPEG frames
    
    Returns:
        Flask Response object with MJPEG stream
    """
    return Response(generate_frames(),
                    mimetype=f'multipart/x-mixed-replace; boundary={MULTIPART_BOUNDARY.decode()}')


@app.route('/status')
def status() -> Dict[str, Any]:
    """
    Camera status endpoint
    
    Returns:
        Dictionary containing camera status information
    """
    try:
        proc = get_camera_process()
        if proc is None:
            return {
                'status': 'error',
                'message': 'Camera not available'
            }
        
        return {
            'status': 'ok',
            'frame_width': DEFAULT_FEED_CONFIG.frame_width,
            'frame_height': DEFAULT_FEED_CONFIG.frame_height,
            'fps': DEFAULT_FEED_CONFIG.frame_rate,
            'pid': proc.pid,
            'camera_type': f'{RPICAM_VID_CMD} (libcamera)',
            'camera_model': 'Raspberry Pi Camera Module 3',
            'autofocus_mode': DEFAULT_FEED_CONFIG.autofocus_mode.value,
            'autofocus_range': DEFAULT_FEED_CONFIG.autofocus_range.value,
            'autofocus_speed': DEFAULT_FEED_CONFIG.autofocus_speed.value
        }
    except CameraInitializationError as e:
        return {
            'status': 'error',
            'message': str(e)
        }


@app.route('/config', methods=['GET', 'POST'])
def config() -> Dict[str, Any]:
    """
    Camera configuration endpoint
    GET: Returns current configuration
    POST: Updates configuration (requires restart)
    
    Returns:
        Dictionary containing configuration information
    """
    if request.method == 'POST':
        # Update configuration from request
        data = request.get_json()
        if data:
            if 'frame_rate' in data:
                DEFAULT_FEED_CONFIG.frame_rate = int(data['frame_rate'])
            if 'frame_width' in data:
                DEFAULT_FEED_CONFIG.frame_width = int(data['frame_width'])
            if 'frame_height' in data:
                DEFAULT_FEED_CONFIG.frame_height = int(data['frame_height'])
            if 'jpeg_quality' in data:
                DEFAULT_FEED_CONFIG.jpeg_quality = int(data['jpeg_quality'])
            if 'autofocus_mode' in data:
                from camera_config import AutofocusMode
                DEFAULT_FEED_CONFIG.autofocus_mode = AutofocusMode(data['autofocus_mode'])
            if 'autofocus_range' in data:
                from camera_config import AutofocusRange
                DEFAULT_FEED_CONFIG.autofocus_range = AutofocusRange(data['autofocus_range'])
            if 'autofocus_speed' in data:
                from camera_config import AutofocusSpeed
                DEFAULT_FEED_CONFIG.autofocus_speed = AutofocusSpeed(data['autofocus_speed'])
            
            # Restart camera with new configuration
            cleanup_camera()
            try:
                get_camera_process()
            except CameraInitializationError as e:
                return {
                    'status': 'error',
                    'message': str(e)
                }
    
    return {
        'status': 'ok',
        'config': {
            'frame_rate': DEFAULT_FEED_CONFIG.frame_rate,
            'frame_width': DEFAULT_FEED_CONFIG.frame_width,
            'frame_height': DEFAULT_FEED_CONFIG.frame_height,
            'jpeg_quality': DEFAULT_FEED_CONFIG.jpeg_quality,
            'autofocus_mode': DEFAULT_FEED_CONFIG.autofocus_mode.value,
            'autofocus_range': DEFAULT_FEED_CONFIG.autofocus_range.value,
            'autofocus_speed': DEFAULT_FEED_CONFIG.autofocus_speed.value
        }
    }


@app.route('/autofocus_trigger', methods=['POST'])
def autofocus_trigger() -> Dict[str, Any]:
    """
    Trigger autofocus on Camera Module 3
    
    Returns:
        Dictionary containing trigger status
    """
    try:
        data = request.get_json() or {}
        trigger_type = data.get('trigger', 'start')
        
        if trigger_type not in ['start', 'cancel']:
            return {
                'status': 'error',
                'message': 'Invalid trigger type. Use "start" or "cancel"'
            }
        
        # Trigger autofocus by restarting camera with trigger
        old_config = DEFAULT_FEED_CONFIG.autofocus_trigger
        DEFAULT_FEED_CONFIG.autofocus_trigger = trigger_type
        cleanup_camera()
        get_camera_process()
        DEFAULT_FEED_CONFIG.autofocus_trigger = None  # Reset after trigger
        
        return {
            'status': 'ok',
            'message': f'Autofocus {trigger_type} triggered'
        }
    except Exception as e:
        logger.error(f"Error triggering autofocus: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


@app.route('/capture')
def capture_frame() -> Response:
    """
    Capture endpoint - Returns the latest JPEG frame from the camera stream
    (Low resolution: 800x480 for fast capture from live feed)
    
    Returns:
        Flask Response with JPEG image data or error message
    """
    try:
        with frame_lock:
            global latest_frame
            if latest_frame is None:
                return Response(
                    {'status': 'error',
                     'message': 'Camera not ready - no frame available yet. Please ensure camera feed is running.'},
                    status=400
                )
            
            # Return the latest frame as JPEG
            return Response(
                latest_frame,
                mimetype='image/jpeg',
                headers={
                    'Content-Disposition': 'attachment; filename=capture.jpg',
                    'Content-Length': str(len(latest_frame))
                }
            )
    except Exception as e:
        logger.error(f"Error in capture endpoint: {e}")
        return Response(
            {'status': 'error', 'message': str(e)},
            status=500
        )


@app.route('/capture_highres')
def capture_highres_frame() -> Response:
    """
    High-resolution capture endpoint - Captures a new image at maximum resolution
    Uses rpicam-still for high-quality capture (4608x2592)
    
    Note: Temporarily pauses the live feed to capture at high resolution,
    then restarts the feed. This is necessary because the camera can only
    be accessed by one process at a time.
    
    Returns:
        Flask Response with JPEG image data or error message
    """
    config = DEFAULT_CAPTURE_CONFIG
    dummy_capture_path: Optional[Path] = None

    logger.info(f"High-res capture: {config.width}x{config.height}, ISO={config.iso}")
    logger.info("Pausing live feed for LED-assisted high-resolution capture...")

    pause_live_feed_for_capture()

    try:
        # Strict sequence: LED off -> dummy capture -> light analysis -> PWM set -> settle -> final capture.
        set_led_duty_cycle(0.0)

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            dummy_capture_path = Path(temp_file.name)

        dummy_cmd = build_still_capture_command(
            config,
            str(dummy_capture_path),
            width=min(config.width, LED_DUMMY_CAPTURE_WIDTH),
            height=min(config.height, LED_DUMMY_CAPTURE_HEIGHT),
            quality=LED_DUMMY_CAPTURE_QUALITY,
            timeout_ms=LED_DUMMY_CAPTURE_TIMEOUT_MS,
        )
        logger.info("Running preliminary capture for light analysis")
        logger.debug(f"Preliminary capture command: {' '.join(dummy_cmd)}")

        dummy_result = subprocess.run(
            dummy_cmd,
            capture_output=True,
            timeout=max(config.timeout / 1000, 1.0) + 2,
        )

        if dummy_result.returncode != 0:
            error_msg = dummy_result.stderr.decode('utf-8', errors='ignore')
            logger.error(f"Preliminary capture failed: {error_msg}")
            return Response(
                {'status': 'error', 'message': f'Preliminary capture failed: {error_msg}'},
                status=500
            )

        dummy_bytes = dummy_capture_path.read_bytes()
        if len(dummy_bytes) < 100:
            logger.error("Preliminary capture returned empty or invalid image")
            return Response(
                {'status': 'error', 'message': 'Preliminary capture returned empty or invalid image'},
                status=500
            )

        led_state = update_led_from_jpeg(dummy_bytes)
        logger.info(
            "Light analysis: brightness=%.1f -> LED duty=%.2f",
            led_state['brightness'],
            led_state['target_duty'],
        )

        if led_state['target_duty'] > 0.0 and LED_SETTLE_TIME > 0:
            time.sleep(LED_SETTLE_TIME)

        final_cmd = build_still_capture_command(config, "-")
        logger.debug(f"High-res capture command: {' '.join(final_cmd)}")

        final_result = subprocess.run(
            final_cmd,
            capture_output=True,
            timeout=config.timeout / 1000 + 5,
        )

        if final_result.returncode != 0:
            error_msg = final_result.stderr.decode('utf-8', errors='ignore')
            logger.error(f"High-res capture failed: {error_msg}")
            return Response(
                {'status': 'error', 'message': f'Capture failed: {error_msg}'},
                status=500
            )

        image_bytes = final_result.stdout
        if not image_bytes or len(image_bytes) < 1000:
            logger.error("High-res capture returned empty or invalid image")
            return Response(
                {'status': 'error', 'message': 'Capture returned empty or invalid image'},
                status=500
            )

        logger.info(f"High-res capture successful: {len(image_bytes)} bytes")
        return Response(
            image_bytes,
            mimetype='image/jpeg',
            headers={
                'Content-Disposition': 'attachment; filename=capture_highres.jpg',
                'Content-Length': str(len(image_bytes))
            }
        )

    except subprocess.TimeoutExpired:
        logger.error("High-res capture timed out")
        return Response(
            {'status': 'error', 'message': 'Capture timed out'},
            status=500
        )
    except FileNotFoundError:
        logger.error(f"{RPICAM_STILL_CMD} not found")
        return Response(
            {'status': 'error', 'message': f'{RPICAM_STILL_CMD} not found. Please install libcamera-apps'},
            status=500
        )
    except Exception as e:
        logger.error(f"Error in high-res capture endpoint: {e}")
        return Response(
            {'status': 'error', 'message': str(e)},
            status=500
        )
    finally:
        try:
            set_led_duty_cycle(0.0)
        except Exception as e:
            logger.debug(f"Failed to turn LED off after capture: {e}")

        if dummy_capture_path is not None:
            try:
                dummy_capture_path.unlink(missing_ok=True)
            except OSError as e:
                logger.debug(f"Failed to remove dummy capture {dummy_capture_path}: {e}")

        logger.info("Restarting live feed...")
        restart_live_feed_after_capture()


def cleanup_camera() -> None:
    """
    Cleanup camera resources on shutdown
    Thread-safe camera process termination
    """
    global camera_process
    with camera_lock:
        if camera_process is not None:
            try:
                if camera_process.poll() is None:
                    # Try graceful termination first
                    camera_process.terminate()
                    try:
                        camera_process.wait(timeout=PROCESS_TERMINATION_TIMEOUT)
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful termination fails
                        logger.warning("Camera process did not terminate gracefully, killing")
                        camera_process.kill()
                        camera_process.wait()
                logger.info("Camera closed successfully")
            except Exception as e:
                logger.error(f"Error closing camera: {e}")
            finally:
                camera_process = None

    try:
        set_led_duty_cycle(0.0)
    except Exception as e:
        logger.debug(f"Failed to turn LED off during cleanup: {e}")


def signal_handler(signum: int, frame) -> None:
    """
    Handle shutdown signals gracefully
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_event.set()
    cleanup_camera()
    cleanup_led()
    exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Live Camera Feed Server - Camera Module 3")
    logger.info("=" * 60)
    
    # Check rpicam-vid availability
    if not check_rpicam_available():
        logger.error(f"{RPICAM_VID_CMD} not found!")
        logger.error("Please install libcamera-apps:")
        logger.error("  sudo apt install libcamera-apps")
        exit(1)
    
    logger.info(f"Using {RPICAM_VID_CMD} for Camera Module 3 streaming")
    logger.info(f"Resolution: {DEFAULT_FEED_CONFIG.frame_width}x{DEFAULT_FEED_CONFIG.frame_height}")
    logger.info(f"Frame Rate: {DEFAULT_FEED_CONFIG.frame_rate} fps")
    logger.info(f"Autofocus: mode={DEFAULT_FEED_CONFIG.autofocus_mode.value}, range={DEFAULT_FEED_CONFIG.autofocus_range.value}")
    
    # Initialize camera
    try:
        proc = get_camera_process()
        if proc is None:
            logger.error("Failed to initialize camera!")
            logger.error("Please check:")
            logger.error("  1. Camera is properly connected")
            logger.error("  2. Camera is enabled (sudo raspi-config)")
            logger.error(f"  3. {RPICAM_VID_CMD} is installed")
            exit(1)
    except CameraInitializationError as e:
        logger.error(f"Camera initialization failed: {e}")
        exit(1)
    
    logger.info(f"Camera feed will be available at: http://localhost:5000")
    logger.info("=" * 60)
    
    try:
        # Run Flask app
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        cleanup_camera()
        cleanup_led()
