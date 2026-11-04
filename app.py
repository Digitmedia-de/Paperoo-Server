import os
import json
import logging
import subprocess
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from modules.printer_manager import PrinterManager
from modules.mqtt_handler import MQTTHandler
from modules.auth import AuthManager
from modules.printer_detector import PrinterDetector
from modules.translations import get_all_translations
from modules.database import TodoDatabase
from modules.print_queue import PrintQueueManager
from modules.session_manager import SessionManager
import atexit
import threading
import time
from pathlib import Path
from datetime import timedelta

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Force reconfiguration of logging
)
logger = logging.getLogger(__name__)

# Set specific log levels for modules
logging.getLogger('modules.mqtt_handler').setLevel(logging.INFO)
logging.getLogger('modules.printer_manager').setLevel(logging.INFO)

APP_VERSION = '1.0.5'
PRINT_TYPES = {'todo', 'list', 'note', 'quote', 'image', 'qr', 'receipt'}
MOTIVATION_PROVIDERS = {'openai', 'anthropic', 'openrouter', 'local'}
SERVER_ROOT = Path(__file__).resolve().parent
UPDATE_SCRIPT = SERVER_ROOT / 'update.sh'
UPDATE_STATUS_PATH = SERVER_ROOT / 'logs' / 'update-status.json'
UPDATE_LOG_PATH = SERVER_ROOT / 'logs' / 'update-manual.log'

# Initialize Flask app
app = Flask(__name__)
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    raise RuntimeError('SECRET_KEY must be set in the environment or .env file')
app.config['SECRET_KEY'] = secret_key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Initialize components
config = {
    'PRINTER_TYPE': os.getenv('PRINTER_TYPE', 'usb'),
    'PRINTER_VENDOR_ID': os.getenv('PRINTER_VENDOR_ID', '0x04b8'),
    'PRINTER_PRODUCT_ID': os.getenv('PRINTER_PRODUCT_ID', '0x0e15'),
    'PRINTER_SERIAL_PORT': os.getenv('PRINTER_SERIAL_PORT', '/dev/ttyUSB0'),
    'PRINTER_NETWORK_IP': os.getenv('PRINTER_NETWORK_IP', '192.168.1.100'),
    'PRINT_IMAGE_WIDTH': os.getenv('PRINT_IMAGE_WIDTH', '384'),
    'MQTT_ENABLED': os.getenv('MQTT_ENABLED', 'false'),
    'MQTT_BROKER': os.getenv('MQTT_BROKER', 'localhost'),
    'MQTT_PORT': os.getenv('MQTT_PORT', '1883'),
    'MQTT_USERNAME': os.getenv('MQTT_USERNAME', ''),
    'MQTT_PASSWORD': os.getenv('MQTT_PASSWORD', ''),
    'MQTT_TOPIC_BEFORE_PRINT': os.getenv('MQTT_TOPIC_BEFORE_PRINT', 'printer/before_print'),
    'MQTT_PAYLOAD_BEFORE_PRINT': os.getenv('MQTT_PAYLOAD_BEFORE_PRINT', '{"action": "power_on"}'),
    'MQTT_WAIT_SECONDS': os.getenv('MQTT_WAIT_SECONDS', '5'),
    'MQTT_TIMEOUT_MINUTES': os.getenv('MQTT_TIMEOUT_MINUTES', '30'),
    'MQTT_TOPIC_AFTER_TIMEOUT': os.getenv('MQTT_TOPIC_AFTER_TIMEOUT', 'printer/after_timeout'),
    'MQTT_PAYLOAD_AFTER_TIMEOUT': os.getenv('MQTT_PAYLOAD_AFTER_TIMEOUT', '{"action": "power_off"}'),
    'MOTIVATION_ENABLED': os.getenv('MOTIVATION_ENABLED', 'false'),
    'MOTIVATION_PROVIDER': os.getenv('MOTIVATION_PROVIDER', 'openai'),
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
    'OPENAI_BASE_URL': os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1/chat/completions'),
    'OPENAI_MODEL': os.getenv('OPENAI_MODEL', os.getenv('MOTIVATION_MODEL', 'gpt-4o-mini')),
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY', ''),
    'ANTHROPIC_BASE_URL': os.getenv('ANTHROPIC_BASE_URL', 'https://api.anthropic.com/v1/messages'),
    'ANTHROPIC_MODEL': os.getenv('ANTHROPIC_MODEL', 'claude-3-5-haiku-latest'),
    'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY', ''),
    'OPENROUTER_BASE_URL': os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1/chat/completions'),
    'OPENROUTER_MODEL': os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini'),
    'LOCAL_BASE_URL': os.getenv('LOCAL_BASE_URL', 'http://localhost:11434/v1/chat/completions'),
    'LOCAL_MODEL': os.getenv('LOCAL_MODEL', 'llama3.2'),
    'LANGUAGE': os.getenv('LANGUAGE', 'de'),
    'WEB_AUTH_ENABLED': os.getenv('WEB_AUTH_ENABLED', 'false'),
    'WEB_USERNAME': os.getenv('WEB_USERNAME', ''),
    'WEB_PASSWORD': os.getenv('WEB_PASSWORD', ''),
    'WEB_PASSWORD_HASH': os.getenv('WEB_PASSWORD_HASH', ''),
    'WEB_SESSION_TIMEOUT': os.getenv('WEB_SESSION_TIMEOUT', '1440'),
    'WEB_REMEMBER_ME_DAYS': os.getenv('WEB_REMEMBER_ME_DAYS', '30'),
    'WEB_IP_WHITELIST_ENABLED': os.getenv('WEB_IP_WHITELIST_ENABLED', 'false'),
    'WEB_IP_WHITELIST': os.getenv('WEB_IP_WHITELIST', '192.168.0.0/16,10.0.0.0/8,127.0.0.1'),
}

