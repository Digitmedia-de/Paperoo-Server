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
            
            if printer_type == 'usb':
                vendor_id_str = self.config.get('PRINTER_VENDOR_ID', '0x04b8')
                product_id_str = self.config.get('PRINTER_PRODUCT_ID', '0x0e15')
                vendor_id = int(vendor_id_str, 16)
                product_id = int(product_id_str, 16)
                
                # Try to detect endpoints automatically
                endpoints = PrinterDetector.detect_usb_endpoints(vendor_id_str, product_id_str)
                in_ep = endpoints['in_ep']
                out_ep = endpoints['out_ep']
                
                logger.info(f"Attempting USB connection: vendor={hex(vendor_id)}, product={hex(product_id)}, in_ep={hex(in_ep)}, out_ep={hex(out_ep)}")
                
                try:
                    # First try with detected endpoints
                    self.printer = Usb(vendor_id, product_id, in_ep=in_ep, out_ep=out_ep)
                    logger.info(f"USB printer connected with detected endpoints")
                except:
                    # If that fails, try auto-detection
                    try:
                        self.printer = Usb(vendor_id, product_id)
                        logger.info(f"USB printer connected with auto-detected endpoints")
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
                self.printer = Serial(port)
            elif printer_type == 'network':
                ip = self.config.get('PRINTER_NETWORK_IP', '192.168.1.100')
                self.printer = Network(ip)
            else:
                raise ValueError(f"Unknown printer type: {printer_type}")
                
            logger.info(f"Printer initialized successfully: {printer_type}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "endpoint" in error_msg.lower():
                error_msg = f"USB endpoint error: {error_msg}. Please check your printer is connected and powered on."
            logger.error(f"Failed to initialize printer: {error_msg}")
            self.printer = None  # Reset printer on error
            return False
    
    def print_todo(self, text, priority, mqtt_handler=None, language=None):
        """Print a ToDo item with optional language override"""
        with self.lock:
            try:
                # Handle MQTT if enabled
                if mqtt_handler and self.config.get('MQTT_ENABLED', 'false').lower() == 'true':
                    if not self.printer_active:
                        # Send power on message
                        mqtt_handler.send_before_print()
                        # Wait configured seconds
                        wait_seconds = int(self.config.get('MQTT_WAIT_SECONDS', 5))
                        time.sleep(wait_seconds)
                        self.printer_active = True
                    
                    # Cancel existing timeout timer
                    if self.timeout_timer:
                        self.timeout_timer.cancel()
                
                # Initialize printer if not already done or if it was reset
                if not self.printer:
                    if not self.initialize_printer():
                        return False, "Printer initialization failed. Please check printer connection and configuration."
                
                # Format and print the ToDo with language override
                self._format_and_print(text, priority, language)
                
                # Update last print time
                self.last_print_time = datetime.now()
                
                # Set up timeout timer for MQTT
                if mqtt_handler and self.config.get('MQTT_ENABLED', 'false').lower() == 'true':
                    timeout_minutes = int(self.config.get('MQTT_TIMEOUT_MINUTES', 30))
                    self.timeout_timer = threading.Timer(
                        timeout_minutes * 60,
                        self._handle_timeout,
                        args=[mqtt_handler]
                    )
                    self.timeout_timer.start()
                
                return True, "ToDo printed successfully"
                
            except Exception as e:
                error_msg = str(e)
                # Reset printer on critical errors
                if "endpoint" in error_msg.lower() or "usb" in error_msg.lower():
                    self.printer = None  # Reset for next attempt
                    error_msg = f"USB connection error: {error_msg}. The printer will retry on next print."
                logger.error(f"Print error: {error_msg}")
                return False, f"Print error: {error_msg}"
    
    def _format_and_print(self, text, priority, language=None):
        """Format and send ToDo to printer with optional language override"""
        try:
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
        """Handle printer timeout"""
        with self.lock:
            if mqtt_handler:
                mqtt_handler.send_after_timeout()
                self.printer_active = False
                logger.info("Printer timeout - sent power off message")
    
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