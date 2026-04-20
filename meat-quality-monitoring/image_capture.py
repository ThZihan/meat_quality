#!/usr/bin/env python3
"""
Image Capture Module for Meat Quality Monitoring System
Handles capturing and saving images from the camera feed server
Provides extensible API for future integrations
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImageCaptureError(Exception):
    """Exception raised when image capture fails"""
    pass


class ImageSaveError(Exception):
    """Exception raised when saving image fails"""
    pass


class ImageCapture:
    """
    Handles image capture and saving operations
    Provides extensible API for future integrations
    """
    
    # Default configuration
    DEFAULT_IMAGES_DIR = "images"
    DEFAULT_CAPTURE_URL = "http://localhost:5000/capture_highres"
    LOWRES_CAPTURE_URL = "http://localhost:5000/capture"
    DEFAULT_FILENAME_FORMAT = "capture_{timestamp}.jpg"
    TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
    
    def __init__(
        self,
        images_dir: Optional[str] = None,
        capture_url: Optional[str] = None,
        filename_format: Optional[str] = None
    ):
        """
        Initialize the ImageCapture instance
        
        Args:
            images_dir: Directory to save captured images (default: "images")
            capture_url: URL of the camera capture endpoint (default: "http://localhost:5000/capture")
            filename_format: Format string for filenames (default: "capture_{timestamp}.jpg")
        """
        self.images_dir = Path(images_dir or self.DEFAULT_IMAGES_DIR)
        self.capture_url = capture_url or self.DEFAULT_CAPTURE_URL
        self.filename_format = filename_format or self.DEFAULT_FILENAME_FORMAT
        
        # Ensure images directory exists
        self._ensure_images_directory()
    
    def _ensure_images_directory(self) -> None:
        """Create images directory if it doesn't exist"""
        try:
            self.images_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Images directory ready: {self.images_dir.absolute()}")
        except Exception as e:
            logger.error(f"Failed to create images directory: {e}")
            raise ImageSaveError(f"Failed to create images directory: {e}")
    
    def _generate_filename(self, custom_prefix: Optional[str] = None) -> str:
        """
        Generate a timestamped filename for the captured image
        
        Args:
            custom_prefix: Optional custom prefix for the filename
            
        Returns:
            Generated filename
        """
        timestamp = datetime.now().strftime(self.TIMESTAMP_FORMAT)
        
        if custom_prefix:
            filename = f"{custom_prefix}_{timestamp}.jpg"
        else:
            filename = self.filename_format.format(timestamp=timestamp)
        
        return filename
    
    def capture_from_feed_server(
        self,
        timeout: int = 10,
        custom_prefix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Capture an image from the camera feed server and save it to disk
        
        Args:
            timeout: Request timeout in seconds (default: 10)
            custom_prefix: Optional custom prefix for the filename
            
        Returns:
            Dictionary containing:
                - success: bool - Whether capture was successful
                - filename: str - Name of the saved file (if successful)
                - filepath: str - Full path to the saved file (if successful)
                - image_bytes: bytes - The captured image data
                - message: str - Status message
                - error: str - Error message (if failed)
        """
        result = {
            'success': False,
            'filename': None,
            'filepath': None,
            'image_bytes': None,
            'message': '',
            'error': None
        }
        
        try:
            # Capture image from feed server
            logger.info(f"Capturing image from {self.capture_url}")
            response = requests.get(
                self.capture_url,
                timeout=timeout
            )
            
            if response.status_code != 200:
                error_msg = f"Camera feed server returned status {response.status_code}"
                logger.error(error_msg)
                result['error'] = error_msg
                result['message'] = error_msg
                return result
            
            # Get image bytes
            image_bytes = response.content
            result['image_bytes'] = image_bytes
            
            # Generate filename
            filename = self._generate_filename(custom_prefix)
            filepath = self.images_dir / filename
            
            # Save image to disk
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f"Image saved successfully: {filepath.absolute()}")
            
            result['success'] = True
            result['filename'] = filename
            result['filepath'] = str(filepath.absolute())
            result['message'] = f"Image captured and saved as {filename}"
            
            return result
            
        except requests.exceptions.Timeout:
            error_msg = "Camera feed server timed out"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
            
        except requests.exceptions.ConnectionError:
            error_msg = "Could not connect to camera feed server. Please ensure camera_feed.py is running."
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
            
        except IOError as e:
            error_msg = f"Failed to save image to disk: {e}"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error during capture: {e}"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
    
    def capture_and_return_bytes(
        self,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """
        Capture an image from the camera feed server and return bytes without saving
        
        Args:
            timeout: Request timeout in seconds (default: 10)
            
        Returns:
            Dictionary containing:
                - success: bool - Whether capture was successful
                - image_bytes: bytes - The captured image data (if successful)
                - message: str - Status message
                - error: str - Error message (if failed)
        """
        result = {
            'success': False,
            'image_bytes': None,
            'message': '',
            'error': None
        }
        
        try:
            logger.info(f"Capturing image bytes from {self.capture_url}")
            response = requests.get(
                self.capture_url,
                timeout=timeout
            )
            
            if response.status_code != 200:
                error_msg = f"Camera feed server returned status {response.status_code}"
                logger.error(error_msg)
                result['error'] = error_msg
                result['message'] = error_msg
                return result
            
            image_bytes = response.content
            result['success'] = True
            result['image_bytes'] = image_bytes
            result['message'] = "Image captured successfully"
            
            return result
            
        except requests.exceptions.Timeout:
            error_msg = "Camera feed server timed out"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
            
        except requests.exceptions.ConnectionError:
            error_msg = "Could not connect to camera feed server"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error during capture: {e}"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result

    def capture_with_led_assistance(
        self,
        timeout: int = 20,
        custom_prefix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Capture a final high-quality image using the server-side LED workflow.

        The target endpoint enforces the sequence:
        preliminary dummy capture -> light evaluation -> PWM LED set ->
        optional settle -> final high-quality capture -> LED off.
        """
        original_capture_url = self.capture_url
        try:
            self.capture_url = self.DEFAULT_CAPTURE_URL
            return self.capture_from_feed_server(
                timeout=timeout,
                custom_prefix=custom_prefix
            )
        finally:
            self.capture_url = original_capture_url
    
    def save_image_bytes(
        self,
        image_bytes: bytes,
        custom_prefix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save provided image bytes to disk
        
        Args:
            image_bytes: Image data as bytes
            custom_prefix: Optional custom prefix for the filename
            
        Returns:
            Dictionary containing:
                - success: bool - Whether save was successful
                - filename: str - Name of the saved file (if successful)
                - filepath: str - Full path to the saved file (if successful)
                - message: str - Status message
                - error: str - Error message (if failed)
        """
        result = {
            'success': False,
            'filename': None,
            'filepath': None,
            'message': '',
            'error': None
        }
        
        try:
            # Generate filename
            filename = self._generate_filename(custom_prefix)
            filepath = self.images_dir / filename
            
            # Save image to disk
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f"Image saved successfully: {filepath.absolute()}")
            
            result['success'] = True
            result['filename'] = filename
            result['filepath'] = str(filepath.absolute())
            result['message'] = f"Image saved as {filename}"
            
            return result
            
        except IOError as e:
            error_msg = f"Failed to save image to disk: {e}"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error during save: {e}"
            logger.error(error_msg)
            result['error'] = error_msg
            result['message'] = error_msg
            return result
    
    def list_captured_images(self) -> list:
        """
        List all captured images in the images directory
        
        Returns:
            List of image filenames sorted by modification time (newest first)
        """
        try:
            # Get all image files
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png']:
                image_files.extend(self.images_dir.glob(ext))
            
            # Sort by modification time (newest first)
            image_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            return [f.name for f in image_files]
            
        except Exception as e:
            logger.error(f"Failed to list captured images: {e}")
            return []


# Convenience function for quick capture
def capture_and_save(
    custom_prefix: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Convenience function to capture and save an image
    
    Args:
        custom_prefix: Optional custom prefix for the filename
        timeout: Request timeout in seconds (default: 10)
        
    Returns:
        Result dictionary from capture_from_feed_server
    """
    capturer = ImageCapture()
    return capturer.capture_from_feed_server(timeout=timeout, custom_prefix=custom_prefix)


# Convenience function to capture bytes only
def capture_bytes_only(timeout: int = 10) -> Dict[str, Any]:
    """
    Convenience function to capture image bytes without saving
    
    Args:
        timeout: Request timeout in seconds (default: 10)
        
    Returns:
        Result dictionary from capture_and_return_bytes
    """
    capturer = ImageCapture()
    return capturer.capture_and_return_bytes(timeout=timeout)


def capture_and_save_with_led_assistance(
    custom_prefix: Optional[str] = None,
    timeout: int = 20
) -> Dict[str, Any]:
    """Convenience function for the dashboard LED-assisted capture path."""
    capturer = ImageCapture()
    return capturer.capture_with_led_assistance(timeout=timeout, custom_prefix=custom_prefix)


if __name__ == "__main__":
    # Test the module
    print("Testing ImageCapture module...")
    
    # Test capture and save
    print("\n1. Testing capture_and_save():")
    result = capture_and_save()
    print(f"   Success: {result['success']}")
    print(f"   Message: {result['message']}")
    if result['success']:
        print(f"   Filename: {result['filename']}")
        print(f"   Filepath: {result['filepath']}")
    
    # Test list captured images
    print("\n2. Testing list_captured_images():")
    capturer = ImageCapture()
    images = capturer.list_captured_images()
    print(f"   Found {len(images)} images:")
    for img in images[:5]:  # Show first 5
        print(f"   - {img}")
    
    print("\nTest complete!")