# Initialize managers
printer_manager = PrinterManager(config)
mqtt_handler = MQTTHandler(config) if config['MQTT_ENABLED'].lower() == 'true' else None
auth_manager = AuthManager(os.getenv('API_KEY'))

# Initialize database and queue manager
todo_db = TodoDatabase('todos.db')
queue_manager = PrintQueueManager(todo_db, printer_manager, mqtt_handler)
queue_manager.start()  # Start background queue processor

# Initialize session manager
session_manager = SessionManager(config, todo_db)

# File watcher for .env changes
env_file_path = Path('.env')
last_mtime = 0
watch_thread = None
stop_watching = False

def reload_config():
    """Reload configuration from .env file"""
    global config, printer_manager, mqtt_handler, auth_manager, last_mtime, queue_manager
    
    try:
        # Reload environment variables
        load_dotenv(override=True)
        
        # Update configuration
        new_config = {
            'PRINTER_TYPE': os.getenv('PRINTER_TYPE', 'usb'),
            'PRINTER_VENDOR_ID': os.getenv('PRINTER_VENDOR_ID', '0x04b8'),
            'PRINTER_PRODUCT_ID': os.getenv('PRINTER_PRODUCT_ID', '0x0e15'),
            'PRINTER_SERIAL_PORT': os.getenv('PRINTER_SERIAL_PORT', '/dev/ttyUSB0'),
            'PRINTER_NETWORK_IP': os.getenv('PRINTER_NETWORK_IP', '192.168.1.100'),
            'PRINT_IMAGE_WIDTH': os.getenv('PRINT_IMAGE_WIDTH', '384'),
            'MQTT_ENABLED': os.getenv('MQTT_ENABLED', 'false'),
            'MQTT_BROKER': os.getenv('MQTT_BROKER', 'localhost'),
            'MQTT_PORT': os.getenv('MQTT_PORT', '1883'),
            'MQTT_USERNAME': os.getenv('MQTT_USERNAME', ''),
            'MQTT_PASSWORD': os.getenv('MQTT_PASSWORD', ''),
            'MQTT_TOPIC_BEFORE_PRINT': os.getenv('MQTT_TOPIC_BEFORE_PRINT', 'printer/before_print'),
            'MQTT_PAYLOAD_BEFORE_PRINT': os.getenv('MQTT_PAYLOAD_BEFORE_PRINT', '{"action": "power_on"}'),
            'MQTT_WAIT_SECONDS': os.getenv('MQTT_WAIT_SECONDS', '5'),
            'MQTT_TIMEOUT_MINUTES': os.getenv('MQTT_TIMEOUT_MINUTES', '30'),
            'MQTT_TOPIC_AFTER_TIMEOUT': os.getenv('MQTT_TOPIC_AFTER_TIMEOUT', 'printer/after_timeout'),
            'MQTT_PAYLOAD_AFTER_TIMEOUT': os.getenv('MQTT_PAYLOAD_AFTER_TIMEOUT', '{"action": "power_off"}'),
            'MOTIVATION_ENABLED': os.getenv('MOTIVATION_ENABLED', 'false'),
            'MOTIVATION_PROVIDER': os.getenv('MOTIVATION_PROVIDER', 'openai'),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
            'OPENAI_BASE_URL': os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1/chat/completions'),
            'OPENAI_MODEL': os.getenv('OPENAI_MODEL', os.getenv('MOTIVATION_MODEL', 'gpt-4o-mini')),
            'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY', ''),
            'ANTHROPIC_BASE_URL': os.getenv('ANTHROPIC_BASE_URL', 'https://api.anthropic.com/v1/messages'),
            'ANTHROPIC_MODEL': os.getenv('ANTHROPIC_MODEL', 'claude-3-5-haiku-latest'),
            'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY', ''),
            'OPENROUTER_BASE_URL': os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1/chat/completions'),
            'OPENROUTER_MODEL': os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini'),
            'LOCAL_BASE_URL': os.getenv('LOCAL_BASE_URL', 'http://localhost:11434/v1/chat/completions'),
            'LOCAL_MODEL': os.getenv('LOCAL_MODEL', 'llama3.2'),
            'LANGUAGE': os.getenv('LANGUAGE', 'de'),
        }
        
        # Check if config actually changed
        if new_config != config:
            config.update(new_config)
            
            # Reinitialize managers with new config
            printer_manager = PrinterManager(config)
            
            # Reinitialize MQTT if needed
            old_mqtt_handler = mqtt_handler
            if config['MQTT_ENABLED'].lower() == 'true':
                if old_mqtt_handler:
                    logger.info("Reloading MQTT handler with new configuration...")
                    old_mqtt_handler.cleanup()
                else:
                    logger.info("Enabling MQTT handler...")
                mqtt_handler = MQTTHandler(config)
            else:
                if old_mqtt_handler:
                    logger.info("Disabling MQTT handler...")
                    old_mqtt_handler.cleanup()
                mqtt_handler = None
            
            # Update queue manager with reinitialized managers
            if 'queue_manager' in globals():
                queue_manager.printer_manager = printer_manager
                queue_manager.mqtt_handler = mqtt_handler
            
            # Update auth manager
            auth_manager = AuthManager(os.getenv('API_KEY'))
            
            logger.info("Configuration reloaded from .env file")
            
        # Update last modification time
        if env_file_path.exists():
            last_mtime = env_file_path.stat().st_mtime
            
    except Exception as e:
        logger.error(f"Error reloading configuration: {str(e)}")

