"""
MQTT Client Module for Meat Quality Monitoring System
Handles MQTT communication with ESP32 sensor nodes
Compatible with paho-mqtt 1.6.x and 2.1.0
"""

import json
import logging
import threading
import time
from typing import Callable, Optional, Dict, Any
import paho.mqtt.client as mqtt
import config
import db_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MQTTClient:
    """
    MQTT client for receiving sensor data from ESP32.
    Handles connection, subscription, and message processing.
    Compatible with paho-mqtt 1.6.x and 2.1.0
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
        self.keep_running = True
        self._started = False  # Flag to prevent multiple start() calls
        self._loop_started = False  # Flag to prevent multiple loop_start() calls
        
        # Create MQTT client with paho-mqtt 1.6.x API
        self.client = mqtt.Client(
            client_id="MeatMonitor-Pi",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            transport="tcp"
        )
        self.client.username_pw_set(self.username, self.password)
        
        self.connected = False
        self.reconnect_delay = config.MQTT_RECONNECT_DELAY
        self.keep_running = True
        
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
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
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
        Connect to MQTT broker.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to MQTT broker: {self.broker}:{self.port}")
            
            # Set username and password before connecting
            self.client.username_pw_set(self.username, self.password)
            
            # Attempt to connect (connect() doesn't accept username/password as args)
            result = self.client.connect(self.broker, self.port, keepalive=60)
            
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info("MQTT connected!")
                # Set connected flag immediately - callback will also set it
                self.connected = True
                return True
            else:
                logger.error(f"MQTT connection failed. RC: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.keep_running = False
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT: {e}")
    
    def start(self):
        """
        Start MQTT client in a separate thread.
        Handles automatic reconnection only when connection is lost.
        Only starts once - subsequent calls are ignored.
        """
        # Prevent multiple threads from being started
        if self._started:
            logger.warning("MQTT client already started - ignoring duplicate start() call")
            return
        
        self._started = True
        
        def _run():
            while self.keep_running:
                if not self.connected:
                    logger.info("Attempting to connect to MQTT broker...")
                    if self.connect():
                        # Start loop to process incoming messages (only once)
                        if not self._loop_started:
                            self.client.loop_start()
                            self._loop_started = True
                        logger.info("MQTT connection established")
                    else:
                        logger.warning(f"MQTT connection failed, retrying in {self.reconnect_delay} seconds...")
                
                # Sleep briefly to prevent tight loop
                # loop_start() handles message processing in background
                time.sleep(0.1)
                
                # Only sleep longer when not connected
                if not self.connected:
                    time.sleep(self.reconnect_delay)
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        logger.info("MQTT client thread started")
    
    def stop(self):
        """Stop MQTT client."""
        self.keep_running = False
        self._started = False
        self._loop_started = False
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT: {e}")
    
    def set_message_callback(self, callback: Callable):
        """
        Set callback for received messages.
        
        Args:
            callback: Function to call when message received
        """
        self.on_message_callback = callback
    
    def set_connect_callback(self, callback: Callable):
        """
        Set callback for connection events.
        
        Args:
            callback: Function to call when connected
        """
        self.on_connect_callback = callback
    
    def set_disconnect_callback(self, callback: Callable):
        """
        Set callback for disconnection events.
        
        Args:
            callback: Function to call when disconnected
        """
        self.on_disconnect_callback = callback
    
    def is_connected(self) -> bool:
        """
        Check if MQTT client is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.connected


# Singleton instance for application
_mqtt_client: Optional[MQTTClient] = None


def get_mqtt_client(session_state=None) -> MQTTClient:
    """
    Get singleton MQTT client instance.
    Uses Streamlit session state to persist across reruns.
    
    Args:
        session_state: Streamlit session_state object (optional)
    
    Returns:
        MQTTClient instance
    """
    # Try to use Streamlit session state if provided
    if session_state is not None and hasattr(session_state, '_mqtt_client'):
        if session_state._mqtt_client is None:
            session_state._mqtt_client = MQTTClient()
        return session_state._mqtt_client
    
    # Fallback to global variable for non-Streamlit usage
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = MQTTClient()
    return _mqtt_client


def reset_mqtt_client(session_state=None):
    """Reset singleton MQTT client instance."""
    # Try to use Streamlit session state if provided
    if session_state is not None and hasattr(session_state, '_mqtt_client'):
        if session_state._mqtt_client is not None:
            session_state._mqtt_client.stop()
        session_state._mqtt_client = None
        return
    
    # Fallback to global variable for non-Streamlit usage
    global _mqtt_client
    if _mqtt_client is not None:
        _mqtt_client.stop()
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
