# Raspberry Pi Hotspot + Local MQTT Setup (Offline-First)

This setup makes your Pi fully independent from internet for sensing:

`ESP32 -> Pi Hotspot WiFi -> Mosquitto MQTT -> mqtt_subscriber.py -> SQLite -> Dashboard`

## 1) Configure Raspberry Pi as WiFi Hotspot

Install required packages:

```bash
sudo apt update
sudo apt install -y hostapd dnsmasq
sudo systemctl unmask hostapd
sudo systemctl disable hostapd dnsmasq
```

Set static hotspot IP on WLAN (example uses `wlan0` + `192.168.4.1`):

```bash
sudo nano /etc/dhcpcd.conf
```

Append:

```conf
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
```

Configure DHCP for hotspot clients:

```bash
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.bak
sudo nano /etc/dnsmasq.conf
```

Use:

```conf
interface=wlan0
dhcp-range=192.168.4.20,192.168.4.200,255.255.255.0,24h
```

Configure hotspot SSID/password:

```bash
sudo nano /etc/hostapd/hostapd.conf
```

Use:

```conf
country_code=BD
interface=wlan0
ssid=MeatMonitor-Pi
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=MeatPi@12345
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

Point hostapd service to this file:

```bash
sudo nano /etc/default/hostapd
```

Set:

```conf
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

Enable/start services:

```bash
sudo systemctl enable hostapd dnsmasq
sudo systemctl restart hostapd dnsmasq
sudo systemctl status hostapd dnsmasq
```

## 2) Configure Mosquitto Broker on Pi

Install and enable:

```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
```

Create MQTT user:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd meat_monitor
```

Create broker config:

```bash
sudo nano /etc/mosquitto/conf.d/meat-monitor.conf
```

Use:

```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /etc/mosquitto/passwd
persistence true
persistence_location /var/lib/mosquitto/
```

Restart broker:

```bash
sudo systemctl restart mosquitto
sudo systemctl status mosquitto
```

## 3) Deploy Python Ingestion + Dashboard

Install dependencies:

```bash
cd /home/pi/meat-quality-monitoring
python3 -m pip install -r requirements.txt
```

Install MQTT subscriber service:

```bash
sudo cp deploy/pi-mqtt-subscriber.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-mqtt-subscriber.service
sudo systemctl start pi-mqtt-subscriber.service
sudo systemctl status pi-mqtt-subscriber.service
```

Run dashboard:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## 4) Configure ESP32

In [`ESP_sensor_node/src/main.cpp`](../meat_quality_Air_data_ESP_Node/ESP_sensor_node/src/main.cpp):

- `MQTT_BROKER` must be hotspot gateway IP (`192.168.4.1`)
- WiFi SSID/PASS should match hotspot (`MeatMonitor-Pi` / `MeatPi@12345`)
- MQTT credentials must match Mosquitto (`meat_monitor` + your password)

Then build/upload from [`ESP_sensor_node/platformio.ini`](../meat_quality_Air_data_ESP_Node/ESP_sensor_node/platformio.ini).

## 5) Validation

Check incoming MQTT on Pi:

```bash
mosquitto_sub -h localhost -t "meat-quality/data" -u meat_monitor -P '<password>' -v
```

Check DB growth:

```bash
cd /home/pi/meat-quality-monitoring
python3 -c "from db_manager import get_db_manager; db=get_db_manager(); print(db.get_reading_count())"
```

## 6) Optional Internet Sync Later

If/when internet returns, you can add a separate sync worker to forward historical data to cloud. The sensing pipeline remains local and uninterrupted.

