import json
import logging
import paho.mqtt.client as mqtt
from typing import Optional

logger = logging.getLogger(__name__)

class MQTTHandler:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.connected = False
        
        if self.config.get('MQTT_ENABLED', 'false').lower() == 'true':
            self.initialize_mqtt()
    
    def initialize_mqtt(self):
        """Initialize MQTT client"""
        try:
            self.client = mqtt.Client(client_id=f"todo_printer_{id(self)}")
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Set authentication if provided
            username = self.config.get('MQTT_USERNAME', '')
            password = self.config.get('MQTT_PASSWORD', '')
            if username and password:
                self.client.username_pw_set(username, password)
            
            # Connect to broker
            broker = self.config.get('MQTT_BROKER', 'localhost')
            port = int(self.config.get('MQTT_PORT', 1883))
            
            self.client.connect(broker, port, 60)
            self.client.loop_start()
            
            logger.info(f"MQTT client initialized - connecting to {broker}:{port}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MQTT: {str(e)}")
            self.client = None
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker successfully")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when client disconnects from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection. Return code: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        logger.debug(f"MQTT message received - Topic: {msg.topic}, Payload: {msg.payload}")
    
    def send_before_print(self):
        """Send MQTT message before printing"""
        if not self.client or not self.connected:
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
            
            self.client.publish(topic, payload)
            logger.info(f"Sent MQTT before_print message to topic: {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send MQTT before_print message: {str(e)}")
            return False
    
    def send_after_timeout(self):
        """Send MQTT message after timeout"""
        if not self.client or not self.connected:
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
            
            self.client.publish(topic, payload)
            logger.info(f"Sent MQTT after_timeout message to topic: {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send MQTT after_timeout message: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up MQTT client"""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("MQTT client disconnected and cleaned up")
            except Exception as e:
                logger.error(f"Error during MQTT cleanup: {str(e)}")