def watch_env_file():
    """Watch .env file for changes"""
    global last_mtime, stop_watching
    
    # Get initial modification time
    if env_file_path.exists():
        last_mtime = env_file_path.stat().st_mtime
    
    while not stop_watching:
        try:
            if env_file_path.exists():
                current_mtime = env_file_path.stat().st_mtime
                if current_mtime != last_mtime:
                    logger.info(".env file changed, reloading configuration...")
                    reload_config()
        except Exception as e:
            logger.error(f"Error watching .env file: {str(e)}")
        
        time.sleep(2)  # Check every 2 seconds

# Start watching .env file in background thread
watch_thread = threading.Thread(target=watch_env_file, daemon=True)
watch_thread.start()

# Login/Logout Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    # Check IP whitelist first
    client_ip = request.remote_addr
    if not session_manager.is_ip_allowed(client_ip):
        logger.warning(f"Login access denied for IP {client_ip}")
        return render_template('access_denied.html', client_ip=client_ip), 403
    
    # If auth is disabled, redirect to main page
    if not session_manager.is_enabled():
        return redirect(url_for('index'))
    
    # If already authenticated, redirect to main page
    if session_manager.is_authenticated():
        return redirect(url_for('index'))
    
    language = request.args.get('lang', config.get('LANGUAGE', 'de'))
    if language not in ['de', 'en']:
        language = 'de'
    translations = get_all_translations(language)
    
    error = None
    rate_limited = False
    lockout_time = 0
    
    if request.method == 'POST':
        # Check rate limiting
        ip_address = request.remote_addr
        can_attempt, remaining = session_manager.check_rate_limit(ip_address)
        
        if not can_attempt:
            rate_limited = True
            lockout_time = remaining
            error = translations.get('rate_limit_error', 'Too many failed login attempts. Please try again later.')
        else:
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            remember_me = request.form.get('remember_me') == 'on'
            
            if session_manager.verify_credentials(username, password):
                # Successful login
                session_manager.record_login_attempt(ip_address, True)
                session_manager.create_session(remember_me)
                
                # Redirect to next URL or index
                next_url = session.get('next_url', url_for('index'))
                session.pop('next_url', None)
                
                logger.info(f"Successful login from {ip_address}")
                return redirect(next_url)
            else:
                # Failed login
                session_manager.record_login_attempt(ip_address, False)
                error = translations.get('invalid_credentials', 'Invalid username or password')
                logger.warning(f"Failed login attempt from {ip_address}")
    
    return render_template('login.html',
                         error=error,
                         rate_limited=rate_limited,
                         lockout_time=lockout_time,
                         show_username=bool(config.get('WEB_USERNAME')),
                         language=language,
                         t=translations,
                         csrf_token=session_manager.get_csrf_token())

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session_manager.destroy_session()
    return redirect(url_for('login'))

