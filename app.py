import atexit
import base64
import ipaddress
import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import timedelta
from functools import wraps
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.security import generate_password_hash

from modules.auth import AuthManager
from modules.configuration import load_config
from modules.database import TodoDatabase
from modules.motivation_generator import MotivationGenerator
from modules.mqtt_handler import MQTTHandler
from modules.print_queue import PrintQueueManager
from modules.printer_detector import PrinterDetector
from modules.printer_manager import PrinterManager
from modules.session_manager import SessionManager
from modules.settings_store import (
    SettingsError,
    SettingsStore,
    boolean_value,
    integer_value,
    text_value,
    url_value,
)
from modules.translations import get_all_translations

SERVER_ROOT = Path(__file__).resolve().parent
load_dotenv(SERVER_ROOT / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
)
logger = logging.getLogger(__name__)
logging.getLogger('modules.mqtt_handler').setLevel(logging.INFO)
logging.getLogger('modules.printer_manager').setLevel(logging.INFO)

APP_VERSION = '1.0.8'
PRINT_TYPES = {'todo', 'list', 'note', 'quote', 'image', 'qr', 'receipt'}
MOTIVATION_PROVIDERS = {'openai', 'anthropic', 'openrouter', 'local'}
UPDATE_SCRIPT = SERVER_ROOT / 'update.sh'
UPDATE_STATUS_PATH = SERVER_ROOT / 'logs' / 'update-status.json'
UPDATE_LOG_PATH = SERVER_ROOT / 'logs' / 'update-manual.log'

app = Flask(__name__)
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    raise RuntimeError('SECRET_KEY must be set in the environment or .env file')
app.config['SECRET_KEY'] = secret_key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

config = load_config()
printer_manager = PrinterManager(config)
mqtt_handler = MQTTHandler(config) if config['MQTT_ENABLED'].lower() == 'true' else None
todo_db = TodoDatabase(str(SERVER_ROOT / 'todos.db'))
auth_manager = AuthManager(os.getenv('API_KEY'), todo_db)
queue_manager = PrintQueueManager(todo_db, printer_manager, mqtt_handler)
queue_manager.start()
session_manager = SessionManager(config, todo_db)
settings_store = SettingsStore(SERVER_ROOT / '.env')

env_file_path = SERVER_ROOT / '.env'
last_mtime = 0
watch_thread = None
stop_watching = False


def reload_config():
    global config, printer_manager, mqtt_handler, auth_manager, last_mtime
    try:
        load_dotenv(env_file_path, override=True)
        new_config = load_config()
        if new_config != config:
            config.update(new_config)
            printer_manager = PrinterManager(config)
            old_mqtt_handler = mqtt_handler
            if config['MQTT_ENABLED'].lower() == 'true':
                if old_mqtt_handler:
                    old_mqtt_handler.cleanup()
                mqtt_handler = MQTTHandler(config)
            else:
                if old_mqtt_handler:
                    old_mqtt_handler.cleanup()
                mqtt_handler = None
            queue_manager.printer_manager = printer_manager
            queue_manager.mqtt_handler = mqtt_handler
            auth_manager = AuthManager(os.getenv('API_KEY'), todo_db)
            session_manager.update_config(config)
            logger.info('Configuration reloaded from .env file')
        if env_file_path.exists():
            last_mtime = env_file_path.stat().st_mtime
    except Exception as e:
        logger.error(f'Error reloading configuration: {str(e)}')
        raise


def watch_env_file():
    global last_mtime, stop_watching
    if env_file_path.exists():
        last_mtime = env_file_path.stat().st_mtime
    while not stop_watching:
        try:
            if env_file_path.exists():
                current_mtime = env_file_path.stat().st_mtime
                if current_mtime != last_mtime:
                    logger.info('.env file changed, reloading configuration...')
                    reload_config()
        except Exception as e:
            logger.error(f'Error watching .env file: {str(e)}')
        time.sleep(2)


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
    language = config.get('LANGUAGE', 'de')
    return render_template(
        'index.html',
        language=language,
        t=get_all_translations(language),
        session_info=session_manager.get_session_info(),
        csrf_token=session_manager.get_csrf_token(),
    )


@app.route('/settings')
@session_manager.require_auth
def settings_page():
    language = config.get('LANGUAGE', 'de')
    return render_template(
        'settings.html',
        app_version=APP_VERSION,
        language=language,
        t=get_all_translations(language),
        session_info=session_manager.get_session_info(),
        csrf_token=session_manager.get_csrf_token(),
    )


