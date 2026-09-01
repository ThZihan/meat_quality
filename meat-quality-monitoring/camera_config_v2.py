"""
Camera Configuration Module - Raspberry Pi Camera Module v2.1 (IMX219)

Dedicated configuration for the Pi Camera v2.1 sensor:
- Sony IMX219 8MP sensor
- Maximum still resolution: 3280x2464
- FIXED FOCUS lens (no autofocus hardware - no rpicam AF flags allowed)
- 1080p30 max video, full-FOV video modes: 1640x1232@30, 3280x2464@15

This module mirrors camera_config.py but strips every Camera Module 3
autofocus option, which rpicam-vid/rpicam-still reject on IMX219 with:
    "the autofocus-mode option is not supported"
"""

import os
import logging
from dataclasses import dataclass

# Re-use LED / light-detection constants from the shared module so the
# illumination logic behaves identically for both camera generations.
from camera_config import (
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

# Configure logging
logger = logging.getLogger(__name__)


# Sensor limits for Pi Camera Module v2.1 (IMX219)
IMX219_MAX_WIDTH = 3280
IMX219_MAX_HEIGHT = 2464
IMX219_MAX_VIDEO_FPS = 30          # at <=1080p; 3280x2464 tops out at ~15fps

# Resolution presets (v2.1 compatible)
RESOLUTION_PRESETS = {
    'vga': {'width': 640, 'height': 480, 'name': 'VGA (640x480)'},
    'wvga': {'width': 800, 'height': 480, 'name': 'WVGA (800x480)'},
    'hd': {'width': 1280, 'height': 720, 'name': 'HD (1280x720)'},
    'fhd': {'width': 1920, 'height': 1080, 'name': 'Full HD (1920x1080)'},
    '2k': {'width': 2560, 'height': 1440, 'name': '2K (2560x1440)'},
    'max': {'width': 3280, 'height': 2464, 'name': 'Camera v2.1 Max (3280x2464)'},
}

# FPS presets
FPS_PRESETS = {
    '15': {'fps': 15, 'name': '15 FPS (Low Bandwidth)'},
    '30': {'fps': 30, 'name': '30 FPS (Standard)'},
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
CAMERA_CAPTURE_TIMEOUT = 10  # seconds
PROCESS_TERMINATION_TIMEOUT = 5  # seconds

# Error thresholds
MAX_CONSECUTIVE_ERRORS = 5

# JPEG markers
JPEG_START_MARKER = b'\xff\xd8'
JPEG_END_MARKER = b'\xff\xd9'

# HTTP multipart boundary
MULTIPART_BOUNDARY = b'frame'

# Human-readable camera identity used by the feed server / status endpoint
CAMERA_MODEL_NAME = "Raspberry Pi Camera Module v2.1 (IMX219, fixed focus)"


@dataclass
class CameraFeedConfigV2:
    """
    Configuration for camera feed streaming with Pi Camera v2.1

    The v2.1 has a fixed-focus lens: there is NO autofocus configuration.
    """

    frame_rate: int = 30
    frame_width: int = 800
    frame_height: int = 480
    bitrate: int = 5000000  # 5 Mbps
    jpeg_quality: int = 85
    camera_device: str = DEFAULT_CAMERA_DEVICE

    def __post_init__(self):
        """Validate configuration values after initialization"""
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError(f"jpeg_quality must be between 1 and 100, got {self.jpeg_quality}")
        if not 1 <= self.frame_rate <= IMX219_MAX_VIDEO_FPS:
            raise ValueError(
                f"frame_rate must be between 1 and {IMX219_MAX_VIDEO_FPS} for IMX219, got {self.frame_rate}"
            )
        if not 64 <= self.frame_width <= IMX219_MAX_WIDTH:
            raise ValueError(
                f"frame_width must be between 64 and {IMX219_MAX_WIDTH} for IMX219, got {self.frame_width}"
            )
        if not 64 <= self.frame_height <= IMX219_MAX_HEIGHT:
            raise ValueError(
                f"frame_height must be between 64 and {IMX219_MAX_HEIGHT} for IMX219, got {self.frame_height}"
            )

    @classmethod
    def from_env(cls) -> 'CameraFeedConfigV2':
        """
        Create configuration from environment variables

        Returns:
            CameraFeedConfigV2 instance with values from environment
        """
        try:
            frame_rate = int(os.getenv('CAMERA_FRAME_RATE', 30))
            frame_width = int(os.getenv('CAMERA_WIDTH', 800))
            frame_height = int(os.getenv('CAMERA_HEIGHT', 480))
            jpeg_quality = int(os.getenv('CAMERA_JPEG_QUALITY', 85))
            bitrate = int(os.getenv('CAMERA_BITRATE', 5000000))
            camera_device = os.getenv('CAMERA_DEVICE', DEFAULT_CAMERA_DEVICE)

            logger.info(f"Loaded v2.1 camera config from environment: {frame_width}x{frame_height} @ {frame_rate}fps")

            return cls(
                frame_rate=frame_rate,
                frame_width=frame_width,
                frame_height=frame_height,
                jpeg_quality=jpeg_quality,
                bitrate=bitrate,
                camera_device=camera_device,
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to load config from environment, using defaults: {e}")
            return cls()

    def get_rpicam_args(self) -> list[str]:
        """
        Generate rpicam-vid command line arguments from config

        NOTE: No autofocus flags - the IMX219 has a fixed-focus lens and
        rpicam-vid aborts when Camera Module 3 AF options are supplied.

        Returns:
            List of command line arguments for rpicam-vid
        """
        return [
            RPICAM_VID_CMD,
            "-o", "-",  # Output to stdout
            "--width", str(self.frame_width),
            "--height", str(self.frame_height),
            "--framerate", str(self.frame_rate),
            "--codec", "mjpeg",
            "--quality", str(self.jpeg_quality),
            "--timeout", "0",  # No timeout
            "--nopreview",  # Disable preview window to prevent camera conflict
        ]


@dataclass
class CameraCaptureConfigV2:
    """
    Configuration for camera image capture with Pi Camera v2.1

    Defaults to the v2.1 native full resolution (3280x2464). Fixed focus,
    so no autofocus settings exist.
    """

    width: int = IMX219_MAX_WIDTH
    height: int = IMX219_MAX_HEIGHT
    format: str = 'png'
    timeout: int = 5000  # milliseconds
    iso: int = 0  # 0 = auto gain (AEC); >0 locks analog gain

    def __post_init__(self):
        """Validate configuration values after initialization"""
        if self.format.lower() not in ['jpeg', 'png']:
            raise ValueError(f"format must be 'jpeg' or 'png', got {self.format}")
        if not 64 <= self.width <= IMX219_MAX_WIDTH:
            raise ValueError(
                f"width must be between 64 and {IMX219_MAX_WIDTH} for IMX219, got {self.width}"
            )
        if not 64 <= self.height <= IMX219_MAX_HEIGHT:
            raise ValueError(
                f"height must be between 64 and {IMX219_MAX_HEIGHT} for IMX219, got {self.height}"
            )
        if not 100 <= self.timeout <= 60000:
            raise ValueError(f"timeout must be between 100 and 60000, got {self.timeout}")
        if not 0 <= self.iso <= 1600:
            raise ValueError(f"iso must be between 0 (auto) and 1600, got {self.iso}")

    @classmethod
    def from_env(cls) -> 'CameraCaptureConfigV2':
        """
        Create configuration from environment variables

        Returns:
            CameraCaptureConfigV2 instance with values from environment
        """
        try:
            width = int(os.getenv('CAMERA_CAPTURE_WIDTH', IMX219_MAX_WIDTH))
            height = int(os.getenv('CAMERA_CAPTURE_HEIGHT', IMX219_MAX_HEIGHT))
            format = os.getenv('CAMERA_CAPTURE_FORMAT', 'png')
            timeout = int(os.getenv('CAMERA_CAPTURE_TIMEOUT', 5000))
            iso = int(os.getenv('CAMERA_CAPTURE_ISO', 0))

            logger.info(f"Loaded v2.1 capture config from environment: {width}x{height}, ISO={iso}, format={format}")

            return cls(
                width=width,
                height=height,
                format=format,
                timeout=timeout,
                iso=iso,
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to load config from environment, using defaults: {e}")
            return cls()

    def get_rpicam_args(self, output_file: str) -> list[str]:
        """
        Generate rpicam-still command line arguments from config

        NOTE: No autofocus flags - IMX219 is fixed focus.

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

        # Optional manual gain (ISO > 0). --immediate removed: it skipped AEC
        # settling and caused dark/black frames in dim scenes.
        if self.iso > 0:
            args.extend(["--gain", str(max(1, self.iso // 100))])  # Map ISO to gain

        return args


# Default configurations
DEFAULT_FEED_CONFIG = CameraFeedConfigV2()
DEFAULT_CAPTURE_CONFIG = CameraCaptureConfigV2()
