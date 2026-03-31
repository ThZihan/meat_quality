"""
Camera module for Raspberry Pi Camera Module 3
Handles real-time camera access for the meat quality monitoring system
Supports both V4L2 cameras and Camera Module 3 via rpicam-still with autofocus
"""

import cv2
import numpy as np
from PIL import Image
import io
import logging
import subprocess
import os
from typing import Optional, Tuple, List, Dict, Any
from contextlib import contextmanager

# Import camera configuration
from camera_config import (
    CameraCaptureConfig,
    DEFAULT_CAPTURE_CONFIG,
    RPICAM_STILL_CMD,
    CAMERA_CAPTURE_TIMEOUT,
    AutofocusMode,
    AutofocusRange,
    AutofocusSpeed,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CameraError(Exception):
    """Base exception for camera-related errors"""
    pass


class CameraInitializationError(CameraError):
    """Exception raised when camera initialization fails"""
    pass


class CameraCaptureError(CameraError):
    """Exception raised when camera capture fails"""
    pass


class V4L2Camera:
    """Wrapper for V4L2 camera access using OpenCV"""
    
    def __init__(self, camera_index: int = 0):
        """
        Initialize the V4L2 camera
        
        Args:
            camera_index: Camera device index (default: 0 for /dev/video0)
        """
        self.camera_index: int = camera_index
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened: bool = False
        
    def open(self) -> bool:
        """
        Open the camera connection
        
        Returns:
            True if camera opened successfully, False otherwise
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if self.cap.isOpened():
                self.is_opened = True
                logger.info(f"V4L2 camera opened successfully at index {self.camera_index}")
                return True
            else:
                logger.error(f"Failed to open V4L2 camera at index {self.camera_index}")
                return False
        except Exception as e:
            logger.error(f"Error opening V4L2 camera: {e}")
            raise CameraInitializationError(f"Failed to open camera: {e}")
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from the camera
        
        Returns:
            Captured frame in BGR format as numpy array, or None if failed
        """
        if not self.is_opened:
            if not self.open():
                return None
        
        try:
            ret, frame = self.cap.read()
            if ret:
                return frame
            else:
                logger.warning("Failed to read frame from V4L2 camera")
                return None
        except Exception as e:
            logger.error(f"Error capturing frame from V4L2 camera: {e}")
            return None
    
    def capture_image_bytes(self, format: str = 'jpeg') -> Optional[bytes]:
        """
        Capture a frame and convert to bytes
        
        Args:
            format: Image format ('jpeg' or 'png')
            
        Returns:
            Image data in specified format as bytes, or None if failed
        """
        frame = self.capture_frame()
        if frame is None:
            return None
        
        try:
            # Convert BGR to RGB for PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(frame_rgb)
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format=format.upper())
            img_byte_arr.seek(0)
            
            return img_byte_arr.getvalue()
        except Exception as e:
            logger.error(f"Error converting frame to bytes: {e}")
            return None
    
    def capture_pil_image(self) -> Optional[Image.Image]:
        """
        Capture a frame and return as PIL Image
        
        Returns:
            Captured image as PIL Image, or None if failed
        """
        frame = self.capture_frame()
        if frame is None:
            return None
        
        try:
            # Convert BGR to RGB for PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(frame_rgb)
        except Exception as e:
            logger.error(f"Error converting frame to PIL Image: {e}")
            return None
    
    def close(self) -> None:
        """Close the camera connection"""
        if self.cap is not None:
            self.cap.release()
            self.is_opened = False
            logger.info("V4L2 camera closed")
    
    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class CameraModule3:
    """Wrapper for Raspberry Pi Camera Module 3 using rpicam-still command"""
    
    def __init__(self, config: Optional[CameraCaptureConfig] = None):
        """
        Initialize the Camera Module 3
        
        Args:
            config: Camera configuration object (uses defaults if not provided)
        """
        self.rpicam_cmd: str = RPICAM_STILL_CMD
        self.config: CameraCaptureConfig = config or DEFAULT_CAPTURE_CONFIG
        # Use images folder in project directory
        self.images_dir: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "images"
        )
        os.makedirs(self.images_dir, exist_ok=True)
        logger.info(f"Camera Module 3 initialized with config: {self.config.width}x{self.config.height}")
        
    def check_camera_available(self) -> bool:
        """
        Check if rpicam-still is available
        
        Returns:
            True if rpicam-still is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["which", self.rpicam_cmd],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking camera availability: {e}")
            return False
    
    def capture_image_bytes(self) -> Optional[bytes]:
        """
        Capture an image using rpicam-still and return as bytes
        
        Returns:
            Image data in specified format as bytes, or None if failed
            
        Raises:
            CameraCaptureError: If image capture fails
        """
        if not self.check_camera_available():
            logger.error(f"{self.rpicam_cmd} not found. Please install libcamera-tools.")
            raise CameraCaptureError(f"{self.rpicam_cmd} not found. Please install libcamera-tools.")
        
        try:
            # Create filename with timestamp for the image
            from datetime import datetime
            ext = 'jpg' if self.config.format.lower() == 'jpeg' else self.config.format.lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_file = os.path.join(self.images_dir, f"capture_{timestamp}.{ext}")
            
            # Capture image using rpicam-still
            cmd = self.config.get_rpicam_args(image_file)
            
            logger.debug(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CAMERA_CAPTURE_TIMEOUT  # Timeout in seconds
            )
            
            if result.returncode != 0:
                logger.error(f"rpicam-still failed: {result.stderr}")
                raise CameraCaptureError(f"rpicam-still failed: {result.stderr}")
            
            # Read the captured image
            if os.path.exists(image_file):
                with open(image_file, 'rb') as f:
                    image_data = f.read()
                
                logger.info(f"Successfully captured image and saved to {image_file} ({len(image_data)} bytes)")
                return image_data
            else:
                logger.error(f"Image file not created: {image_file}")
                raise CameraCaptureError(f"Image file not created: {image_file}")
                
        except subprocess.TimeoutExpired:
            logger.error("Camera capture timed out")
            raise CameraCaptureError("Camera capture timed out")
        except CameraCaptureError:
            raise
        except Exception as e:
            logger.error(f"Error capturing image with rpicam-still: {e}")
            raise CameraCaptureError(f"Error capturing image: {e}")
    
    def capture_pil_image(self) -> Optional[Image.Image]:
        """
        Capture an image using rpicam-still and return as PIL Image
        
        Returns:
            Captured image as PIL Image, or None if failed
        """
        try:
            image_bytes = self.capture_image_bytes()
            if image_bytes is None:
                return None
            
            return Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            logger.error(f"Error converting bytes to PIL Image: {e}")
            return None
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture an image using rpicam-still and return as numpy array (BGR)
        
        Returns:
            Captured frame in BGR format as numpy array, or None if failed
        """
        try:
            image_bytes = self.capture_image_bytes()
            if image_bytes is None:
                return None
            
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            # Decode JPEG to BGR format
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            logger.error(f"Error converting bytes to numpy array: {e}")
            return None
    
    def trigger_autofocus(self, trigger_type: str = 'start') -> bool:
        """
        Trigger autofocus on Camera Module 3
        
        Args:
            trigger_type: Type of trigger ('start' or 'cancel')
            
        Returns:
            True if trigger was successful, False otherwise
        """
        try:
            if trigger_type not in ['start', 'cancel']:
                logger.error(f"Invalid trigger type: {trigger_type}")
                return False
            
            # Trigger autofocus by capturing with trigger
            old_trigger = self.config.autofocus_trigger
            self.config.autofocus_trigger = trigger_type
            
            try:
                self.capture_image_bytes()
                return True
            finally:
                self.config.autofocus_trigger = old_trigger
                
        except Exception as e:
            logger.error(f"Error triggering autofocus: {e}")
            return False
    
    def close(self) -> None:
        """No resources to close for rpicam-still"""
        pass
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def get_camera_frame(camera_index: int = 0, use_module3: bool = False,
                     config: Optional[CameraCaptureConfig] = None) -> Optional[np.ndarray]:
    """
    Convenience function to capture a single frame
    
    Args:
        camera_index: Camera device index for V4L2 (default: 0)
        use_module3: Use Camera Module 3 via rpicam-still (default: False)
        config: Configuration for Camera Module 3 (uses defaults if not provided)
        
    Returns:
        Captured frame in BGR format as numpy array, or None if failed
    """
    if use_module3:
        with CameraModule3(config) as camera:
            return camera.capture_frame()
    else:
        with V4L2Camera(camera_index) as camera:
            return camera.capture_frame()