# Documentation Routes
@app.route('/docs')
def api_docs():
    """Serve API documentation"""
    return redirect('/docs/swagger.html')

@app.route('/docs/<path:filename>')
def serve_docs(filename):
    """Serve documentation files"""
    from flask import send_from_directory
    return send_from_directory('docs', filename)

# Web Routes
@app.route('/')
@session_manager.require_auth
def index():
    """Render the main web interface"""
    # Get current printer configuration
    current_printer = {
        'type': config['PRINTER_TYPE'],
        'vendor_id': config.get('PRINTER_VENDOR_ID'),
        'product_id': config.get('PRINTER_PRODUCT_ID'),
        'serial_port': config.get('PRINTER_SERIAL_PORT'),
        'network_ip': config.get('PRINTER_NETWORK_IP')
    }
    motivation_enabled = config.get('MOTIVATION_ENABLED', 'false').lower() == 'true'
    language = config.get('LANGUAGE', 'de')
    translations = get_all_translations(language)
    session_info = session_manager.get_session_info()
    return render_template('index.html', 
                         current_printer=current_printer, 
                         motivation_enabled=motivation_enabled,
                         motivation_provider=config.get('MOTIVATION_PROVIDER', 'openai'),
                         app_version=APP_VERSION,
                         language=language,
                         t=translations,
                         session_info=session_info,
                         csrf_token=session_manager.get_csrf_token())

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Paperoo Server',
        'mqtt_enabled': config['MQTT_ENABLED'].lower() == 'true',
        'mqtt_connected': mqtt_handler.connected if mqtt_handler else False,
        'env_watching': watch_thread.is_alive() if watch_thread else False
    })