def public_settings():
    providers = {}
    for provider in MOTIVATION_PROVIDERS:
        prefix = provider.upper()
        defaults = MotivationGenerator.DEFAULTS[provider]
        providers[provider] = {
            'base_url': config.get(f'{prefix}_BASE_URL', defaults['base_url']),
            'model': config.get(f'{prefix}_MODEL', defaults['model']),
            'api_key_configured': bool(config.get(f'{prefix}_API_KEY', '')),
        }
    return {
        'auth': {
            'enabled': session_manager.is_enabled(),
            'username': config.get('WEB_USERNAME', ''),
            'password_configured': bool(config.get('WEB_PASSWORD_HASH') or config.get('WEB_PASSWORD')),
            'session_timeout': int(config.get('WEB_SESSION_TIMEOUT', 1440)),
            'remember_me_days': int(config.get('WEB_REMEMBER_ME_DAYS', 30)),
        },
        'motivation': {
            'enabled': config.get('MOTIVATION_ENABLED', 'false').lower() == 'true',
            'provider': config.get('MOTIVATION_PROVIDER', 'openai'),
            'providers': providers,
        },
        'mqtt': {
            'enabled': config.get('MQTT_ENABLED', 'false').lower() == 'true',
            'broker': config.get('MQTT_BROKER', ''),
            'port': int(config.get('MQTT_PORT', 1883)),
            'username': config.get('MQTT_USERNAME', ''),
            'password_configured': bool(config.get('MQTT_PASSWORD')),
            'topic_before_print': config.get('MQTT_TOPIC_BEFORE_PRINT', ''),
            'payload_before_print': config.get('MQTT_PAYLOAD_BEFORE_PRINT', ''),
            'wait_seconds': int(config.get('MQTT_WAIT_SECONDS', 5)),
            'timeout_minutes': int(config.get('MQTT_TIMEOUT_MINUTES', 30)),
            'topic_after_timeout': config.get('MQTT_TOPIC_AFTER_TIMEOUT', ''),
            'payload_after_timeout': config.get('MQTT_PAYLOAD_AFTER_TIMEOUT', ''),
        },
    }


@app.route('/api/settings', methods=['GET'])
@session_manager.require_auth
def api_get_settings():
    return jsonify({'success': True, 'data': public_settings()})


