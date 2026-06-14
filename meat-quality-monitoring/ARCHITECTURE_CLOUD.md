# Cloud-Based (Server) Architecture — `masterV3-cloud` branch

This branch restores the **original cloud/server-based data flow** for the Meat
Quality Monitoring System. It exists alongside the current `masterV2` branch,
which uses a **Pi-hotspot + local MQTT** approach. Both branches are fully
independent and the live hotspot system is **not affected** by this branch.

---

## 1. Architecture Diagram

```
                ┌──────────────────────────────────────────────────────┐
                    WiFi (home / mobile hotspot)                         │
                              │                                           │
   ┌──────────────┐    HTTP POST (JSON, API key)        ┌───────────────────────────────┐
   │   ESP32      │ ──────────────────────────────────► │  Cloud API Server             │
   │ (sensors:    │  https://meat-monitor.kalobiral     │  meat-monitor.kalobiral.com.bd│
   │  MQ135/136/  │  .com.bd/api/meat-data              │  - /api/meat-data (POST)      │
   │  137, AHT10) │  offline queue + EEPROM Wi-Fi creds │  - /current      (GET)        │
   └──────────────┘                                     │  - /history     (GET)         │
                                                        └───────────────┬───────────────┘
                                                                        │ poll (bookmark + catch-up)
                                                                        ▼
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │  Raspberry Pi                                                                │
   │  ┌───────────────────────────┐    ┌──────────────────────────────────────┐  │
   │  │ api_client.py (poller)    │ ─► │ Local SQLite DB  (meat_monitor.db)   │  │
   │  │  - polls /current         │    └───────────────┬──────────────────────┘  │
   │  │  - catch-up via /history  │                    │                          │
   │  │  - bookmark recovery      │                    ▼                          │
   │  │  systemd: meat-monitor-   │           ┌──────────────────────┐            │
   │  │  client.service           │           │ Streamlit Dashboard  │            │
   │  └───────────────────────────┘           │ (app.py)             │            │
   │                                          └──────────────────────┘            │
   │  ┌───────────────────────────┐                                                │
   │  │ capture.py (camera)       │ ──► pending_sync/ (local images)              │
   │  └──────────────┬────────────┘            │                                   │
   │                 │                         │ batch upload                      │
   │                 │                         ▼                                   │
   │  ┌──────────────▼────────────┐   sync.py ─────────► iot-upload.kalobiral     │
   │  │ pi-image-capture.service  │            .com.bd/api/upload-image           │
   │  └───────────────────────────┘                                                │
   └──────────────────────────────────────────────────────────────────────────────┘
```

## 2. Data Flow (sensor readings)

| Step | Component | Direction | Protocol |
|------|-----------|-----------|----------|
| 1 | ESP32 reads MQ135/136/137 + AHT10 | local | I2C / ADC |
| 2 | ESP32 → Cloud API (`/api/meat-data`) | outbound | HTTPS POST (JSON, `X-API-Key`) |
| 3 | ESP32 offline queue | local | EEPROM-backed FIFO (max 20) |
| 4 | Pi `api_client.py` polls `/current` | Pi → cloud | HTTPS GET, every 5 s |
| 5 | `api_client.py` stores new reading in `meat_monitor.db` | local | SQLite |
| 6 | On startup, `catch_up()` fetches `/history` since bookmark | Pi → cloud | HTTPS GET |
| 7 | Bookmark persisted at `~/.meat_monitor_bookmark.json` | local | JSON file |
| 8 | Streamlit dashboard reads local DB | local | SQLite |

## 3. Data Flow (images)

| Step | Component | Direction |
|------|-----------|-----------|
| 1 | `capture.py` captures from camera → `pending_sync/` | local write |
| 2 | `sync.py` uploads batches ≥ 10 MiB to `iot-upload.kalobiral.com.bd` | HTTPS POST |
| 3 | Successfully uploaded images are deleted locally | local cleanup |
| 4 | `sync_state.db` ledger tracks upload state | SQLite |

## 4. Key Files (this branch)

