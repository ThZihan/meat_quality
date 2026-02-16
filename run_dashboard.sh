#!/bin/bash
# Startup script for Meat Quality Monitoring Dashboard
# This script activates the virtual environment and runs the Streamlit dashboard

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Create data directory if it doesn't exist
mkdir -p data/backups data/exports

# Check if Mosquitto is running
if ! systemctl is-active --quiet mosquitto; then
    echo "Warning: Mosquitto MQTT broker is not running."
    echo "Start it with: sudo systemctl start mosquitto"
    echo ""
fi

# Run Streamlit dashboard
echo "Starting Meat Quality Monitoring Dashboard..."
echo "Access at: http://localhost:8501"
echo "Press Ctrl+C to stop"
echo ""

streamlit run app.py --server.address 0.0.0.0 --server.port 8501
