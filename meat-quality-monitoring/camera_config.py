"""
Camera Configuration Module
Handles camera settings via environment variables and provides constants
for the meat quality monitoring system.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class AutofocusMode(Enum):
    """Autofocus mode options for Camera Module 3"""
    AUTO = "auto"
    MANUAL = "manual"
    CONTINUOUS = "continuous"


class AutofocusRange(Enum):
    """Autofocus range options for Camera Module 3"""
    NORMAL = "normal"
    MACRO = "macro"
    FULL = "full"


class AutofocusSpeed(Enum):
    """Autofocus speed options for Camera Module 3"""
    NORMAL = "normal"
    FAST = "fast"


# Resolution presets
RESOLUTION_PRESETS = {
    'vga': {'width': 640, 'height': 480, 'name': 'VGA (640x480)'},
    'wvga': {'width': 800, 'height': 480, 'name': 'WVGA (800x480)'},
    'hd': {'width': 1280, 'height': 720, 'name': 'HD (1280x720)'},
    'fhd': {'width': 1920, 'height': 1080, 'name': 'Full HD (1920x1080)'},
    '2k': {'width': 2560, 'height': 1440, 'name': '2K (2560x1440)'},
    'max': {'width': 3280, 'height': 2464, 'name': 'Camera Module 3 Max (3280x2464)'},
}

# FPS presets
FPS_PRESETS = {
    '15': {'fps': 15, 'name': '15 FPS (Low Bandwidth)'},
    '30': {'fps': 30, 'name': '30 FPS (Standard)'},
    '60': {'fps': 60, 'name': '60 FPS (Smooth)'},
    '90': {'fps': 90, 'name': '90 FPS (High Performance)'},
}

# Camera commands
RPICAM_VID_CMD = "rpicam-vid"
RPICAM_STILL_CMD = "rpicam-still"

# Default camera device
DEFAULT_CAMERA_DEVICE = "/dev/video0"

# Buffer size limits
MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB
BUFFER_READ_SIZE = 4096  # 4 KB

# Timeout values
CAMERA_INIT_TIMEOUT = 2  # seconds
CAMERA_CAPTURE_TIMEOUT = 10  # seconds
PROCESS_TERMINATION_TIMEOUT = 5  # seconds

# Error thresholds
MAX_CONSECUTIVE_ERRORS = 5

# JPEG markers
JPEG_START_MARKER = b'\xff\xd8'
JPEG_END_MARKER = b'\xff\xd9'

# HTTP multipart boundary
MULTIPART_BOUNDARY = b'frame'


@dataclass
class CameraFeedConfig:
    """
    Configuration for camera feed streaming
    
    Attributes:
        frame_rate: Frames per second for streaming
        frame_width: Width of video frames
        frame_height: Height of video frames
        bitrate: Video bitrate in bits per second
        jpeg_quality: JPEG quality (1-100)
        camera_device: Camera device path
        autofocus_mode: Autofocus mode setting
        autofocus_range: Autofocus range setting
        autofocus_speed: Autofocus speed setting
        autofocus_trigger: Autofocus trigger command
    """
    frame_rate: int = 30
    frame_width: int = 800
    frame_height: int = 480
    bitrate: int = 5000000  # 5 Mbps
    jpeg_quality: int = 85
    camera_device: str = DEFAULT_CAMERA_DEVICE
    
    # Autofocus configuration for Camera Module 3
    autofocus_mode: AutofocusMode = AutofocusMode.CONTINUOUS
    autofocus_range: AutofocusRange = AutofocusRange.NORMAL
    autofocus_speed: AutofocusSpeed = AutofocusSpeed.NORMAL
    autofocus_trigger: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration values after initialization"""
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError(f"jpeg_quality must be between 1 and 100, got {self.jpeg_quality}")
        if not 1 <= self.frame_rate <= 120:
            raise ValueError(f"frame_rate must be between 1 and 120, got {self.frame_rate}")
        if not 64 <= self.frame_width <= 4608:
            raise ValueError(f"frame_width must be between 64 and 4608, got {self.frame_width}")
        if not 64 <= self.frame_height <= 2592:
            raise ValueError(f"frame_height must be between 64 and 2592, got {self.frame_height}")
    
    @classmethod
    def from_env(cls) -> 'CameraFeedConfig':
        """
        Create configuration from environment variables
        
        Returns:
            CameraFeedConfig instance with values from environment
        """
        try:
            frame_rate = int(os.getenv('CAMERA_FRAME_RATE', 30))
            frame_width = int(os.getenv('CAMERA_WIDTH', 800))
            frame_height = int(os.getenv('CAMERA_HEIGHT', 480))
            jpeg_quality = int(os.getenv('CAMERA_JPEG_QUALITY', 85))
            bitrate = int(os.getenv('CAMERA_BITRATE', 5000000))
            camera_device = os.getenv('CAMERA_DEVICE', DEFAULT_CAMERA_DEVICE)
            
            # Parse autofocus mode
            autofocus_mode_str = os.getenv('CAMERA_AUTOFOCUS_MODE', 'continuous')
            autofocus_mode = AutofocusMode(autofocus_mode_str)
            
            # Parse autofocus range
            autofocus_range_str = os.getenv('CAMERA_AUTOFOCUS_RANGE', 'normal')
            autofocus_range = AutofocusRange(autofocus_range_str)
            
            # Parse autofocus speed
            autofocus_speed_str = os.getenv('CAMERA_AUTOFOCUS_SPEED', 'normal')
            autofocus_speed = AutofocusSpeed(autofocus_speed_str)
            
            logger.info(f"Loaded camera config from environment: {frame_width}x{frame_height} @ {frame_rate}fps")
            
            return cls(
                frame_rate=frame_rate,
                frame_width=frame_width,
                frame_height=frame_height,
                jpeg_quality=jpeg_quality,
                bitrate=bitrate,
                camera_device=camera_device,
                autofocus_mode=autofocus_mode,
                autofocus_range=autofocus_range,
                autofocus_speed=autofocus_speed
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to load config from environment, using defaults: {e}")
            return cls()
    
    def get_rpicam_args(self) -> list[str]:
        """
        Generate rpicam-vid command line arguments from config
        
        Returns:
            List of command line arguments for rpicam-vid
        """
        args = [
            RPICAM_VID_CMD,
            "-o", "-",  # Output to stdout
            "--width", str(self.frame_width),
            "--height", str(self.frame_height),
            "--framerate", str(self.frame_rate),
            "--codec", "mjpeg",
            "--quality", str(self.jpeg_quality),
            "--timeout", "0",  # No timeout
            "--nopreview"  # Disable preview window to prevent camera conflict
        ]
        
        # Add autofocus options for Camera Module 3
        args.extend(["--autofocus-mode", self.autofocus_mode.value])
        args.extend(["--autofocus-range", self.autofocus_range.value])
        args.extend(["--autofocus-speed", self.autofocus_speed.value])
        
        if self.autofocus_trigger:
            args.extend(["--autofocus-trigger", self.autofocus_trigger])
        
        return args


@dataclass
class CameraCaptureConfig:
    """
    Configuration for camera image capture
    
    Attributes:
        width: Image width in pixels
        height: Image height in pixels
        format: Image format ('jpeg' or 'png')
        timeout: Capture timeout in milliseconds
        iso: ISO sensitivity (lower = less noise, requires more light)
        autofocus_mode: Autofocus mode setting
        autofocus_range: Autofocus range setting
        autofocus_speed: Autofocus speed setting
        autofocus_trigger: Autofocus trigger command
    """
    width: int = 4608
    height: int = 2592
    format: str = 'png'
    timeout: int = 5000  # milliseconds
    iso: int = 0  # 0 = auto gain (AEC controls gain+shutter); >0 locks analog gain
    autofocus_mode: AutofocusMode = AutofocusMode.CONTINUOUS
    autofocus_range: AutofocusRange = AutofocusRange.NORMAL
    autofocus_speed: AutofocusSpeed = AutofocusSpeed.NORMAL
    autofocus_trigger: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration values after initialization"""
        if self.format.lower() not in ['jpeg', 'png']:
            raise ValueError(f"format must be 'jpeg' or 'png', got {self.format}")
        if not 64 <= self.width <= 4608:
            raise ValueError(f"width must be between 64 and 4608, got {self.width}")
        if not 64 <= self.height <= 2592:
            raise ValueError(f"height must be between 64 and 2592, got {self.height}")
        if not 100 <= self.timeout <= 60000:
            raise ValueError(f"timeout must be between 100 and 60000, got {self.timeout}")
        if not 0 <= self.iso <= 1600:
            raise ValueError(f"iso must be between 0 (auto) and 1600, got {self.iso}")
    
    @classmethod
    def from_env(cls) -> 'CameraCaptureConfig':
        """
        Create configuration from environment variables
        
        Returns:
            CameraCaptureConfig instance with values from environment
        """
        try:
            width = int(os.getenv('CAMERA_CAPTURE_WIDTH', 4608))
            height = int(os.getenv('CAMERA_CAPTURE_HEIGHT', 2592))
            format = os.getenv('CAMERA_CAPTURE_FORMAT', 'png')
            timeout = int(os.getenv('CAMERA_CAPTURE_TIMEOUT', 5000))
            iso = int(os.getenv('CAMERA_CAPTURE_ISO', 0))
            
            # Parse autofocus mode
            autofocus_mode_str = os.getenv('CAMERA_AUTOFOCUS_MODE', 'continuous')
            autofocus_mode = AutofocusMode(autofocus_mode_str)
            
            # Parse autofocus range
            autofocus_range_str = os.getenv('CAMERA_AUTOFOCUS_RANGE', 'normal')
            autofocus_range = AutofocusRange(autofocus_range_str)
            
            # Parse autofocus speed
            autofocus_speed_str = os.getenv('CAMERA_AUTOFOCUS_SPEED', 'normal')
            autofocus_speed = AutofocusSpeed(autofocus_speed_str)
            
            logger.info(f"Loaded capture config from environment: {width}x{height}, ISO={iso}, format={format}")
            
            return cls(
                width=width,
                height=height,
                format=format,
                timeout=timeout,
                iso=iso,
                autofocus_mode=autofocus_mode,
                autofocus_range=autofocus_range,
                autofocus_speed=autofocus_speed
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to load capture config from environment, using defaults: {e}")
            return cls()
    
    def get_rpicam_args(self, output_file: str) -> list[str]:
        """
        Generate rpicam-still command line arguments from config
        
        Args:
            output_file: Path to save the captured image
            
        Returns:
            List of command line arguments for rpicam-still
        """
        args = [
            RPICAM_STILL_CMD,
            "-t", str(self.timeout),
            "-o", output_file,
            "--width", str(self.width),
            "--height", str(self.height),
            "--nopreview",  # Disable preview
        ]
        
        # Optional manual gain (ISO > 0). Default 0 keeps AEC free to raise
        # gain in dim light; locking gain at 1 produced black frames. The
        # --immediate flag is gone: AEC/AWB need the settle time to converge.
        if self.iso > 0:
            args.extend(["--gain", str(max(1, self.iso // 100))])  # Map ISO to gain
        
        # Add autofocus options for Camera Module 3
        args.extend(["--autofocus-mode", self.autofocus_mode.value])
        args.extend(["--autofocus-range", self.autofocus_range.value])
        args.extend(["--autofocus-speed", self.autofocus_speed.value])
        
        if self.autofocus_trigger:
            args.extend(["--autofocus-trigger", self.autofocus_trigger])
        
        return args


# ---------------------------------------------------------------------------
# LED / Light-Detection Configuration
# ---------------------------------------------------------------------------

# GPIO pin connected to the LED driver (BCM numbering).
LED_GPIO_PIN: int = int(os.getenv('LED_GPIO_PIN', 18))

# PWM frequency in Hz.
LED_PWM_FREQUENCY: int = int(os.getenv('LED_PWM_FREQUENCY', 1000))

# Brightness thresholds (0-255 scale, mean of grayscale frame).
#
# Normal ambient light reads around 130.  The LED should begin ramping up
# when brightness drops below 115 and be completely off at 120 and above.
# A small hysteresis band (115-120) prevents flicker at the transition
# boundary.
LED_DARK_THRESHOLD: float = float(os.getenv('LED_DARK_THRESHOLD', 115.0))
LED_BRIGHT_THRESHOLD: float = float(os.getenv('LED_BRIGHT_THRESHOLD', 120.0))

# PWM duty-cycle limits.
#
# Keep a visible minimum floor once the darkness threshold is crossed so the
# live-feed response is perceptible on hardware that barely glows at very low
# PWM duty cycles.
LED_MIN_PWM: float = float(os.getenv('LED_MIN_PWM', 0.35))
LED_MAX_PWM: float = float(os.getenv('LED_MAX_PWM', 1.0))

# Anti-flicker throttling.
LED_THROTTLE_INTERVAL: float = float(os.getenv('LED_THROTTLE_INTERVAL', 0.5))
LED_PWM_STEP: float = float(os.getenv('LED_PWM_STEP', 0.05))

# How often (seconds) the live-feed monitor analyses a frame for brightness.
LED_MONITOR_INTERVAL: float = float(os.getenv('LED_MONITOR_INTERVAL', 1.0))
LED_ANALYSIS_INTERVAL: float = float(os.getenv('LED_ANALYSIS_INTERVAL', LED_MONITOR_INTERVAL))

# Preliminary low-cost capture sizing for light analysis before the final shot.
LED_DUMMY_CAPTURE_WIDTH: int = int(os.getenv('LED_DUMMY_CAPTURE_WIDTH', 640))
LED_DUMMY_CAPTURE_HEIGHT: int = int(os.getenv('LED_DUMMY_CAPTURE_HEIGHT', 480))
LED_DUMMY_CAPTURE_QUALITY: int = int(os.getenv('LED_DUMMY_CAPTURE_QUALITY', 80))
LED_DUMMY_CAPTURE_TIMEOUT_MS: int = int(os.getenv('LED_DUMMY_CAPTURE_TIMEOUT_MS', 900))

# Seconds to wait after setting PWM before the final high-res capture
# so the LED illumination can stabilise.
LED_SETTLE_TIME: float = float(os.getenv('LED_SETTLE_TIME', 0.3))


# Default configurations
DEFAULT_FEED_CONFIG = CameraFeedConfig()
DEFAULT_CAPTURE_CONFIG = CameraCaptureConfig()