| File | Purpose |
|------|---------|
| [`config.py`](meat-quality-monitoring/config.py:1) | `SENSOR_API_BASE`, polling intervals, bookmark path, thresholds |
| [`api_client.py`](meat-quality-monitoring/api_client.py:1) | Cloud poller + catch-up + `SensorAPIClient` for dashboard |
| [`sync.py`](meat-quality-monitoring/sync.py:1) | Batch image uploader to cloud |
| [`db_manager.py`](meat-quality-monitoring/db_manager.py:1) | SQLite access layer |
| [`app.py`](meat-quality-monitoring/app.py:1) | Streamlit dashboard |
| [`capture.py`](meat-quality-monitoring/capture.py:1) | Camera capture service |
| [`deploy/meat-monitor-client.service`](meat-quality-monitoring/deploy/meat-monitor-client.service:1) | systemd unit for API poller |
| [`deploy/pi-image-capture.service`](meat-quality-monitoring/deploy/pi-image-capture.service:1) | systemd unit for camera |
| [`../meat_quality_Air_data_ESP_Node/ESP_sensor_node/src/main.cpp`](../meat_quality_Air_data_ESP_Node/ESP_sensor_node/src/main.cpp:1) | ESP32 HTTP API firmware |
| [`../meat_quality_Air_data_ESP_Node/ESP_sensor_node/platformio.ini`](../meat_quality_Air_data_ESP_Node/ESP_sensor_node/platformio.ini:1) | ESP32 build config |

## 5. Configuration (`.env`)

```ini
SENSOR_API_BASE=https://meat-monitor.kalobiral.com.bd/api/meat-data
SENSOR_API_KEY=<your-api-key>
SENSOR_API_POLL_INTERVAL=5
SENSOR_API_MAX_RETRIES=3
SENSOR_API_HISTORY_LIMIT=5000

# Image upload
UPLOAD_URL=https://iot-upload.kalobiral.com.bd/api/upload-image
UPLOAD_API_KEY=<your-upload-api-key>
```

## 6. How this branch differs from `masterV2`

| Aspect | `masterV2` (current live) | `masterV3-cloud` (this branch) |
|--------|---------------------------|--------------------------------|
| ESP → where? | MQTT broker `192.168.4.1` (Pi hotspot) | HTTPS to cloud `meat-monitor.kalobiral.com.bd` |
| Pi data source | Local MQTT subscriber (`mqtt_subscriber.py`) | Cloud API poller (`api_client.py`) |
| Requires internet on ESP? | No (Pi hotspot only) | Yes |
| Requires cloud server? | No | Yes |
| Image upload | Local only (`pending_sync/`) | `sync.py` → cloud upload endpoint |
| systemd unit for data | `pi-mqtt-subscriber.service` | `meat-monitor-client.service` |
| Bookmark recovery | N/A (direct MQTT, no gap) | Yes (`~/.meat_monitor_bookmark.json`) |

## 7. How to switch the Pi to this architecture

> ⚠️ This is optional. The live system is `masterV2`. Only do this if you want
> to migrate the Pi back to the cloud flow.

```bash
# 1. Stop the hotspot-mode services
sudo systemctl stop pi-mqtt-subscriber.service pi-image-capture.service

# 2. Switch the main checkout to the cloud branch
cd ~/projects/meat-quality-monitoring
git stash            # preserve any local tweaks
git checkout masterV3-cloud
git stash pop        # optional

# 3. Install dependencies (requests, python-dotenv, ...)
pip install -r requirements.txt

# 4. Configure API credentials
cp .env.example .env
# edit .env: set SENSOR_API_KEY and UPLOAD_API_KEY

# 5. Enable the cloud-mode services
sudo cp deploy/meat-monitor-client.service /etc/systemd/system/
sudo cp deploy/pi-image-capture.service    /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now meat-monitor-client.service pi-image-capture.service
```

## 8. ESP32 re-flash (HTTP API firmware)

```bash
cd meat_quality_Air_data_ESP_Node/ESP_sensor_node
# edit src/main.cpp: set API_KEY (and optionally API_URL)
# flash:
pio run -t upload
```

After flashing, the ESP connects to the home WiFi (configured via the SoftAP
portal at `192.168.4.1` on first boot) and POSTs readings to the cloud.
