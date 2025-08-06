import subprocess
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class PrinterDetector:
    """Detect and manage available printers"""
    
    # Known printer vendors and their IDs
    KNOWN_PRINTERS = {
        '04b8': 'Epson',
        '0519': 'Star Micronics',
        '1504': 'Bixolon',
        '0dd4': 'Citizen',
        '0416': 'Winbond',
        '067b': 'Prolific',  # USB-Serial adapters
        '0403': 'FTDI',      # USB-Serial adapters
    }
    
    @staticmethod
    def detect_usb_endpoints(vendor_id: str, product_id: str) -> Dict:
        """Try to detect USB endpoints for a specific printer"""
        import usb.core
        import usb.util
        
        try:
            # Convert hex string to int
            vid = int(vendor_id, 16) if isinstance(vendor_id, str) else vendor_id
            pid = int(product_id, 16) if isinstance(product_id, str) else product_id
            
            # Find the device
            dev = usb.core.find(idVendor=vid, idProduct=pid)
            if dev is None:
                return {'in_ep': 0x81, 'out_ep': 0x01}  # Default values
            
            # Get the active configuration
            cfg = dev.get_active_configuration()
            
            # Find the first interface
            intf = cfg[(0, 0)]
            
            # Find endpoints
            in_ep = None
            out_ep = None
            
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    if in_ep is None:
                        in_ep = ep.bEndpointAddress
                else:
                    if out_ep is None:
                        out_ep = ep.bEndpointAddress
            
            return {
                'in_ep': in_ep or 0x81,
                'out_ep': out_ep or 0x01
            }
        except:
            # Return default values if detection fails
            return {'in_ep': 0x81, 'out_ep': 0x01}
    
    @staticmethod
    def detect_usb_printers() -> List[Dict]:
        """Detect USB printers connected to the system"""
        printers = []
        
        try:
            # Run lsusb command
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("Failed to run lsusb command")
                return printers
            
            # Parse lsusb output
            # Format: Bus 001 Device 004: ID 04b8:0e15 Seiko Epson Corp.
            pattern = r'Bus (\d+) Device (\d+): ID ([0-9a-f]{4}):([0-9a-f]{4})\s+(.+)'
            
            for line in result.stdout.split('\n'):
                match = re.match(pattern, line)
                if match:
                    bus, device, vendor_id, product_id, description = match.groups()
                    
                    # Check if it might be a printer
                    is_printer = False
                    if vendor_id in PrinterDetector.KNOWN_PRINTERS:
                        is_printer = True
                    elif any(keyword in description.lower() for keyword in ['print', 'receipt', 'pos', 'tsp', 'tm-']):
                        is_printer = True
                    
                    if is_printer:
                        printers.append({
                            'type': 'usb',
                            'vendor_id': f'0x{vendor_id}',
                            'product_id': f'0x{product_id}',
                            'vendor_name': PrinterDetector.KNOWN_PRINTERS.get(vendor_id, 'Unknown'),
                            'description': description.strip(),
                            'bus': bus,
                            'device': device,
                            'identifier': f'usb_{vendor_id}_{product_id}'
                        })
                        logger.info(f"Found USB printer: {description} ({vendor_id}:{product_id})")
            
        except FileNotFoundError:
            logger.warning("lsusb command not found - trying alternative method")
            printers.extend(PrinterDetector._detect_usb_sysfs())
        except Exception as e:
            logger.error(f"Error detecting USB printers: {str(e)}")
        
        return printers
    
    @staticmethod
    def _detect_usb_sysfs() -> List[Dict]:
        """Alternative USB detection using sysfs (for systems without lsusb)"""
        printers = []
        import os
        import glob
        
        try:
            # Check /sys/bus/usb/devices/
            for device_path in glob.glob('/sys/bus/usb/devices/*/'):
                try:
                    vendor_file = os.path.join(device_path, 'idVendor')
                    product_file = os.path.join(device_path, 'idProduct')
                    manufacturer_file = os.path.join(device_path, 'manufacturer')
                    product_name_file = os.path.join(device_path, 'product')
                    
                    if os.path.exists(vendor_file) and os.path.exists(product_file):
                        with open(vendor_file, 'r') as f:
                            vendor_id = f.read().strip()
                        with open(product_file, 'r') as f:
                            product_id = f.read().strip()
                        
                        description = ""
                        if os.path.exists(manufacturer_file):
                            with open(manufacturer_file, 'r') as f:
                                description = f.read().strip() + " "
                        if os.path.exists(product_name_file):
                            with open(product_name_file, 'r') as f:
                                description += f.read().strip()
                        
                        # Check if it's a printer
                        if vendor_id in PrinterDetector.KNOWN_PRINTERS or \
                           any(keyword in description.lower() for keyword in ['print', 'receipt', 'pos']):
                            printers.append({
                                'type': 'usb',
                                'vendor_id': f'0x{vendor_id}',
                                'product_id': f'0x{product_id}',
                                'vendor_name': PrinterDetector.KNOWN_PRINTERS.get(vendor_id, 'Unknown'),
                                'description': description or f"USB Device {vendor_id}:{product_id}",
                                'identifier': f'usb_{vendor_id}_{product_id}'
                            })
                except:
                    continue
        except Exception as e:
            logger.error(f"Error reading sysfs: {str(e)}")
        
        return printers
    
    @staticmethod
    def detect_serial_printers() -> List[Dict]:
        """Detect serial port printers"""
        printers = []
        import glob
        import os
        
        # Common serial port patterns
        serial_patterns = [
            '/dev/ttyUSB*',
            '/dev/ttyACM*',
            '/dev/ttyS*',
            '/dev/serial/by-id/*'
        ]
        
        for pattern in serial_patterns:
            for port in glob.glob(pattern):
                if os.path.exists(port):
                    # Get more info about the port if possible
                    description = "Serial Port"
                    if 'by-id' in port:
                        description = os.path.basename(port).replace('_', ' ')
                    
                    printers.append({
                        'type': 'serial',
                        'port': port,
                        'description': f"{description} ({port})",
                        'identifier': f'serial_{port.replace("/", "_")}'
                    })
                    logger.info(f"Found serial port: {port}")
        
        return printers
    
    @staticmethod
    def detect_network_printers() -> List[Dict]:
        """Detect network printers (basic implementation)"""
        printers = []
        
        # This is a placeholder - in production you might want to:
        # - Scan local network for port 9100 (RAW printing)
        # - Use mDNS/Bonjour to find printers
        # - Check CUPS for network printers
        
        # For now, just return empty or configured printers
        return printers
    
    @staticmethod
    def detect_all_printers() -> Dict[str, List[Dict]]:
        """Detect all available printers"""
        return {
            'usb': PrinterDetector.detect_usb_printers(),
            'serial': PrinterDetector.detect_serial_printers(),
            'network': PrinterDetector.detect_network_printers()
        }
    
    @staticmethod
    def save_printer_config(printer_config: Dict, env_path: str = '.env') -> bool:
        """Save selected printer configuration to .env file"""
        try:
            # Read current .env
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Update printer configuration
            new_lines = []
            printer_type_written = False
            
            for line in lines:
                # Skip old printer configuration lines
                if line.startswith('PRINTER_TYPE='):
                    new_lines.append(f"PRINTER_TYPE={printer_config['type']}\n")
                    printer_type_written = True
                elif line.startswith('PRINTER_VENDOR_ID=') and printer_config['type'] == 'usb':
                    new_lines.append(f"PRINTER_VENDOR_ID={printer_config['vendor_id']}\n")
                elif line.startswith('PRINTER_PRODUCT_ID=') and printer_config['type'] == 'usb':
                    new_lines.append(f"PRINTER_PRODUCT_ID={printer_config['product_id']}\n")
                elif line.startswith('PRINTER_SERIAL_PORT=') and printer_config['type'] == 'serial':
                    new_lines.append(f"PRINTER_SERIAL_PORT={printer_config['port']}\n")
                elif line.startswith('PRINTER_NETWORK_IP=') and printer_config['type'] == 'network':
                    new_lines.append(f"PRINTER_NETWORK_IP={printer_config['ip']}\n")
                else:
                    new_lines.append(line)
            
            # Write back to .env
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            logger.info(f"Saved printer configuration: {printer_config}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save printer configuration: {str(e)}")
            return False