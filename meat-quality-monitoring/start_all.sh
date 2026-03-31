#!/bin/bash
# Startup script for Meat Quality Monitoring System
# This script launches both the Camera Feed Server and the Dashboard

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Meat Quality Monitoring System"
echo "=========================================="
echo ""

# Activate the virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Virtual environment activated."
else
    echo "WARNING: Virtual environment not found. Using system Python."
fi

echo ""
echo "Starting Camera Feed Server (background)..."
echo ""

# Start camera feed in background, redirecting output to log file
nohup python camera_feed.py > camera_feed.log 2>&1 &
CAMERA_PID=$!

# Wait a moment for camera feed to start
sleep 2

# Check if camera feed started successfully
if ps -p $CAMERA_PID > /dev/null; then
    echo "Camera Feed Server started successfully (PID: $CAMERA_PID)"
    echo "Camera feed available at: http://localhost:5000"
else
    echo "WARNING: Camera Feed Server may not have started properly."
    echo "Check camera_feed.log for details."
fi

echo ""
echo "=========================================="
echo "Starting Dashboard..."
echo "=========================================="
echo ""
echo "Dashboard will be available at: http://localhost:8502"
echo ""
echo "Press Ctrl+C to stop both services."
echo "=========================================="
echo ""

# Start the Streamlit dashboard in foreground
streamlit run app.py --server.address 0.0.0.0 --server.port 8502

# When dashboard is stopped, also stop the camera feed
if ps -p $CAMERA_PID > /dev/null; then
    echo ""
    echo "Stopping Camera Feed Server..."
    kill $CAMERA_PID
fi

echo "All services stopped."
