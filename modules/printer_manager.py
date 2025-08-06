import os
import time
import threading
from datetime import datetime, timedelta
from escpos.printer import Usb, Serial, Network
from escpos.exceptions import Error as EscposError
import logging
from .printer_detector import PrinterDetector
from .motivation_generator import MotivationGenerator
from .translations import get_translation

logger = logging.getLogger(__name__)

class PrinterManager:
    def __init__(self, config):
        self.config = config
        self.printer = None
        self.last_print_time = None
        self.timeout_timer = None
        self.printer_active = False
        self.lock = threading.Lock()
        self.language = config.get('LANGUAGE', 'de')
        
        # Initialize motivation generator if enabled
        if config.get('MOTIVATION_ENABLED', 'false').lower() == 'true':
            api_key = config.get('OPENAI_API_KEY', '')
            model = config.get('MOTIVATION_MODEL', 'gpt-4o-mini')
            self.motivation_generator = MotivationGenerator(api_key, model, self.language)
        else:
            self.motivation_generator = None
        
    def initialize_printer(self):
        """Initialize the printer based on configuration"""
        try:
            printer_type = self.config.get('PRINTER_TYPE', 'usb')
            logger.info("="*50)
            logger.info(f"PRINTER INITIALIZATION - Type: {printer_type.upper()}")
            logger.info("="*50)
            
            if printer_type == 'usb':
                vendor_id_str = self.config.get('PRINTER_VENDOR_ID', '0x04b8')
                product_id_str = self.config.get('PRINTER_PRODUCT_ID', '0x0e15')
                vendor_id = int(vendor_id_str, 16)
                product_id = int(product_id_str, 16)
                
                logger.info(f"USB Configuration:")
                logger.info(f"  Vendor ID: {vendor_id_str} ({hex(vendor_id)})")
                logger.info(f"  Product ID: {product_id_str} ({hex(product_id)})")
                
                # Try to detect endpoints automatically
                endpoints = PrinterDetector.detect_usb_endpoints(vendor_id_str, product_id_str)
                in_ep = endpoints['in_ep']
                out_ep = endpoints['out_ep']
                
                logger.info(f"  Input Endpoint: {hex(in_ep)}")
                logger.info(f"  Output Endpoint: {hex(out_ep)}")
                logger.info(f"Attempting USB connection...")
                
                try:
                    # First try with detected endpoints
                    self.printer = Usb(vendor_id, product_id, in_ep=in_ep, out_ep=out_ep)
                    logger.info(f"✓ USB printer connected successfully with detected endpoints")
                    logger.info("="*50)
                except:
                    # If that fails, try auto-detection
                    try:
                        self.printer = Usb(vendor_id, product_id)
                        logger.info(f"✓ USB printer connected successfully with auto-detected endpoints")
                        logger.info("="*50)
                    except Exception as e:
                        # Last resort: try with different common endpoints
                        for out_ep in [0x01, 0x02, 0x03, 0x04]:
                            for in_ep in [0x81, 0x82, 0x83, 0x84]:
                                try:
                                    self.printer = Usb(vendor_id, product_id, in_ep=in_ep, out_ep=out_ep)
                                    logger.info(f"USB printer connected with endpoints in={hex(in_ep)}, out={hex(out_ep)}")
                                    break
                                except:
                                    continue
                            if self.printer:
                                break
                        if not self.printer:
                            logger.error(f"Failed to connect to USB printer with all endpoint combinations")
                            raise Exception(f"Cannot connect to USB printer (vendor={hex(vendor_id)}, product={hex(product_id)}). Please check the printer is connected and powered on.")
            elif printer_type == 'serial':
                port = self.config.get('PRINTER_SERIAL_PORT', '/dev/ttyUSB0')
                logger.info(f"Serial Configuration:")
                logger.info(f"  Port: {port}")
                logger.info(f"Attempting Serial connection...")
                self.printer = Serial(port)
                logger.info(f"✓ Serial printer connected successfully on {port}")
                logger.info("="*50)
                
            elif printer_type == 'network':
                ip = self.config.get('PRINTER_NETWORK_IP', '192.168.1.100')
                logger.info(f"Network Configuration:")
                logger.info(f"  IP Address: {ip}")
                logger.info(f"Attempting Network connection...")
                self.printer = Network(ip)
                logger.info(f"✓ Network printer connected successfully at {ip}")
                logger.info("="*50)
                
            else:
                raise ValueError(f"Unknown printer type: {printer_type}")
                
            logger.info(f"PRINTER READY - Type: {printer_type.upper()}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "endpoint" in error_msg.lower():
                error_msg = f"USB endpoint error: {error_msg}. Please check your printer is connected and powered on."
            logger.error(f"Failed to initialize printer: {error_msg}")
            self.printer = None  # Reset printer on error
            return False
    
    def print_todo(self, text, priority, mqtt_handler=None, language=None, is_retry=False):
        """Print a ToDo item with optional language override
        
        Args:
            text: The todo text to print
            priority: Priority level (1-5)
            mqtt_handler: MQTT handler instance
            language: Optional language override
            is_retry: True if this is a retry attempt (forces MQTT before_print)
        """
        with self.lock:
            # Handle MQTT BEFORE any printing attempt
            if mqtt_handler and self.config.get('MQTT_ENABLED', 'false').lower() == 'true':
                # Send before_print message if printer was inactive OR if this is a retry
                if not self.printer_active or is_retry:
                    if is_retry:
                        logger.info("Retry attempt - sending MQTT before_print message to ensure printer is ready")
                    else:
                        logger.info("Printer was idle - sending MQTT before_print message")
                    
                    mqtt_handler.send_before_print()
                    
                    # Wait configured seconds for printer to become ready
                    wait_seconds = int(self.config.get('MQTT_WAIT_SECONDS', 5))
                    logger.info(f"Waiting {wait_seconds} seconds for printer to become ready")
                    time.sleep(wait_seconds)
                    self.printer_active = True
                else:
                    logger.debug("Printer already active - skipping before_print message")
                
                # Cancel existing timeout timer (will be restarted after print)
                if self.timeout_timer:
                    self.timeout_timer.cancel()
                    logger.debug("Cancelled existing MQTT timeout timer")
            
            try:
                # Initialize printer if not already done or if it was reset
                if not self.printer:
                    if not self.initialize_printer():
                        # Still set up timeout even if print fails
                        self._setup_mqtt_timeout(mqtt_handler)
                        return False, "Printer initialization failed. Please check printer connection and configuration."
                
                # Format and print the ToDo with language override
                self._format_and_print(text, priority, language)
                
                # Update last print time
                self.last_print_time = datetime.now()
                
                # Set up timeout timer for MQTT
                self._setup_mqtt_timeout(mqtt_handler)
                
                return True, "ToDo printed successfully"
                
            except Exception as e:
                error_msg = str(e)
                # Reset printer on critical errors
                if "endpoint" in error_msg.lower() or "usb" in error_msg.lower():
                    self.printer = None  # Reset for next attempt
                    error_msg = f"USB connection error: {error_msg}. The printer will retry on next print."
                logger.error(f"Print error: {error_msg}")
                
                # Still set up timeout even if print fails (printer was powered on)
                self._setup_mqtt_timeout(mqtt_handler)
                
                return False, f"Print error: {error_msg}"
    
    def _setup_mqtt_timeout(self, mqtt_handler):
        """Set up MQTT timeout timer to send after_timeout message when idle"""
        if mqtt_handler and self.config.get('MQTT_ENABLED', 'false').lower() == 'true':
            # Cancel existing timer if any
            if self.timeout_timer:
                self.timeout_timer.cancel()
            
            timeout_minutes = float(self.config.get('MQTT_TIMEOUT_MINUTES', 30))
            logger.info(f"Starting MQTT idle timer: will send after_timeout message in {timeout_minutes} minutes if no prints occur")
            self.timeout_timer = threading.Timer(
                timeout_minutes * 60,
                self._handle_timeout,
                args=[mqtt_handler]
            )
            self.timeout_timer.start()
    
    def _format_and_print(self, text, priority, language=None):
        """Format and send ToDo to printer with optional language override"""
        try:
            logger.debug(f"Printing ToDo: '{text}' with priority {priority} in language '{language or self.language}'")
            # Get translations - use override language if provided
            lang = language if language else self.language
            
            # Set character encoding to avoid issues
            try:
                self.printer.charcode('CP858')  # Western European codepage
            except:
                pass  # If setting codepage fails, continue anyway
            
            # Start with some space at the top
            self.printer.text("\n")
            
            # Print priority stars and name only (no "Priorität:" label)
            self.printer.set(align='center', font='a', width=1, height=1, bold=True)
            # Use simple ASCII characters that work on all printers
            # Show stars with spaces for better readability
            stars = ""
            for i in range(5):
                if i < priority:
                    stars += "* "  # Filled star with space
                else:
                    stars += "- "  # Dash for empty
            priority_display = stars.strip()
            self.printer.text(f"{priority_display}\n")
            
            # Priority level names
            priority_key = f'priority_{priority}'
            priority_name = get_translation(lang, priority_key, 'Normal')
            self.printer.set(align='center', font='a', width=1, height=1, bold=False)
            self.printer.text(f"({priority_name})\n")
            
            self.printer.text("-" * 32 + "\n")
            
            # Print timestamp centered
            self.printer.set(align='center', font='a', width=1, height=1)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.printer.text(f"{timestamp}\n")
            self.printer.text("-" * 32 + "\n\n")
            
            # Print ToDo text - CENTER aligned and word-wrapped
            self.printer.set(align='center', font='a', width=1, height=1, bold=True)
            # Word wrap text for receipt printer (typically 32 chars per line for centered text)
            wrapped_lines = self._wrap_text_centered(text, 30)  # Slightly less for centered
            for line in wrapped_lines:
                self.printer.text(line + "\n")
            
            # Print footer with motivation
            self.printer.text("\n" + "-" * 32 + "\n")
            self.printer.set(align='center', font='b', width=1, height=1, bold=False)
            
            # Get motivational quote or use default
            if self.motivation_generator and self.motivation_generator.is_enabled():
                motivation = self.motivation_generator.get_motivation(text, priority, language=lang)
            else:
                motivation = get_translation(lang, 'receipt_motivation_default', 'Get it done!')
            
            self.printer.text(f"{motivation}\n")
            self.printer.text("\n\n")
            
            # Cut paper
            self.printer.cut()
            
        except Exception as e:
            raise Exception(f"Formatting error: {str(e)}")
    
    def _wrap_text(self, text, width):
        """Wrap text to fit printer width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines)
    
    def _wrap_text_centered(self, text, width):
        """Wrap text to fit printer width and return as list of lines for centering"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            # Check if adding this word would exceed the width
            if current_length + len(word) + (1 if current_line else 0) <= width:
                current_line.append(word)
                current_length += len(word) + (1 if current_line else 0)
            else:
                # Save current line and start new one
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        # Add the last line
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _handle_timeout(self, mqtt_handler):
        """Handle printer idle timeout - send after_timeout message"""
        with self.lock:
            logger.info(f"MQTT idle timeout reached after {self.config.get('MQTT_TIMEOUT_MINUTES')} minutes - sending after_timeout message")
            if mqtt_handler:
                success = mqtt_handler.send_after_timeout()
                if success:
                    logger.info("MQTT after_timeout message sent successfully")
                else:
                    logger.warning("Failed to send MQTT after_timeout message")
                self.printer_active = False
            self.timeout_timer = None  # Clear the timer reference
    
    def cleanup(self):
        """Clean up printer resources"""
        with self.lock:
            if self.timeout_timer:
                self.timeout_timer.cancel()
            if self.printer:
                try:
                    self.printer.close()
                except:
                    pass