def get_camera_image_bytes(camera_index: int = 0, format: str = 'jpeg',
                           use_module3: bool = False,
                           config: Optional[CameraCaptureConfig] = None) -> Optional[bytes]:
    """
    Convenience function to capture a frame as bytes
    
    Args:
        camera_index: Camera device index for V4L2 (default: 0)
        format: Image format ('jpeg' or 'png')
        use_module3: Use Camera Module 3 via rpicam-still (default: False)
        config: Configuration for Camera Module 3 (uses defaults if not provided)
        
    Returns:
        Image data in specified format as bytes, or None if failed
    """
    if use_module3:
        camera_config = config or CameraCaptureConfig(format=format)
        with CameraModule3(camera_config) as camera:
            return camera.capture_image_bytes()
    else:
        with V4L2Camera(camera_index) as camera:
            return camera.capture_image_bytes(format=format)


def get_camera_pil_image(camera_index: int = 0, use_module3: bool = False,
                         config: Optional[CameraCaptureConfig] = None) -> Optional[Image.Image]:
    """
    Convenience function to capture a frame as PIL Image
    
    Args:
        camera_index: Camera device index for V4L2 (default: 0)
        use_module3: Use Camera Module 3 via rpicam-still (default: False)
        config: Configuration for Camera Module 3 (uses defaults if not provided)
        
    Returns:
        Captured image as PIL Image, or None if failed
    """
    if use_module3:
        with CameraModule3(config) as camera:
            return camera.capture_pil_image()
    else:
        with V4L2Camera(camera_index) as camera:
            return camera.capture_pil_image()


