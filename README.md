# 🥩 Meat Quality Monitoring System

A sophisticated Streamlit dashboard for monitoring meat quality using simulated sensor data. This system simulates readings from MQ136 (H2S), MQ137 (NH3), MQ135 (CO2), and DHT11 (Temperature/Humidity) sensors.

## Features

- **Realistic Data Simulation**: Time-based gas accumulation with temperature correlation
- **Real-time Dashboard**: Auto-refreshing interface with 2-second updates
- **Visual Analytics**: Multi-line charts and correlation heatmaps
- **Spoilage Detection**: Automatic status determination (Fresh/Warning/Spoiled)
- **Interactive Controls**: Start/Stop simulation, adjust temperature and humidity

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Install Dependencies

```bash
cd meat_quality_monitoring
pip install -r requirements.txt
```

## Running the Dashboard

### On Raspberry Pi (Local)

```bash
cd meat_quality_monitoring
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

### Access from PC's Browser

To access the dashboard from your PC's browser (when running on Raspberry Pi):

1. **Find your Raspberry Pi's IP address:**
   ```bash
   hostname -I
   ```

2. **Run Streamlit with network access:**
   ```bash
   streamlit run app.py --server.address 0.0.0.0 --server.port 8501
   ```

3. **Open in your PC's browser:**
   ```
   http://<RASPBERRY_PI_IP>:8501
   ```
   Replace `<RASPBERRY_PI_IP>` with the actual IP address (e.g., `http://192.168.1.100:8501`)

## Dashboard Layout

### Sidebar Controls
- **Start/Stop Simulation**: Toggle the data simulation
- **Room Temperature Slider**: Adjust temperature (0-50°C) to test correlation
- **Humidity Slider**: Adjust humidity (0-100%)
- **Reset Button**: Reset simulation to initial state
- **Time Elapsed**: Shows simulation duration
- **Thresholds Info**: Reference values for spoilage detection

### Top Row - Metric Cards
- H2S (MQ136): Hydrogen Sulfide in ppm
- NH3 (MQ137): Ammonia in ppm
- CO2 (MQ135): Carbon Dioxide in ppm
- Temperature: Room temperature in °C
- Humidity: Relative humidity in %

### Middle Row - Trends Chart
Multi-line chart showing H2S and NH3 levels over the last 100 readings with threshold indicators.

### Bottom Row - Analytics
- **Correlation Heatmap**: Shows relationships between temperature and gas levels
- **Spoilage Status**: Large status indicator (Fresh/Warning/Spoiled) with progress bars

## Simulation Logic

### Gas Accumulation
- H2S and NH3 levels increase over time (simulating spoilage)
- Higher temperatures accelerate gas production (Q10 coefficient)
- Realistic sensor noise added to all readings

### Spoilage Thresholds
| Gas | Fresh | Warning | Spoiled |
|-----|-------|---------|---------|
| H2S | < 10 ppm | 10-50 ppm | > 50 ppm |
| NH3 | < 25 ppm | 25-100 ppm | > 100 ppm |

## Hardware Context

This dashboard is designed for the following sensors:
- **MQ136**: Hydrogen Sulfide (H2S) - Primary spoilage indicator
- **MQ137**: Ammonia (NH3) - Secondary decomposition indicator
- **MQ135**: General Air Quality (CO2, organic compounds)
- **DHT11**: Temperature and Humidity

## File Structure

```
meat_quality_monitoring/
├── app.py              # Main Streamlit dashboard
├── mock_data.py        # Data simulation module
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## License

MIT License
