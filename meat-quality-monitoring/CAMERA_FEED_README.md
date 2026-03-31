# Live Camera Feed Server

This module provides a live camera feed from your Raspberry Pi Camera Module 3 accessible via web browser at `http://localhost:5000`.

## Features

- **Real-time MJPEG streaming** from Camera Module 3 using `rpicam-vid` (libcamera stack)
- **Autofocus support** with configurable modes (Auto, Manual, Continuous)
- **Modern web interface** with status indicators
- **Auto-recovery** on connection errors
- **Status API** for health monitoring
- **Thread-safe** camera process management
- **Configuration API** for runtime parameter adjustment
- **Environment variable support** for flexible configuration

## Requirements

- Python 3.7+
- Flask 3.0+
- `rpicam-vid` (libcamera-apps)
- Raspberry Pi Camera Module 3 connected to Raspberry Pi

## System Dependencies

The camera feed server requires the following system packages to be installed via `apt` (not pip):

```bash
# Update package lists
sudo apt update

# Install required camera packages
sudo apt install -y libcamera-apps libcamera-tools v4l-utils
```

These packages provide:
- **libcamera-apps**: `rpicam-vid` and `rpicam-still` for Camera Module 3
- **libcamera-tools**: Additional libcamera utilities
- **v4l-utils**: Video4Linux utilities for camera management

## Installation

1. Install system dependencies:
```bash
sudo apt update && sudo apt install -y libcamera-apps libcamera-tools v4l-utils
```

2. Install Python dependencies:
```bash
cd meat-quality-monitoring
pip install -r requirements.txt
```

Or install only the required packages:
```bash
pip install Flask opencv-python Pillow
```

3. Verify `rpicam-vid` is installed:
```bash
which rpicam-vid
# Should show /usr/bin/rpicam-vid
```

## Usage

### Quick Start

Simply run the startup script:
```bash
./start_camera_feed.sh
```

### Manual Start

```bash
python3 camera_feed.py
```

### Access the Camera Feed

Open your web browser and navigate to:
```
http://localhost:5000
```

Or from another device on your network:
```
http://<your-raspberry-pi-ip>:5000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main camera feed page |
| `/video_feed` | GET | MJPEG video stream |
| `/status` | GET | Camera status JSON |
| `/config` | GET | Get current camera configuration |
| `/config` | POST | Update camera configuration |
| `/autofocus_trigger` | POST | Trigger autofocus on Camera Module 3 |

## Environment Variables

You can configure camera settings via environment variables:

```bash
# Camera feed settings
export CAMERA_FRAME_RATE=30
export CAMERA_WIDTH=1280
export CAMERA_HEIGHT=720
export CAMERA_JPEG_QUALITY=85
export CAMERA_BITRATE=5000000
export CAMERA_DEVICE=/dev/video0

# Autofocus settings
export CAMERA_AUTOFOCUS_MODE=continuous
export CAMERA_AUTOFOCUS_RANGE=normal
export CAMERA_AUTOFOCUS_SPEED=normal

# Capture settings
export CAMERA_CAPTURE_WIDTH=1640
export CAMERA_CAPTURE_HEIGHT=1232
export CAMERA_CAPTURE_FORMAT=jpeg
export CAMERA_CAPTURE_TIMEOUT=5000
```

Then start the camera feed server:
```bash
python3 camera_feed.py
```

### Status API Response

```json
{
  "status": "ok",
  "camera_type": "rpicam-vid (libcamera)",
  "camera_model": "Raspberry Pi Camera Module 3",
  "frame_width": 640,
  "frame_height": 480,
  "fps": 30,
  "pid": 4269,
  "autofocus_mode": "continuous",
  "autofocus_range": "normal",
  "autofocus_speed": "normal"
}
```

### Configuration API

**GET /config** - Returns current configuration:
```json
{
  "status": "ok",
  "config": {
    "frame_rate": 30,
    "frame_width": 640,
    "frame_height": 480,
    "jpeg_quality": 85,
    "autofocus_mode": "continuous",
    "autofocus_range": "normal",
    "autofocus_speed": "normal"
  }
}
```

**POST /config** - Update configuration:
```bash
curl -X POST http://localhost:5000/config \
  -H "Content-Type: application/json" \
  -d '{
    "frame_rate": 30,
    "frame_width": 1280,
    "frame_height": 720,
    "jpeg_quality": 90,
    "autofocus_mode": "continuous",
    "autofocus_range": "normal",
    "autofocus_speed": "normal"
  }'
```

### Autofocus Trigger API

Trigger autofocus on Camera Module 3:
```bash
curl -X POST http://localhost:5000/autofocus_trigger \
  -H "Content-Type: application/json" \
  -d '{"trigger": "start"}'
