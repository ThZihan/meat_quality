#!/bin/bash
# Startup script for the Live Camera Feed Server
# This script starts the Flask camera feed server at localhost:5000
# Supports Raspberry Pi Camera Module 3 with autofocus

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use virtual environment Python
VENV_PYTHON="../.venv/bin/python"

# Check if virtual environment exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PYTHON"
    echo "Please create the virtual environment first."
    exit 1
fi

# Check if Flask is installed
if ! $VENV_PYTHON -c "import flask" 2>/dev/null; then
    echo "Flask is not installed. Installing..."
    $VENV_PYTHON -m pip install Flask
fi

# Check if OpenCV is installed
if ! $VENV_PYTHON -c "import cv2" 2>/dev/null; then
    echo "OpenCV is not installed. Installing..."
    $VENV_PYTHON -m pip install opencv-python
fi

# Check if rpicam-vid is available
if ! command -v rpicam-vid &> /dev/null; then
    echo "WARNING: rpicam-vid not found!"
    echo "Please ensure your Raspberry Pi Camera Module 3 is properly connected."
    echo ""
    echo "You may need to:"
    echo "  1. Check camera connection"
    echo "  2. Enable the camera (sudo raspi-config -> Interface Options -> Camera)"
    echo "  3. Install libcamera-apps: sudo apt install libcamera-apps"
    echo "  4. Reboot if needed"
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to cancel..."
fi

echo "=========================================="
echo "Starting Live Camera Feed Server"
echo "=========================================="
echo ""
echo "Camera feed will be available at:"
echo "  http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Start the camera feed server
$VENV_PYTHON camera_feed.py