def list_available_cameras(max_cameras: int = 10) -> List[int]:
    """
    List available V4L2 camera devices
    
    Args:
        max_cameras: Maximum number of cameras to check
        
    Returns:
        List of available camera indices
    """
    available = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available


def check_module3_available() -> bool:
    """
    Check if Camera Module 3 (rpicam-still) is available
    
    Returns:
        True if rpicam-still is available, False otherwise
    """
    camera = CameraModule3()
    return camera.check_camera_available()


# Backward compatibility alias for legacy v2.1 reference
# This function is kept for compatibility with existing code
def check_pi_camera_v2_available() -> bool:
    """
    Check if Camera Module 3 (rpicam-still) is available
    
    Note: This is a backward compatibility alias. The function name
    references the legacy v2.1 camera, but it actually checks for
    Camera Module 3 availability using the modern libcamera stack.
    
    Returns:
        True if rpicam-still is available, False otherwise
    """
    logger.info("check_pi_camera_v2_available() called - using Camera Module 3 (libcamera)")
    return check_module3_available()


# Backward compatibility wrapper for get_camera_image_bytes
def get_camera_image_bytes_legacy(camera_index: int = 0, use_pi_camera_v2: bool = False,
                                   format: str = 'jpeg') -> Optional[bytes]:
    """
    Legacy wrapper for get_camera_image_bytes with v2.1 parameter naming
    
    Note: This is a backward compatibility wrapper. The parameter name
    references the legacy v2.1 camera, but it actually uses Camera Module 3.
    
    Args:
        camera_index: Camera device index for V4L2 (default: 0)
        use_pi_camera_v2: Use Camera Module 3 via rpicam-still (default: False)
        format: Image format ('jpeg' or 'png')
        
    Returns:
        Image data in specified format as bytes, or None if failed
    """
    if use_pi_camera_v2:
        logger.info("get_camera_image_bytes_legacy() - using Camera Module 3 (libcamera)")
        return get_camera_image_bytes(camera_index=camera_index, format=format, use_module3=True)
    else:
        return get_camera_image_bytes(camera_index=camera_index, format=format, use_module3=False)