```

Available trigger types:
- `start` - Start autofocus
- `cancel` - Cancel autofocus

## Configuration

### Default Configuration

You can modify default camera settings in [`camera_config.py`](camera_config.py:1) by editing the `DEFAULT_FEED_CONFIG` object:

```python
DEFAULT_FEED_CONFIG = CameraFeedConfig(
    frame_rate=30,
    frame_width=640,
    frame_height=480,
    bitrate=5000000,  # 5 Mbps
    jpeg_quality=85,
    autofocus_mode=AutofocusMode.CONTINUOUS,
    autofocus_range=AutofocusRange.NORMAL,
    autofocus_speed=AutofocusSpeed.NORMAL
)
```

### Autofocus Configuration

Camera Module 3 supports advanced autofocus options:

#### Autofocus Modes

| Mode | Description |
|------|-------------|
| `auto` | Single autofocus trigger |
| `manual` | Manual focus control |
| `continuous` | Continuous autofocus (default) |

#### Autofocus Range

| Range | Description |
|-------|-------------|
| `normal` | Standard focus range (default) |
| `macro` | Close-up focus (0.1-0.5m) |
| `full` | Full focus range |

#### Autofocus Speed

| Speed | Description |
|-------|-------------|
| `normal` | Standard focus speed (default) |
| `fast` | Fast focus (may reduce accuracy) |

### Resolution Presets

Available resolution presets in [`camera_feed.py`](camera_feed.py:1):

| Preset | Resolution | Description |
|--------|------------|-------------|
| `vga` | 640x480 | VGA (Low bandwidth) |
| `hd` | 1280x720 | HD (Standard) |
| `fhd` | 1920x1080 | Full HD |
| `2k` | 2560x1440 | 2K QHD |
| `max` | 3280x2464 | Camera Module 3 Max |

### FPS Presets

Available FPS presets in [`camera_feed.py`](camera_feed.py:1):

| Preset | FPS | Description |
|--------|-----|-------------|
| `15` | 15 | Low bandwidth |
| `30` | 30 | Standard (default) |
| `60` | 60 | Smooth |
| `90` | 90 | High performance |

## Troubleshooting

### Camera not found

If you see "Failed to initialize camera":

1. Check rpicam-vid is installed:
```bash
which rpicam-vid
```

2. Test camera directly:
```bash
rpicam-vid -t 5000 --inline -o - | mpv -
```

3. Check camera connection and enable if needed:
```bash
sudo raspi-config
# Navigate to: Interface Options -> Camera -> Enable
```

4. Verify camera is detected:
```bash
libcamera-hello --list-cameras
```

### Black screen or no video

1. Check if camera is working with test script:
```bash
python3 test_camera.py
```

2. Test with rpicam-still:
```bash
rpicam-still -t 1000 -o test.jpg
```

3. Check camera status:
```bash
curl http://localhost:5000/status
```

### Autofocus not working

1. Verify Camera Module 3 is properly connected:
```bash
libcamera-hello
```

2. Check autofocus status:
```bash
rpicam-vid --autofocus-mode continuous -t 5000 --inline -o - | mpv -
```

3. Trigger autofocus via API:
```bash
curl -X POST http://localhost:5000/autofocus_trigger \
  -H "Content-Type: application/json" \
  -d '{"trigger": "start"}'
```

## Running in Background

To run the camera feed server in the background:

```bash
nohup python3 camera_feed.py > camera_feed.log 2>&1 &
```

To stop it:
```bash
pkill -f camera_feed.py
```

Or using systemd (recommended for production):
```bash
sudo systemctl enable camera-feed.service
sudo systemctl start camera-feed.service
sudo systemctl status camera-feed.service
```

## Integration with Main Dashboard

The camera feed can run alongside the main Streamlit dashboard:

Terminal 1 (Main Dashboard):
```bash
streamlit run app.py
```

Terminal 2 (Camera Feed):
```bash
./start_camera_feed.sh
```

Then access both:
- Dashboard: `http://localhost:8501`
- Camera Feed: `http://localhost:5000`

## Technical Details

### How It Works

1. **Flask Server**: Serves the web interface and video stream
2. **MJPEG Streaming**: Uses multipart HTTP response for continuous video
3. **libcamera Stack**: Uses `rpicam-vid` for Camera Module 3 access
4. **Autofocus**: Configurable autofocus modes via libcamera
5. **Thread Safety**: Uses locks to prevent concurrent camera access
6. **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM
7. **Configuration Management**: Centralized configuration via `camera_config.py` module
8. **Environment Variables**: Flexible configuration via environment variables

### Performance

- Resolution: 640x480 (configurable)
- Frame Rate: ~30 FPS
- Latency: ~100-200ms (local network)
- CPU Usage: ~5-15% (depending on resolution)
- Memory: ~50-100 MB (buffer management)

### Camera Module 3 Features

- **Autofocus**: Built-in PDAF (Phase Detection Autofocus)
- **Resolution**: Up to 4608x2592 pixels
- **Field of View**: 66° (horizontal), 53° (vertical)
- **Focus Range**: 0.1m to infinity (macro mode)
- **Video Modes**: Up to 1080p at 50/60 FPS

## Files

| File | Description |
|------|-------------|
| [`camera_feed.py`](camera_feed.py:1) | Flask server with MJPEG streaming and autofocus |
| [`camera.py`](camera.py:1) | Camera module (shared with main app) |
| [`camera_config.py`](camera_config.py:1) | Camera configuration management |
| [`templates/camera_feed.html`](templates/camera_feed.html:1) | Web interface template |
| [`start_camera_feed.sh`](start_camera_feed.sh:1) | Startup script |
| [`requirements.txt`](requirements.txt:1) | Python and system dependencies |

## Advanced Usage

### Using the Camera Module in Python

```python
from camera import CameraModule3, check_module3_available
from camera_config import CameraCaptureConfig, AutofocusMode

# Check if Camera Module 3 is available
if check_module3_available():
    # Create configuration with autofocus
    config = CameraCaptureConfig(
        width=1920,
        height=1080,
        autofocus_mode=AutofocusMode.CONTINUOUS
    )
    
    # Capture image
    with CameraModule3(config) as camera:
        image_bytes = camera.capture_image_bytes()
        # Process image...
    
    # Trigger autofocus
    camera.trigger_autofocus('start')
else:
    print("Camera Module 3 not available, falling back to V4L2")
```

## License

Part of the Meat Quality Monitoring System.