@app.route('/api/settings/auth', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_update_auth_settings():
    try:
        data = request.get_json(silent=True) or {}
        enabled = data.get('enabled', session_manager.is_enabled())
        if not isinstance(enabled, bool):
            raise SettingsError('enabled must be a boolean')
        username = text_value(data.get('username', config.get('WEB_USERNAME', '')), 'username', 100)
        session_timeout = integer_value(data.get('session_timeout', 1440), 'session_timeout', 5, 10080)
        remember_me_days = integer_value(data.get('remember_me_days', 30), 'remember_me_days', 1, 365)
        new_password = text_value(data.get('new_password', ''), 'new_password', 500)
        confirmation = text_value(data.get('password_confirmation', ''), 'password_confirmation', 500)

        if session_manager.is_enabled():
            current_password = text_value(data.get('current_password', ''), 'current_password', 500, required=True)
            if not session_manager.verify_credentials(session_manager.username, current_password):
                return jsonify({'success': False, 'error': 'Current password is incorrect'}), 403

        password_hash = config.get('WEB_PASSWORD_HASH', '')
        plaintext_password = config.get('WEB_PASSWORD', '')
        if new_password or confirmation:
            if len(new_password) < 12:
                raise SettingsError('The new password must contain at least 12 characters')
            if new_password != confirmation:
                raise SettingsError('The password confirmation does not match')
            password_hash = generate_password_hash(new_password)
            plaintext_password = ''
        if enabled and not (password_hash or plaintext_password):
            raise SettingsError('Set a password before enabling web protection')

        settings_store.update({
            'WEB_AUTH_ENABLED': str(enabled).lower(),
            'WEB_USERNAME': username,
            'WEB_PASSWORD_HASH': password_hash,
            'WEB_PASSWORD': plaintext_password,
            'WEB_SESSION_TIMEOUT': session_timeout,
            'WEB_REMEMBER_ME_DAYS': remember_me_days,
        })
        reload_config()
        if enabled:
            session_manager.create_session(session.get('remember_me', False))
        return jsonify({'success': True, 'data': public_settings()['auth']})
    except SettingsError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except OSError as e:
        logger.error(f'Could not save authentication settings: {str(e)}')
        return jsonify({'success': False, 'error': 'Could not save authentication settings'}), 500


@app.route('/api/settings/api-keys', methods=['GET'])
@session_manager.require_auth
def api_get_managed_api_keys():
    return jsonify({'success': True, 'data': todo_db.get_api_keys()})


@app.route('/api/settings/api-keys', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_create_managed_api_key():
    try:
        data = request.get_json(silent=True) or {}
        comment = text_value(data.get('comment', ''), 'comment', 200, required=True)
        raw_key = auth_manager.generate_api_key()
        key_id = todo_db.create_api_key(
            auth_manager.hash_api_key(raw_key),
            raw_key[:12],
            comment,
        )
        key = next(item for item in todo_db.get_api_keys() if item['id'] == key_id)
        return jsonify({'success': True, 'data': {'api_key': raw_key, 'key': key}}), 201
    except SettingsError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Could not create API key: {str(e)}')
        return jsonify({'success': False, 'error': 'Could not create API key'}), 500


@app.route('/api/settings/api-keys/<int:key_id>', methods=['DELETE'])
@session_manager.require_auth
@session_manager.require_csrf
def api_revoke_managed_api_key(key_id):
    if todo_db.revoke_api_key(key_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'The API key is already inactive or is the legacy key'}), 400


@app.route('/api/settings/print-log', methods=['GET'])
@session_manager.require_auth
def api_get_print_log():
    try:
        limit = request.args.get('limit', 100, type=int)
        key_id = request.args.get('key_id', type=int)
        return jsonify({
            'success': True,
            'data': todo_db.get_print_events(limit=limit, key_id=key_id),
        })
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid log filter'}), 400


def save_motivation_settings(data):
    provider = data.get('provider', config.get('MOTIVATION_PROVIDER', 'openai'))
    enabled = data.get('enabled', config.get('MOTIVATION_ENABLED', 'false').lower() == 'true')
    if provider not in MOTIVATION_PROVIDERS:
        raise SettingsError('Invalid motivation provider')
    enabled_value = boolean_value(enabled, 'enabled')
    prefix = provider.upper()
    defaults = MotivationGenerator.DEFAULTS[provider]
    provider_data = data.get('settings') or {}
    if not isinstance(provider_data, dict):
        raise SettingsError('settings must be an object')
    base_url = url_value(provider_data.get('base_url', config.get(f'{prefix}_BASE_URL', defaults['base_url'])), 'base_url')
    model = text_value(provider_data.get('model', config.get(f'{prefix}_MODEL', defaults['model'])), 'model', 200, required=True)
    api_key = text_value(provider_data.get('api_key', ''), 'api_key', 4096)
    clear_api_key = provider_data.get('clear_api_key', False)
    if not isinstance(clear_api_key, bool):
        raise SettingsError('clear_api_key must be a boolean')
    if api_key and clear_api_key:
        raise SettingsError('An API key cannot be entered and cleared at the same time')
    if not api_key:
        api_key = '' if clear_api_key else config.get(f'{prefix}_API_KEY', '')
    if enabled and provider != 'local' and not api_key:
        raise SettingsError('An API key is required for the selected provider')

    settings_store.update({
        'MOTIVATION_PROVIDER': provider,
        'MOTIVATION_ENABLED': enabled_value,
        f'{prefix}_BASE_URL': base_url,
        f'{prefix}_MODEL': model,
        f'{prefix}_API_KEY': api_key,
    })
    reload_config()


@app.route('/api/settings/motivation', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_update_motivation():
    try:
        save_motivation_settings(request.get_json(silent=True) or {})
        return jsonify({'success': True, 'data': public_settings()['motivation']})
    except SettingsError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except OSError as e:
        logger.error(f'Could not save motivation settings: {str(e)}')
        return jsonify({'success': False, 'error': 'Could not save motivation settings'}), 500


@app.route('/api/settings/mqtt', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_update_mqtt_settings():
    try:
        data = request.get_json(silent=True) or {}
        enabled = boolean_value(data.get('enabled', False), 'enabled')
        broker = text_value(data.get('broker', ''), 'broker', 255, required=enabled == 'true')
        username = text_value(data.get('username', ''), 'username', 255)
        password = text_value(data.get('password', ''), 'password', 4096)
        clear_password = data.get('clear_password', False)
        if not isinstance(clear_password, bool):
            raise SettingsError('clear_password must be a boolean')
        if password and clear_password:
            raise SettingsError('A password cannot be entered and cleared at the same time')
        if not password:
            password = '' if clear_password else config.get('MQTT_PASSWORD', '')
        payload_before = text_value(data.get('payload_before_print', ''), 'payload_before_print', 4096)
        payload_after = text_value(data.get('payload_after_timeout', ''), 'payload_after_timeout', 4096)
        for payload in (payload_before, payload_after):
            if payload:
                try:
                    json.loads(payload)
                except ValueError:
                    raise SettingsError('MQTT payloads must contain valid JSON') from None
        settings_store.update({
            'MQTT_ENABLED': enabled,
            'MQTT_BROKER': broker,
            'MQTT_PORT': integer_value(data.get('port', 1883), 'port', 1, 65535),
            'MQTT_USERNAME': username,
            'MQTT_PASSWORD': password,
            'MQTT_TOPIC_BEFORE_PRINT': text_value(data.get('topic_before_print', ''), 'topic_before_print', 500, required=enabled == 'true'),
            'MQTT_PAYLOAD_BEFORE_PRINT': payload_before,
            'MQTT_WAIT_SECONDS': integer_value(data.get('wait_seconds', 5), 'wait_seconds', 0, 300),
            'MQTT_TIMEOUT_MINUTES': integer_value(data.get('timeout_minutes', 30), 'timeout_minutes', 1, 1440),
            'MQTT_TOPIC_AFTER_TIMEOUT': text_value(data.get('topic_after_timeout', ''), 'topic_after_timeout', 500, required=enabled == 'true'),
            'MQTT_PAYLOAD_AFTER_TIMEOUT': payload_after,
        })
        reload_config()
        return jsonify({'success': True, 'data': public_settings()['mqtt']})
    except SettingsError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except OSError as e:
        logger.error(f'Could not save MQTT settings: {str(e)}')
        return jsonify({'success': False, 'error': 'Could not save MQTT settings'}), 500

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
@session_manager.require_auth
@session_manager.require_csrf
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

def require_api_or_web_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('Authorization') or request.headers.get('X-API-Key'):
            return auth_manager.require_api_key(f)(*args, **kwargs)
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return session_manager.require_auth(session_manager.require_csrf(f))(*args, **kwargs)
        return session_manager.require_auth(f)(*args, **kwargs)
    return decorated_function


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
        elif print_type == 'qr':
            try:
                qr_size = int(data.get('qr_size', 8))
            except (TypeError, ValueError):
                qr_size = 8
            metadata['qr_size'] = min(16, max(1, qr_size))

        success, message, todo_id = queue_manager.add_todo(text, priority, metadata)
        key_record = g.get('api_key_record')
        try:
            todo_db.add_print_event(
                key_record['id'] if key_record else None,
                print_type,
                text,
                metadata,
                language,
                'printed' if success else 'queued',
            )
        except Exception as e:
            logger.error(f'Could not record print event: {str(e)}')
        response_data = {
            'id': todo_id,
            'text': text,
            'priority': priority,
            'language': language,
            'type': print_type
        }
        if print_type == 'qr':
            response_data['qr_size'] = metadata['qr_size']

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
@session_manager.require_csrf
def api_select_printer():
    try:
        data = request.get_json(silent=True) or {}
        printer_type = data.get('type')
        values = {'PRINTER_TYPE': printer_type}
        printer_config = {'type': printer_type}
        if printer_type == 'usb':
            for field, key in (('vendor_id', 'PRINTER_VENDOR_ID'), ('product_id', 'PRINTER_PRODUCT_ID')):
                identifier = text_value(data.get(field, ''), field, 6, required=True).lower()
                if not re.fullmatch(r'(?:0x)?[0-9a-f]{4}', identifier):
                    raise SettingsError(f'{field} must be a four-digit hexadecimal USB ID')
                if not identifier.startswith('0x'):
                    identifier = f'0x{identifier}'
                values[key] = identifier
                printer_config[field] = identifier
        elif printer_type == 'serial':
            port = text_value(data.get('port', ''), 'port', 500, required=True)
            if not port.startswith('/dev/'):
                raise SettingsError('The serial port must be a /dev/ path')
            values['PRINTER_SERIAL_PORT'] = port
            printer_config['port'] = port
        elif printer_type == 'network':
            address = text_value(data.get('ip', ''), 'ip', 255, required=True)
            try:
                ipaddress.ip_address(address)
            except ValueError:
                raise SettingsError('Enter a valid IPv4 or IPv6 address') from None
            values['PRINTER_NETWORK_IP'] = address
            printer_config['ip'] = address
        else:
            raise SettingsError('Invalid printer type')

        settings_store.update(values)
        reload_config()
        return jsonify({'success': True, 'data': printer_config})
    except SettingsError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except OSError as e:
        logger.error(f'Could not save printer configuration: {str(e)}')
        return jsonify({'success': False, 'error': 'Could not save printer configuration'}), 500


@app.route('/api/settings/language', methods=['POST'])
@session_manager.require_auth
@session_manager.require_csrf
def api_update_language():
    try:
        data = request.get_json(silent=True) or {}
        language = data.get('language', 'de')
        if language not in ['de', 'en']:
            raise SettingsError('Invalid language')
        settings_store.update({'LANGUAGE': language})
        reload_config()
        return jsonify({
            'success': True,
            'translations': get_all_translations(language),
        })
    except SettingsError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except OSError as e:
        logger.error(f'Could not save language: {str(e)}')
        return jsonify({'success': False, 'error': 'Could not save language'}), 500

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
    try:
        print_type = request.form.get('type', 'todo').strip().lower()
        if print_type not in PRINT_TYPES:
            return jsonify({'success': False, 'error': 'Invalid print type'}), 400
        text = request.form.get('text', '').strip()
        if len(text) > 500:
            return jsonify({'success': False, 'error': 'Text must not exceed 500 characters'}), 400
        if print_type != 'image' and not text:
            return jsonify({'success': False, 'error': 'Text is required'}), 400

        try:
            priority = int(request.form.get('priority', 3))
            if priority < 1 or priority > 5:
                priority = 3
        except (TypeError, ValueError):
            priority = 3

        metadata = {
            'source': 'web',
            'language': config.get('LANGUAGE', 'de'),
            'type': print_type,
        }
        if print_type == 'list':
            title = request.form.get('title', '').strip()
            if len(title) > 200:
                return jsonify({'success': False, 'error': 'List title must not exceed 200 characters'}), 400
            if title:
                metadata['title'] = title
        elif print_type == 'quote':
            author = request.form.get('author', '').strip()
            if len(author) > 200:
                return jsonify({'success': False, 'error': 'Author must not exceed 200 characters'}), 400
            if author:
                metadata['author'] = author
        elif print_type == 'image':
            image_file = request.files.get('image')
            if not image_file or not image_file.filename:
                return jsonify({'success': False, 'error': 'An image file is required'}), 400
            image_bytes = image_file.read(10 * 1024 * 1024 + 1)
            if len(image_bytes) > 10 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Image file must not exceed 10 MB'}), 400
            try:
                with Image.open(BytesIO(image_bytes)) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                return jsonify({'success': False, 'error': 'The selected file is not a valid image'}), 400
            metadata['image'] = base64.b64encode(image_bytes).decode('ascii')
        elif print_type == 'qr':
            try:
                qr_size = int(request.form.get('qr_size', 8))
            except (TypeError, ValueError):
                qr_size = 8
            metadata['qr_size'] = min(16, max(1, qr_size))

        success, message, todo_id = queue_manager.add_todo(text, priority, metadata)
        response_data = {
            'success': True,
            'message': message,
            'todo_id': todo_id,
            'type': print_type,
            'queued': not success,
        }
        if print_type == 'qr':
            response_data['qr_size'] = metadata['qr_size']
        return jsonify(response_data), 200
    except Exception as e:
        logger.error(f'Web print error: {str(e)}')
        return jsonify({'success': False, 'error': 'Could not process print job'}), 500

# Queue management endpoints
@app.route('/api/queue/status', methods=['GET'])
@require_api_or_web_auth
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
@require_api_or_web_auth
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
@require_api_or_web_auth
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
@require_api_or_web_auth
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
@require_api_or_web_auth
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