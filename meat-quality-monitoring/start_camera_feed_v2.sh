#!/bin/bash
# Startup script for the Live Camera Feed Server - Pi Camera Module v2.1 (IMX219)
# Starts the Flask camera feed server at http://localhost:5000
#
# The v2.1 camera is FIXED FOCUS (no autofocus flags passed to rpicam-*).
# Requires /boot/firmware/config.txt to contain: dtoverlay=imx219,cam0

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use virtual environment Python (project venv)
VENV_PYTHON="venv/bin/python3"

# Fallback to a sibling .venv if the project venv is missing
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="../.venv/bin/python"
fi

# Check if virtual environment exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found (tried venv/ and ../.venv)"
    echo "Please create the virtual environment first."
    exit 1
fi

# Check if Flask is installed
if ! $VENV_PYTHON -c "import flask" 2>/dev/null; then
    echo "Flask is not installed. Installing..."
    $VENV_PYTHON -m pip install Flask
fi

# Check if rpicam-vid is available
if ! command -v rpicam-vid &> /dev/null; then
    echo "WARNING: rpicam-vid not found!"
    echo "Please ensure your Raspberry Pi Camera v2.1 is properly connected."
    echo ""
    echo "You may need to:"
    echo "  1. Check camera connection"
    echo "  2. Enable the camera (sudo raspi-config -> Interface Options -> Camera)"
    echo "  3. Install libcamera-apps: sudo apt install libcamera-apps"
    echo "  4. Set the overlay for v2.1 in /boot/firmware/config.txt: dtoverlay=imx219,cam0"
    echo "  5. Reboot after changing the overlay"
    echo ""
fi

echo "=========================================="
echo "Starting Live Camera Feed Server (v2.1)"
echo "=========================================="
echo ""
echo "Camera feed will be available at:"
echo "  http://localhost:5000"
echo ""
echo "Camera: Raspberry Pi Camera Module v2.1 (IMX219, fixed focus)"
echo ""

exec $VENV_PYTHON camera_feed_v2.py
