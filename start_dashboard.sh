#!/bin/bash
# Startup script for Meat Quality Monitoring System Dashboard

# Navigate to the project folder
cd /home/zihan/projects/meat-quality-monitoring

# Activate the virtual environment
source venv/bin/activate

# Run the Streamlit app with LAN access on port 8502
streamlit run app.py --server.address 0.0.0.0 --server.port 8502

# Keep window open if there's an error
read -p "Press Enter to close..."
