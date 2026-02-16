"""
Camera module for Pi camera capture
Handles real-time camera access for the meat quality monitoring system
Supports both V4L2 cameras and Pi Camera V2.1 via rpicam-still
"""

import cv2
import numpy as np
from PIL import Image
import io
import logging
import subprocess
import os
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PiCamera:
    """Wrapper for Pi Camera access using OpenCV (V4L2)"""
    
    def __init__(self, camera_index=0):
        """
        Initialize the camera
        
        Args:
            camera_index: Camera device index (default: 0 for /dev/video0)
        """
        self.camera_index = camera_index
        self.cap = None
        self.is_opened = False
        
    def open(self):
        """Open the camera connection"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if self.cap.isOpened():
                self.is_opened = True
                logger.info(f"Camera opened successfully at index {self.camera_index}")
                return True
            else:
                logger.error(f"Failed to open camera at index {self.camera_index}")
                return False
        except Exception as e:
            logger.error(f"Error opening camera: {e}")
            return False
    
    def capture_frame(self):
        """
        Capture a single frame from the camera
        
        Returns:
            numpy.ndarray: Captured frame in BGR format, or None if failed
        """
        if not self.is_opened:
            if not self.open():
                return None
        
        try:
            ret, frame = self.cap.read()
            if ret:
                return frame
            else:
                logger.warning("Failed to read frame from camera")
                return None
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None
    
    def capture_image_bytes(self, format='jpeg'):
        """
        Capture a frame and convert to bytes
        
        Args:
            format: Image format ('jpeg' or 'png')
            
        Returns:
            bytes: Image data in specified format, or None if failed
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
    
    def capture_pil_image(self):
        """
        Capture a frame and return as PIL Image
        
        Returns:
            PIL.Image: Captured image, or None if failed
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
    
    def close(self):
        """Close the camera connection"""
        if self.cap is not None:
            self.cap.release()
            self.is_opened = False
            logger.info("Camera closed")
    
    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class PiCameraV2:
    """Wrapper for Pi Camera V2.1 using rpicam-still command"""
    
    def __init__(self):
        """Initialize the Pi Camera V2"""
        self.rpicam_cmd = "rpicam-still"
        # Use images folder in project directory
        self.images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
        os.makedirs(self.images_dir, exist_ok=True)
        
    def check_camera_available(self):
        """Check if rpicam-still is available"""
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
    
    def capture_image_bytes(self, format='jpeg', width=1640, height=1232):
        """
        Capture an image using rpicam-still and return as bytes
        
        Args:
            format: Image format ('jpeg' or 'png')
            width: Image width (default: 1640)
            height: Image height (default: 1232)
            
        Returns:
            bytes: Image data in specified format, or None if failed
        """
        if not self.check_camera_available():
            logger.error(f"{self.rpicam_cmd} not found. Please install libcamera-tools.")
            return None
        
        try:
            # Create filename with timestamp for the image
            from datetime import datetime
            ext = 'jpg' if format.lower() == 'jpeg' else format.lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_file = os.path.join(self.images_dir, f"capture_{timestamp}.{ext}")
            
            # Capture image using rpicam-still
            cmd = [
                self.rpicam_cmd,
                "-t", "5000",  # 5 second timeout
                "-o", image_file,
                "--width", str(width),
                "--height", str(height),
                "--nopreview"  # Disable preview
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"rpicam-still failed: {result.stderr}")
                return None
            
            # Read the captured image
            if os.path.exists(image_file):
                with open(image_file, 'rb') as f:
                    image_data = f.read()
                
                logger.info(f"Successfully captured image and saved to {image_file} ({len(image_data)} bytes)")
                return image_data
            else:
                logger.error(f"Image file not created: {image_file}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Camera capture timed out")
            return None
        except Exception as e:
            logger.error(f"Error capturing image with rpicam-still: {e}")
            return None
    
    def capture_pil_image(self, format='jpeg', width=1640, height=1232):
        """
        Capture an image using rpicam-still and return as PIL Image
        
        Args:
            format: Image format ('jpeg' or 'png')
            width: Image width (default: 1640)
            height: Image height (default: 1232)
            
        Returns:
            PIL.Image: Captured image, or None if failed
        """
        image_bytes = self.capture_image_bytes(format=format, width=width, height=height)
        if image_bytes is None:
            return None
        
        try:
            return Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            logger.error(f"Error converting bytes to PIL Image: {e}")
            return None
    
    def capture_frame(self, width=1640, height=1232):
        """
        Capture an image using rpicam-still and return as numpy array (BGR)
        
        Args:
            width: Image width (default: 1640)
            height: Image height (default: 1232)
            
        Returns:
            numpy.ndarray: Captured frame in BGR format, or None if failed
        """
        image_bytes = self.capture_image_bytes(format='jpeg', width=width, height=height)
        if image_bytes is None:
            return None
        
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            # Decode JPEG to BGR format
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            logger.error(f"Error converting bytes to numpy array: {e}")
            return None
    
    def close(self):
        """No resources to close for rpicam-still"""
        pass
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def get_camera_frame(camera_index=0, use_pi_camera_v2=False):
    """
    Convenience function to capture a single frame
    
    Args:
        camera_index: Camera device index (default: 0)
        use_pi_camera_v2: Use Pi Camera V2 via rpicam-still (default: False)
        
    Returns:
        numpy.ndarray: Captured frame in BGR format, or None if failed
    """
    if use_pi_camera_v2:
        with PiCameraV2() as camera:
            return camera.capture_frame()
    else:
        with PiCamera(camera_index) as camera:
            return camera.capture_frame()


def get_camera_image_bytes(camera_index=0, format='jpeg', use_pi_camera_v2=False):
    """
    Convenience function to capture a frame as bytes
    
    Args:
        camera_index: Camera device index (default: 0)
        format: Image format ('jpeg' or 'png')
        use_pi_camera_v2: Use Pi Camera V2 via rpicam-still (default: False)
        
    Returns:
        bytes: Image data in specified format, or None if failed
    """
    if use_pi_camera_v2:
        with PiCameraV2() as camera:
            return camera.capture_image_bytes(format=format)
    else:
        with PiCamera(camera_index) as camera:
            return camera.capture_image_bytes(format=format)


def get_camera_pil_image(camera_index=0, use_pi_camera_v2=False):
    """
    Convenience function to capture a frame as PIL Image
    
    Args:
        camera_index: Camera device index (default: 0)
        use_pi_camera_v2: Use Pi Camera V2 via rpicam-still (default: False)
        
    Returns:
        PIL.Image: Captured image, or None if failed
    """
    if use_pi_camera_v2:
        with PiCameraV2() as camera:
            return camera.capture_pil_image()
    else:
        with PiCamera(camera_index) as camera:
            return camera.capture_pil_image()


def list_available_cameras(max_cameras=10):
    """
    List available camera devices (V4L2 only)
    
    Args:
        max_cameras: Maximum number of cameras to check
        
    Returns:
        list: List of available camera indices
    """
    available = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available


def check_pi_camera_v2_available():
    """
    Check if Pi Camera V2 (rpicam-still) is available
    
    Returns:
        bool: True if rpicam-still is available, False otherwise
    """
    camera = PiCameraV2()
    return camera.check_camera_available()
