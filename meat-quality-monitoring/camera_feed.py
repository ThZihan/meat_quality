#!/usr/bin/env python3
"""
Live Camera Feed Server using Flask
Provides MJPEG streaming from Raspberry Pi Camera Module 3 at localhost/camera_feed
Uses rpicam-vid for streaming (libcamera stack) with autofocus support
"""

import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
from flask import Response
from flask import request
import subprocess
import time
import threading
import signal
import logging
from typing import Optional, Tuple, Generator, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from flask import Flask, render_template, Response, request
from flask import Response
from flask import Flask
    from flask import Response
    from flask import request
import subprocess
import time
import threading
import signal
    import logging
    from typing import Optional, Tuple, Generator, Dict, Any
    from contextlib import contextmanager
    from pathlib import Path

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
    )

    from flask import Response

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
            'cancel'
            
            if trigger_type not in ['start', 'cancel']:
                return {
                    'status': 'error',
                    'message': 'Invalid trigger type. Use "start" or "cancel"'
                }
            
            # Trigger autofocus by restarting camera with trigger
            old_config = DEFAULT_FEED_CONFIG.autofocus_trigger
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
        (800x480 resolution for fast capture)
        
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
        accessed by one process at a time.
        
        Returns:
            Flask Response with JPEG image data or error message
        """
        try:
            # Use default high-resolution capture config
            config = DEFAULT_CAPTURE_CONFIG
            
            logger.info(f"High-res capture: {config.width}x{config.height}, ISO={config.iso}")
            logger.info("Pausing live feed for high-resolution capture...")
            
            # Pause live feed by stopping the camera process
            old_camera_process = None
            with camera_lock:
                global camera_process
                old_camera_process = camera_process
                camera_process = None
            
            # Wait for the old process to fully terminate
            if old_camera_process is not None:
                try:
                    old_camera_process.terminate()
                    old_camera_process.wait(timeout=PROCESS_TERMINATION_TIMEOUT)
                    logger.info("Live feed paused successfully")
                except subprocess.TimeoutExpired:
                    logger.warning("Camera process did not terminate gracefully, killing")
                    old_camera_process.kill()
                    old_camera_process.wait()
            
            # Small delay to ensure camera is fully released
            time.sleep(0.5)
            
            # Build rpicam-still command
            cmd = [
                RPICAM_STILL_CMD,
                "-t", str(config.timeout),
                "-o", "-",  # Output to stdout
                "--width", str(config.width),
                "--height", str(config.height),
                "--nopreview",  # Disable preview
                "--quality", "95",  # High quality JPEG
                "--encoding", "jpg",  # Use JPEG encoding
            ]
            
            # Add ISO setting for low light sensitivity control
            if config.iso > 0:
                cmd.extend(["--immediate", "--gain", str(config.iso // 100)])  # Map ISO to gain
            
            # Add autofocus options for Camera Module 3
            cmd.extend(["--autofocus-mode", config.autofocus_mode.value])
            cmd.extend(["--autofocus-range", config.autofocus_range.value])
            cmd.extend(["--autofocus-speed", config.autofocus_speed.value])
            
            if config.autofocus_trigger:
                cmd.extend(["--autofocus-trigger", config.autofocus_trigger])
            
            logger.debug(f"High-res capture command: {' '.join(cmd)}")
            
            # Execute capture command
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=config.timeout / 1000 + 5  # Add buffer to timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                logger.error(f"High-res capture failed: {error_msg}")
                # Restart live feed even on failure
                try:
                    get_camera_process()
                    logger.info("Live feed restarted after failed capture")
                except Exception as e:
                    logger.error(f"Failed to restart live feed: {e}")
                return Response(
                    {'status': 'error', 'message': f'Capture failed: {error_msg}'},
                    status=500
                )
            
            # Get captured image bytes
            image_bytes = result.stdout
            
            if not image_bytes or len(image_bytes) < 1000:
                logger.error("High-res capture returned empty or invalid image")
                # Restart live feed even on failure
                try:
                    get_camera_process()
                    logger.info("Live feed restarted after failed capture")
                except Exception as e:
                    logger.error(f"Failed to restart live feed: {e}")
                return Response(
                    {'status': 'error', 'message': 'Capture returned empty or invalid image'},
                    status=500
                )
            
            logger.info(f"High-res capture successful: {len(image_bytes)} bytes")
            logger.info("Restarting live feed...")
            
            # Restart live feed
            try:
                get_camera_process()
                logger.info("Live feed restarted successfully")
            except Exception as e:
                logger.error(f"Failed to restart live feed: {e}")
            
            # Return the captured image
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
            # Try to restart live feed
            try:
                get_camera_process()
                logger.info("Live feed restarted after timeout")
            except Exception as e:
                logger.error(f"Failed to restart live feed: {e}")
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