@app.route('/api/reload-config', methods=['POST'])
def api_reload_config():
    """Manually reload configuration from .env file"""
    try:
        reload_config()
        return jsonify({
            'success': True,
            'message': 'Configuration reloaded successfully',
            'config': {
                'language': config.get('LANGUAGE', 'de'),
                'motivation_enabled': config.get('MOTIVATION_ENABLED', 'false').lower() == 'true',
                'mqtt_enabled': config.get('MQTT_ENABLED', 'false').lower() == 'true',
                'printer_type': config.get('PRINTER_TYPE', 'usb')
            }
        })
    except Exception as e:
        logger.error(f"Error reloading config via API: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# API Routes
@app.route('/api/print', methods=['POST'])
@auth_manager.require_api_key
def api_print_todo():
    """API endpoint to print a document"""
    try:
        data = request.get_json()
        
        # Validate input
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided',
                'message': 'Please provide JSON data with text and priority'
            }), 400
        
        requested_type = data.get('type', 'todo')
        print_type = requested_type.strip().lower() if isinstance(requested_type, str) else 'todo'
        if print_type not in PRINT_TYPES:
            print_type = 'todo'
        text = data.get('text', '').strip()
        priority = data.get('priority', 3)
        language = data.get('language', config.get('LANGUAGE', 'de'))  # Optional language parameter
        image_data = data.get('image', '')
        
        if print_type == 'image':
            if not isinstance(image_data, str) or not image_data.strip():
                return jsonify({
                    'success': False,
                    'error': 'Image is required',
                    'message': 'Please provide a base64-encoded image'
                }), 400
        elif not text:
            return jsonify({
                'success': False,
                'error': 'Text is required',
                'message': 'Please provide the text to print'
            }), 400
        
        # Validate language
        if language not in ['de', 'en']:
            language = config.get('LANGUAGE', 'de')
        
        # Validate priority
        try:
            priority = int(priority)
            if priority < 1 or priority > 5:
                priority = 3
        except:
            priority = 3
        
        metadata = {'source': 'api', 'language': language, 'type': print_type}
        title = data.get('title', data.get('list_name', ''))
        if print_type == 'list' and isinstance(title, str) and title.strip():
            metadata['title'] = title.strip()
        author = data.get('author', '')
        if print_type == 'quote' and isinstance(author, str) and author.strip():
            metadata['author'] = author.strip()
        if print_type == 'image':
            metadata['image'] = image_data

        success, message, todo_id = queue_manager.add_todo(text, priority, metadata)
        response_data = {
            'id': todo_id,
            'text': text,
            'priority': priority,
            'language': language,
            'type': print_type
        }

        if success:
            logger.info(f"{print_type} printed successfully")
            return jsonify({
                'success': True,
                'message': message,
                'data': response_data
            }), 200

        logger.info(f"{print_type} saved to queue: {message}")
        response_data['queued'] = True
        return jsonify({
            'success': True,
            'message': message,
            'data': response_data
        }), 200
            
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Server error',
            'message': str(e)
        }), 500

@app.route('/api/status', methods=['GET'])
@auth_manager.require_api_key
def api_status():
    """Get printer and system status"""
    return jsonify({
        'success': True,
        'data': {
            'version': APP_VERSION,
            'printer_configured': printer_manager.printer is not None,
            'mqtt_enabled': config['MQTT_ENABLED'].lower() == 'true',
            'mqtt_connected': mqtt_handler.connected if mqtt_handler else False,
            'printer_active': printer_manager.printer_active,
            'last_print_time': printer_manager.last_print_time.isoformat() if printer_manager.last_print_time else None
        }
    })

@app.route('/api/printers', methods=['GET'])
@session_manager.require_auth
def api_get_printers():
    """Get list of available printers"""
    try:
        printers = PrinterDetector.detect_all_printers()
        
        # Get current configuration
        current_config = {
            'type': config.get('PRINTER_TYPE', 'usb'),
            'vendor_id': config.get('PRINTER_VENDOR_ID'),
            'product_id': config.get('PRINTER_PRODUCT_ID'),
            'serial_port': config.get('PRINTER_SERIAL_PORT'),
            'network_ip': config.get('PRINTER_NETWORK_IP')
        }
        
        return jsonify({
            'success': True,
            'data': {
                'printers': printers,
                'current': current_config
            }
        })
    except Exception as e:
        logger.error(f"Error detecting printers: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to detect printers',
            'message': str(e)
        }), 500

