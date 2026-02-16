"""
Simple MQTT client for receiving sensor data from ESP32.
Uses persistent background loop for better Streamlit compatibility.
Compatible with paho-mqtt 2.1.0
"""

import logging
import time
import json
from typing import Optional, Callable
import paho.mqtt.client as mqtt
import config
import db_manager
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class SimpleMQTTClient:
    """
    Simple MQTT client using persistent background loop.
    Designed for Streamlit compatibility - maintains connection in background.
    """
    
    def __init__(self, broker: str = None, port: int = None,
                 username: str = None, password: str = None):
        """
        Initialize MQTT client.
        
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
        self.reconnect_delay = config.MQTT_RECONNECT_DELAY
        
        # Create MQTT client with paho-mqtt 2.1.0 API
        self.client = mqtt.Client(
            client_id="MeatMonitor-Pi-Dashboard",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            transport="tcp"
        )
        self.client.username_pw_set(self.username, self.password)
        
        self.connected = False
        self.last_message = None
        self._loop_started = False  # Track if loop_start has been called
        
        # Callbacks
        self.on_message_callback: Optional[Callable] = None
        self.on_connect_callback: Optional[Callable] = None
        self.on_disconnect_callback: Optional[Callable] = None
        
        # Database manager
        self.db = db_manager.get_db_manager()
        
        # Setup MQTT callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_log = self._on_log
        
        logger.info(f"MQTT client initialized for broker: {self.broker}:{self.port}")
    
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
            
            if self.on_connect_callback:
                self.on_connect_callback()
        else:
            logger.error(f"Failed to connect to MQTT broker. Reason code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc, properties, reason_code=None):
        """
        Callback when MQTT client disconnects from broker.
        """
        self.connected = False
        
        if self.on_disconnect_callback:
            self.on_disconnect_callback()
        else:
            logger.warning(f"Disconnected from MQTT broker unexpectedly. Reason code: {rc}")
    
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
            
            # Store last message for polling
            self.last_message = payload
            
            # Call custom callback if set
            if self.on_message_callback:
                self.on_message_callback(topic, payload)
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _on_log(self, client, userdata, level, buf):
        """
        Callback for MQTT client logging.
        """
        logger.log(level, buf)
    
    def connect(self) -> bool:
        """
        Connect to MQTT broker and start background loop.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Check if already connected
            if hasattr(self.client, 'is_connected'):
                if self.client.is_connected():
                    logger.debug("MQTT client already connected, skipping connection attempt")
                    self.connected = True
                    return True
            
            logger.info(f"Connecting to MQTT broker: {self.broker}:{self.port}")
            
            # Attempt to connect
            result = self.client.connect(self.broker, self.port, keepalive=60)
            
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info("MQTT connected!")
                
                # Start background loop if not already started
                if not self._loop_started:
                    self.client.loop_start()
                    self._loop_started = True
                    logger.info("MQTT background loop started")
                
                # Process network events once to trigger callbacks
                self.client.loop(timeout=1.0)
                self.connected = True
                return True
            else:
                logger.error(f"MQTT connection failed. RC: {result}")
                self.connected = False
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        try:
            if self._loop_started:
                self.client.loop_stop()
                self._loop_started = False
                logger.info("MQTT background loop stopped")
            self.client.disconnect()
            self.connected = False
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT: {e}")
    
    def poll(self, timeout=0.1) -> bool:
        """
        Poll for MQTT messages - lightweight version for Streamlit.
        Just checks connection status and processes any pending messages.
        
        Args:
            timeout: Time to wait for messages in seconds (short timeout for Streamlit)
        
        Returns:
            True if connected, False otherwise
        """
        # Check actual paho-mqtt client connection state
        is_actually_connected = self.client.is_connected()
        
        # Sync our cached state with actual state
        if is_actually_connected != self.connected:
            self.connected = is_actually_connected
            if is_actually_connected:
                logger.info("MQTT connection state: CONNECTED")
            else:
                logger.warning("MQTT connection state: DISCONNECTED")
        
        if not self.connected:
            if not self.connect():
                logger.warning(f"MQTT connection failed, retrying in {self.reconnect_delay} seconds...")
                return False
            # After successful connect, sync state again
            self.connected = self.client.is_connected()
            return self.connected
        
        # Just check connection status (background loop handles network events)
        # When using loop_start(), we don't need to call client.loop()
        return self.connected
    
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
    
    def is_connected(self) -> bool:
        """Check if MQTT client is connected."""
        return self.connected
    
    def set_message_callback(self, callback: Callable):
        """Set callback for received messages."""
        self.on_message_callback = callback
    
    def set_connect_callback(self, callback: Callable):
        """Set callback for connection events."""
        self.on_connect_callback = callback
    
    def set_disconnect_callback(self, callback: Callable):
        """Set callback for disconnection events."""
        self.on_disconnect_callback = callback


# Singleton instance for application
_mqtt_client: Optional[SimpleMQTTClient] = None


def get_simple_mqtt_client(session_state=None) -> SimpleMQTTClient:
    """
    Get singleton MQTT client instance.
    Uses Streamlit session state to persist across reruns.
    
    Args:
        session_state: Streamlit session_state object (optional)
    
    Returns:
        SimpleMQTTClient instance
    """
    # Try to use Streamlit session state if provided
    if session_state is not None and hasattr(session_state, '_mqtt_client'):
        if session_state._mqtt_client is None:
            session_state._mqtt_client = SimpleMQTTClient()
        return session_state._mqtt_client
    
    # Fallback to global variable for non-Streamlit usage
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = SimpleMQTTClient()
    return _mqtt_client


def reset_mqtt_client(session_state=None):
    """Reset singleton MQTT client instance."""
    # Try to use Streamlit session state if provided
    if session_state is not None and hasattr(session_state, '_mqtt_client'):
        if session_state._mqtt_client is not None:
            session_state._mqtt_client.disconnect()
        session_state._mqtt_client = None
        return
    
    # Fallback to global variable for non-Streamlit usage
    global _mqtt_client
    if _mqtt_client is not None:
        _mqtt_client.disconnect()
    _mqtt_client = None


def map_quality_level(esp_quality: str) -> str:
    """
    Map ESP32 quality level to Pi dashboard status.
    
    Args:
        esp_quality: Quality level from ESP32 (EXCELLENT, GOOD, FAIR, POOR, SPOILED)
    
    Returns:
        Mapped quality status for Pi dashboard (SAFE, WARNING, SPOILED, CRITICAL)
    """
    return config.QUALITY_LEVEL_MAP.get(esp_quality, "WARNING")


def determine_gas_status(h2s: float, nh3: float, co2: float) -> str:
    """
    Determine gas status based on sensor readings.
    
    Args:
        h2s: H2S reading in ppm
        nh3: NH3 reading in ppm
        co2: CO2 reading in ppm
    
    Returns:
        Gas status: LOW, HIGH, or CRITICAL
    """
    # Check for critical levels
    if (h2s >= config.H2S_CRITICAL_THRESHOLD or 
        nh3 >= config.NH3_CRITICAL_THRESHOLD or 
        co2 >= config.CO2_CRITICAL_THRESHOLD):
        return "CRITICAL"
    
    # Check for warning levels
    if (h2s >= config.H2S_WARNING_THRESHOLD or 
        nh3 >= config.NH3_WARNING_THRESHOLD or 
        co2 >= config.CO2_WARNING_THRESHOLD):
        return "HIGH"
    
    return "LOW"
