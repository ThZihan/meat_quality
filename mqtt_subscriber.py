#!/usr/bin/env python3
"""
Standalone MQTT subscriber for meat quality monitoring system.
Runs independently of Streamlit and writes sensor data to database.
This solves the issue of Streamlit's frequent reruns causing MQTT client reconnections.
"""

import logging
import json
import signal
import sys
from typing import Optional
from datetime import datetime
import paho.mqtt.client as mqtt
import config
import db_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mqtt_subscriber.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MQTTSubscriber:
    """
    MQTT subscriber that runs independently and writes to database.
    Designed to be run as a separate process from Streamlit.
    """
    
    def __init__(self, broker: str = None, port: int = None,
                 username: str = None, password: str = None):
        """
        Initialize MQTT subscriber.
        
        Args:
            broker: MQTT broker address
            port: MQTT broker port
            username: MQTT username
            password: MQTT password
        """
        self.broker = broker or config.MQTT_BROKER
        self.port = port or config.MQTT_PORT
        self.username = username or config.MQTT_USERNAME
        self.password = password or config.MQTT_PASSWORD
        self.topic = config.MQTT_TOPIC
        self.keep_running = True
        self.connected = False
        
        # Create MQTT client with paho-mqtt 1.6.x API
        self.client = mqtt.Client(
            client_id="MeatMonitor-Pi-Subscriber",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            transport="tcp"
        )
        self.client.username_pw_set(self.username, self.password)
        
        # Database manager
        self.db = db_manager.get_db_manager()
        
        # Setup MQTT callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_log = self._on_log
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"MQTT subscriber initialized for broker: {self.broker}:{self.port}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.keep_running = False
        self.disconnect()
        sys.exit(0)
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback when MQTT client connects to broker.
        """
        if rc == mqtt.MQTT_ERR_SUCCESS:
            self.connected = True
            logger.info(f"Connected to MQTT broker: {self.broker}:{self.port}")
            
            # Subscribe to topics
            client.subscribe(self.topic, qos=config.MQTT_QOS)
            client.subscribe(config.MQTT_STATUS_TOPIC, qos=config.MQTT_QOS)
            client.subscribe(config.MQTT_LWT_TOPIC, qos=config.MQTT_QOS)
            
            logger.info(f"Subscribed to topics: {self.topic}, {config.MQTT_STATUS_TOPIC}, {config.MQTT_LWT_TOPIC}")
        else:
            logger.error(f"Failed to connect to MQTT broker. Reason code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """
        Callback when MQTT client disconnects from broker.
        """
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker. Reason code: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """
        Callback when MQTT message is received.
        """
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.debug(f"Received message on topic '{topic}': {payload}")
            
            # Process sensor data messages
            if topic == self.topic:
                self._process_sensor_data(payload)
            # Process status messages
            elif topic == config.MQTT_STATUS_TOPIC:
                logger.info(f"Device status: {payload}")
            # Process LWT messages
            elif topic == config.MQTT_LWT_TOPIC:
                logger.warning(f"Device LWT: {payload}")
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _on_log(self, client, userdata, level, buf):
        """
        Callback for MQTT client logging.
        """
        logger.log(level, buf)
    
    def connect(self) -> bool:
        """
        Connect to MQTT broker.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to MQTT broker: {self.broker}:{self.port}")
            
            # Attempt to connect
            result = self.client.connect(self.broker, self.port, keepalive=60)
            
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info("MQTT connected!")
                # Process network events once to trigger callbacks
                self.client.loop(timeout=1.0)
                return True
            else:
                logger.error(f"MQTT connection failed. RC: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT: {e}")
    
    def _process_sensor_data(self, payload: str):
        """
        Process sensor data from MQTT message.
        
        Args:
            payload: JSON string with sensor data
        """
        try:
            data = json.loads(payload)
            
            # Extract sensor readings from nested structure
            # ESP32 sends: {"sensors": {"mq135_co2": ..., "mq136_h2s": ..., "mq137_nh3": ...}, "quality": {"level": ...}}
            sensors = data.get('sensors', {})
            quality_data = data.get('quality', {})
            
            # Extract gas sensor values from nested sensors object
            h2s = sensors.get('mq136_h2s', 0.0)
            nh3 = sensors.get('mq137_nh3', 0.0)
            co2 = sensors.get('mq135_co2', 0.0)
            temp = sensors.get('temperature', 0.0)
            humidity = sensors.get('humidity', 0.0)
            quality = quality_data.get('level', 'UNKNOWN')
            
            logger.info(f"Processed sensor data: H2S={h2s:.2f}ppm, NH3={nh3:.2f}ppm, "
                       f"CO2={co2:.2f}ppm, Temp={temp:.1f}°C, "
                       f"Humidity={humidity:.1f}%, Quality={quality}")
            
            # Save to database
            self.db.insert_sensor_reading({
                'timestamp': datetime.now(),
                'device_id': 'ESP32-Sensor',
                'temperature': temp,
                'humidity': humidity,
                'mq135_co2': co2,
                'mq136_h2s': h2s,
                'mq137_nh3': nh3,
                'quality_level': quality
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing sensor data JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")
    
    def run(self):
        """
        Run MQTT subscriber main loop.
        """
        logger.info("Starting MQTT subscriber...")
        
        # Connect to MQTT broker
        if not self.connect():
            logger.error("Failed to connect to MQTT broker. Exiting...")
            sys.exit(1)
        
        # Main loop - process network events
        try:
            while self.keep_running:
                self.client.loop(timeout=1.0)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.disconnect()
            logger.info("MQTT subscriber stopped")


def main():
    """Main entry point."""
    subscriber = MQTTSubscriber()
    subscriber.run()


if __name__ == "__main__":
    main()