@app.route('/api/printers/select', methods=['POST'])
@session_manager.require_auth
def api_select_printer():
    """Select and save a printer configuration"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        printer_type = data.get('type')
        printer_config = {'type': printer_type}
        
        # Validate and prepare configuration based on type
        if printer_type == 'usb':
            if not data.get('vendor_id') or not data.get('product_id'):
                return jsonify({
                    'success': False,
                    'error': 'USB printer requires vendor_id and product_id'
                }), 400
            printer_config['vendor_id'] = data['vendor_id']
            printer_config['product_id'] = data['product_id']
            
        elif printer_type == 'serial':
            if not data.get('port'):
                return jsonify({
                    'success': False,
                    'error': 'Serial printer requires port'
                }), 400
            printer_config['port'] = data['port']
            
        elif printer_type == 'network':
            if not data.get('ip'):
                return jsonify({
                    'success': False,
                    'error': 'Network printer requires IP address'
                }), 400
            printer_config['ip'] = data['ip']
        else:
            return jsonify({
                'success': False,
                'error': f'Invalid printer type: {printer_type}'
            }), 400
        
        # Save configuration to .env
        if PrinterDetector.save_printer_config(printer_config):
            # Update current configuration
            load_dotenv(override=True)  # Reload .env
            
            # Update config dict
            config['PRINTER_TYPE'] = printer_type
            if printer_type == 'usb':
                config['PRINTER_VENDOR_ID'] = printer_config['vendor_id']
                config['PRINTER_PRODUCT_ID'] = printer_config['product_id']
            elif printer_type == 'serial':
                config['PRINTER_SERIAL_PORT'] = printer_config['port']
            elif printer_type == 'network':
                config['PRINTER_NETWORK_IP'] = printer_config['ip']
            
            # Reinitialize printer manager with new config
            global printer_manager
            printer_manager = PrinterManager(config)
            
            return jsonify({
                'success': True,
                'message': 'Printer configuration saved successfully',
                'data': printer_config
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error selecting printer: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to select printer',
            'message': str(e)
        }), 500

# Web form submission (protected by session auth)
@app.route('/api/settings/language', methods=['POST'])
@session_manager.require_auth
def api_update_language():
    """Update language settings"""
    try:
        data = request.get_json()
        language = data.get('language', 'de')
        
        if language not in ['de', 'en']:
            language = 'de'
        
        # Update config
        config['LANGUAGE'] = language
        
        # Reinitialize printer manager with new language
        global printer_manager
        printer_manager = PrinterManager(config)
        
        logger.info(f"Language setting updated: {language}")
        
        return jsonify({
            'success': True,
            'message': f'Language set to {language}',
            'translations': get_all_translations(language)
        })
    except Exception as e:
        logger.error(f"Error updating language settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/settings/motivation', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_update_motivation():
    """Update the motivation provider and its enabled state"""
    global printer_manager
    try:
        data = request.get_json(silent=True) or {}
        provider = data.get('provider', config.get('MOTIVATION_PROVIDER', 'openai'))
        enabled = data.get('enabled', config.get('MOTIVATION_ENABLED', 'false').lower() == 'true')
        if provider not in MOTIVATION_PROVIDERS or not isinstance(enabled, bool):
            return jsonify({
                'success': False,
                'error': 'Invalid motivation settings'
            }), 400

        from dotenv import set_key
        set_key('.env', 'MOTIVATION_PROVIDER', provider)
        set_key('.env', 'MOTIVATION_ENABLED', str(enabled).lower())
        config['MOTIVATION_PROVIDER'] = provider
        config['MOTIVATION_ENABLED'] = str(enabled).lower()
        printer_manager = PrinterManager(config)
        queue_manager.printer_manager = printer_manager

        return jsonify({
            'success': True,
            'data': {
                'provider': provider,
                'enabled': enabled,
                'generator_enabled': printer_manager.motivation_generator.is_enabled() if printer_manager.motivation_generator else False
            }
        })
    except Exception as e:
        logger.error(f"Error updating motivation settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def read_update_status():
    if not UPDATE_STATUS_PATH.exists():
        return None
    try:
        return json.loads(UPDATE_STATUS_PATH.read_text())
    except (OSError, ValueError):
        return None

@app.route('/api/system/update/status', methods=['GET'])
@session_manager.require_auth
def api_system_update_status():
    return jsonify({
        'success': True,
        'data': {
            'current_version': APP_VERSION,
            'update_script_available': UPDATE_SCRIPT.is_file(),
            'job': read_update_status()
        }
    })

@app.route('/api/system/update/check', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_system_update_check():
    try:
        completed = subprocess.run(
            [str(UPDATE_SCRIPT), '--check'],
            cwd=SERVER_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        try:
            result = json.loads(completed.stdout)
        except ValueError:
            result = {'success': False, 'error': 'Update check returned an invalid response'}
        if completed.returncode != 0 or not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Update check failed')
            }), 502
        return jsonify(result)
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Update check timed out'}), 504
    except OSError as e:
        logger.error(f"Could not start update check: {str(e)}")
        return jsonify({'success': False, 'error': 'Could not start update check'}), 500

@app.route('/api/system/update/install', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_system_update_install():
    if (SERVER_ROOT / 'logs' / 'update.lock').exists():
        return jsonify({'success': False, 'error': 'Another update is already running'}), 409
    try:
        UPDATE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with UPDATE_LOG_PATH.open('a') as update_log:
            subprocess.Popen(
                [str(UPDATE_SCRIPT), '--install'],
                cwd=SERVER_ROOT,
                stdout=update_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return jsonify({'success': True, 'message': 'Update started'}), 202
    except OSError as e:
        logger.error(f"Could not start update: {str(e)}")
        return jsonify({'success': False, 'error': 'Could not start update'}), 500

@app.route('/print', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def web_print_todo():
    """Handle web form submission to print ToDo"""
    try:
        text = request.form.get('text', '').strip()
        priority = request.form.get('priority', 3)
        
        if not text:
            return jsonify({
                'success': False,
                'message': 'Please enter ToDo text'
            }), 400
        
        # Validate priority
        try:
            priority = int(priority)
            if priority < 1 or priority > 5:
                priority = 3
        except:
            priority = 3
        
        # Add to queue and attempt to print
        success, message, todo_id = queue_manager.add_todo(text, priority, {'source': 'web'})
        
        return jsonify({
            'success': True,  # Always return success if saved
            'message': message,
            'todo_id': todo_id,
            'queued': not success  # Indicate if it was queued for retry
        }), 200
        
    except Exception as e:
        logger.error(f"Web print error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Queue management endpoints
@app.route('/api/queue/status', methods=['GET'])
@session_manager.require_auth
def api_queue_status():
    """Get queue status and statistics"""
    try:
        status = queue_manager.get_queue_status()
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/queue/todos', methods=['GET'])
@session_manager.require_auth
def api_get_todos():
    """Get list of recent todos"""
    try:
        limit = request.args.get('limit', 50, type=int)
        todos = todo_db.get_recent_todos(limit=limit)
        return jsonify({
            'success': True,
            'data': todos
        })
    except Exception as e:
        logger.error(f"Error getting todos: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/queue/pending', methods=['GET'])
@session_manager.require_auth
def api_get_pending():
    """Get pending todos in queue"""
    try:
        todos = todo_db.get_pending_todos(limit=20)
        return jsonify({
            'success': True,
            'data': todos
        })
    except Exception as e:
        logger.error(f"Error getting pending todos: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/queue/retry', methods=['POST'])
@session_manager.require_auth
def api_retry_failed():
    """Retry all failed todos"""
    try:
        count = queue_manager.retry_failed()
        return jsonify({
            'success': True,
            'message': f'Reset {count} failed todos for retry',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error retrying failed todos: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/queue/clear', methods=['POST'])
@session_manager.require_auth
def api_clear_queue():
    """Clear all pending and failed todos from the queue"""
    try:
        count = queue_manager.clear_queue()
        return jsonify({
            'success': True,
            'message': f'Cleared {count} todos from queue',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error clearing queue: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Cleanup on exit
def cleanup():
    """Clean up resources on application exit"""
    global stop_watching
    logger.info("Cleaning up resources...")
    
    # Stop watching thread
    stop_watching = True
    if watch_thread:
        watch_thread.join(timeout=5)
    
    # Stop queue manager
    queue_manager.stop()
    
    # Cleanup managers
    if mqtt_handler:
        mqtt_handler.cleanup()
    printer_manager.cleanup()

atexit.register(cleanup)

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    logger.info("="*60)
    logger.info(f"Starting Paperoo Server on {host}:{port}")
    logger.info("="*60)
    
    # Show MQTT status
    if config.get('MQTT_ENABLED', 'false').lower() == 'true':
        logger.info(f"MQTT: Enabled - Connecting to {config.get('MQTT_BROKER')}:{config.get('MQTT_PORT')}")
        # Give MQTT a moment to connect
        time.sleep(2)
        if mqtt_handler and mqtt_handler.connected:
            logger.info("MQTT: ✓ Connected successfully")
        else:
            logger.warning("MQTT: ⚠ Not connected yet (will retry in background)")
    else:
        logger.info("MQTT: Disabled")
    
    logger.info("="*60)
    
    app.run(host=host, port=port, debug=debug)