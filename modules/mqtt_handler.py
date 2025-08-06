import json
import logging
import time
import threading
import paho.mqtt.client as mqtt
from typing import Optional

logger = logging.getLogger(__name__)

class MQTTHandler:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.connected = False
        self.connecting = False
        self.should_reconnect = True
        self.reconnect_thread = None
        self.reconnect_delay = 5  # Start with 5 seconds
        self.max_reconnect_delay = 60  # Max 60 seconds between attempts
        
        if self.config.get('MQTT_ENABLED', 'false').lower() == 'true':
            self.initialize_mqtt()
    
    def initialize_mqtt(self):
        """Initialize MQTT client and start connection"""
        try:
            # Create unique client ID
            # Use CallbackAPIVersion.VERSION1 for compatibility
            try:
                # For newer versions of paho-mqtt (>=2.0.0)
                from paho.mqtt.client import CallbackAPIVersion
                self.client = mqtt.Client(
                    callback_api_version=CallbackAPIVersion.VERSION1,
                    client_id=f"paperoo_{id(self)}"
                )
            except (ImportError, TypeError):
                # For older versions of paho-mqtt (<2.0.0)
                self.client = mqtt.Client(client_id=f"paperoo_{id(self)}")
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_publish = self._on_publish
            
            # Set authentication if provided
            username = self.config.get('MQTT_USERNAME', '')
            password = self.config.get('MQTT_PASSWORD', '')
            if username and password:
                self.client.username_pw_set(username, password)
            
            # Get broker details
            self.broker = self.config.get('MQTT_BROKER', 'localhost')
            self.port = int(self.config.get('MQTT_PORT', 1883))
            
            print(f"MQTT: Initializing connection to {self.broker}:{self.port} (user: {username if username else 'none'})")
            logger.info(f"MQTT initialized for {self.broker}:{self.port} with username: {username if username else 'none'}")
            
            # Start connection loop
            self.client.loop_start()
            
            # Attempt initial connection
            self._attempt_connection()
            
        except Exception as e:
            logger.error(f"Failed to initialize MQTT: {str(e)}")
            self.client = None
    
    def _attempt_connection(self):
        """Attempt to connect to MQTT broker"""
        if self.connecting or self.connected:
            return
        
        self.connecting = True
        try:
            print(f"MQTT: Attempting connection to {self.broker}:{self.port}")
            logger.info(f"Attempting MQTT connection to {self.broker}:{self.port}")
            self.client.connect_async(self.broker, self.port, 60)
            
            # Wait for connection with timeout
            timeout = 10  # seconds
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.connected:
                # Connection success is logged in _on_connect callback
                self.reconnect_delay = 5  # Reset delay on successful connection
            else:
                print(f"MQTT: Connection timeout after {timeout} seconds to {self.broker}:{self.port}")
                logger.warning(f"MQTT connection timeout after {timeout} seconds to {self.broker}:{self.port}")
                # Start reconnection thread if needed
                if self.should_reconnect and not self.reconnect_thread:
                    self._start_reconnect_thread()
                    
        except Exception as e:
            logger.error(f"MQTT connection attempt failed: {str(e)}")
            if self.should_reconnect and not self.reconnect_thread:
                self._start_reconnect_thread()
        finally:
            self.connecting = False
    
    def _start_reconnect_thread(self):
        """Start background thread for reconnection attempts"""
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            return
        
        self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self.reconnect_thread.start()
    
    def _reconnect_loop(self):
        """Background loop to attempt reconnection"""
        while self.should_reconnect and not self.connected:
            logger.info(f"MQTT reconnection attempt in {self.reconnect_delay} seconds...")
            time.sleep(self.reconnect_delay)
            
            if not self.should_reconnect:
                break
                
            if not self.connected and not self.connecting:
                self._attempt_connection()
                
                # Exponential backoff with max delay
                if not self.connected:
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to broker"""
        if rc == 0:
            self.connected = True
            self.connecting = False
            print("="*50)
            print(f"✓ MQTT CONNECTED to {self.broker}:{self.port}")
            print("="*50)
            logger.info("="*50)
            logger.info(f"✓ MQTT CONNECTED to {self.broker}:{self.port}")
            logger.info("="*50)
            
            # Subscribe to any topics if needed
            # Example: client.subscribe("paperoo/commands")
            
        else:
            self.connected = False
            self.connecting = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier", 
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = error_messages.get(rc, f"Unknown error code: {rc}")
            print(f"MQTT ERROR: {error_msg}")
            logger.error(f"Failed to connect to MQTT broker: {error_msg}")
            
            # Start reconnection if needed
            if self.should_reconnect:
                self._start_reconnect_thread()
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when client disconnects from broker"""
        self.connected = False
        self.connecting = False
        
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection. Return code: {rc}")
            # Attempt reconnection for unexpected disconnects
            if self.should_reconnect:
                logger.info("Starting MQTT reconnection process...")
                self._start_reconnect_thread()
        else:
            logger.info("MQTT client disconnected normally")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        logger.debug(f"MQTT message received - Topic: {msg.topic}, Payload: {msg.payload}")
    
    def _on_publish(self, client, userdata, mid):
        """Callback for when a message is published"""
        print(f"MQTT >>> Message {mid} delivered to broker")
        logger.debug(f"MQTT message {mid} published successfully")
    
    def ensure_connected(self):
        """Ensure MQTT is connected, attempt connection if not"""
        if not self.client:
            return False
            
        if not self.connected and not self.connecting:
            self._attempt_connection()
            
        return self.connected
    
    def send_before_print(self):
        """Send MQTT message before printing"""
        if not self.ensure_connected():
            logger.warning("MQTT client not connected - skipping before_print message")
            return False
        
        try:
            topic = self.config.get('MQTT_TOPIC_BEFORE_PRINT', 'printer/before_print')
            payload = self.config.get('MQTT_PAYLOAD_BEFORE_PRINT', '{"action": "power_on"}')
            
            # Parse payload if it's JSON
            try:
                payload_dict = json.loads(payload)
                payload = json.dumps(payload_dict)
            except:
                # Use payload as-is if not valid JSON
                pass
            
            # Ensure we're using string payload
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            
            print(f"MQTT >>> Publishing to topic '{topic}' with QoS 1")
            print(f"MQTT >>> Payload type: {type(payload)}, content: {payload}")
            
            result = self.client.publish(topic, payload, qos=1, retain=False)
            
            # Wait for message to be sent
            result.wait_for_publish(timeout=5.0)
            
            if result.is_published():
                print(f"MQTT >>> ✓ Successfully published to {topic}: {payload}")
                print(f"MQTT >>> Message ID: {result.mid}")
                logger.info(f"Sent MQTT before_print message to topic: {topic}")
                return True
            else:
                print(f"MQTT >>> ✗ Failed to publish, rc={result.rc}")
                logger.error(f"Failed to publish MQTT message, error code: {result.rc}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send MQTT before_print message: {str(e)}")
            return False
    
    def send_after_timeout(self):
        """Send MQTT message after timeout"""
        if not self.ensure_connected():
            logger.warning("MQTT client not connected - skipping after_timeout message")
            return False
        
        try:
            topic = self.config.get('MQTT_TOPIC_AFTER_TIMEOUT', 'printer/after_timeout')
            payload = self.config.get('MQTT_PAYLOAD_AFTER_TIMEOUT', '{"action": "power_off"}')
            
            # Parse payload if it's JSON
            try:
                payload_dict = json.loads(payload)
                payload = json.dumps(payload_dict)
            except:
                # Use payload as-is if not valid JSON
                pass
            
            # Ensure we're using string payload
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            
            print(f"MQTT >>> Publishing TIMEOUT to topic '{topic}' with QoS 1")
            print(f"MQTT >>> Payload type: {type(payload)}, content: {payload}")
            
            result = self.client.publish(topic, payload, qos=1, retain=False)
            
            # Wait for message to be sent
            result.wait_for_publish(timeout=5.0)
            
            if result.is_published():
                print(f"MQTT >>> ✓ Successfully published timeout to {topic}: {payload}")
                print(f"MQTT >>> Message ID: {result.mid}")
                logger.info(f"Sent MQTT after_timeout message to topic: {topic}")
                return True
            else:
                print(f"MQTT >>> ✗ Failed to publish timeout, rc={result.rc}")
                logger.error(f"Failed to publish MQTT message, error code: {result.rc}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send MQTT after_timeout message: {str(e)}")
            return False
    
    def reconnect(self):
        """Force reconnection to MQTT broker"""
        if self.connected:
            logger.info("MQTT already connected")
            return
            
        logger.info("Forcing MQTT reconnection...")
        self._attempt_connection()
    
    def cleanup(self):
        """Clean up MQTT client"""
        self.should_reconnect = False  # Stop reconnection attempts
        
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("MQTT client disconnected and cleaned up")
            except Exception as e:
                logger.error(f"Error during MQTT cleanup: {str(e)}")