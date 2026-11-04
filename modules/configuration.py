import os


DEFAULT_CONFIG = {
    'PRINTER_TYPE': 'usb',
    'PRINTER_VENDOR_ID': '0x04b8',
    'PRINTER_PRODUCT_ID': '0x0e15',
    'PRINTER_SERIAL_PORT': '/dev/ttyUSB0',
    'PRINTER_NETWORK_IP': '192.168.1.100',
    'PRINT_IMAGE_WIDTH': '384',
    'MQTT_ENABLED': 'false',
    'MQTT_BROKER': 'localhost',
    'MQTT_PORT': '1883',
    'MQTT_USERNAME': '',
    'MQTT_PASSWORD': '',
    'MQTT_TOPIC_BEFORE_PRINT': 'printer/before_print',
    'MQTT_PAYLOAD_BEFORE_PRINT': '{"action": "power_on"}',
    'MQTT_WAIT_SECONDS': '5',
    'MQTT_TIMEOUT_MINUTES': '30',
    'MQTT_TOPIC_AFTER_TIMEOUT': 'printer/after_timeout',
    'MQTT_PAYLOAD_AFTER_TIMEOUT': '{"action": "power_off"}',
    'MOTIVATION_ENABLED': 'false',
    'MOTIVATION_PROVIDER': 'openai',
    'OPENAI_API_KEY': '',
    'OPENAI_BASE_URL': 'https://api.openai.com/v1/chat/completions',
    'OPENAI_MODEL': 'gpt-4o-mini',
    'ANTHROPIC_API_KEY': '',
    'ANTHROPIC_BASE_URL': 'https://api.anthropic.com/v1/messages',
    'ANTHROPIC_MODEL': 'claude-3-5-haiku-latest',
    'OPENROUTER_API_KEY': '',
    'OPENROUTER_BASE_URL': 'https://openrouter.ai/api/v1/chat/completions',
    'OPENROUTER_MODEL': 'openai/gpt-4o-mini',
    'LOCAL_BASE_URL': 'http://localhost:11434/v1/chat/completions',
    'LOCAL_MODEL': 'llama3.2',
    'LANGUAGE': 'de',
    'WEB_AUTH_ENABLED': 'false',
    'WEB_USERNAME': '',
    'WEB_PASSWORD': '',
    'WEB_PASSWORD_HASH': '',
    'WEB_SESSION_TIMEOUT': '1440',
    'WEB_REMEMBER_ME_DAYS': '30',
    'WEB_IP_WHITELIST_ENABLED': 'false',
    'WEB_IP_WHITELIST': '192.168.0.0/16,10.0.0.0/8,127.0.0.1',
}


def load_config():
    values = {key: os.getenv(key, default) for key, default in DEFAULT_CONFIG.items()}
    legacy_comments = {
        'WEB_USERNAME': '# Optional username (leave empty for password-only auth)',
        'WEB_PASSWORD_HASH': '# Recommended: generate with python3 -c "from werkzeug.security import generate_password_hash as g; print(g(\'DEIN_PASSWORT\'))"',
        'WEB_PASSWORD': '# Legacy plaintext fallback; a startup warning is shown when used',
    }
    for key, comment in legacy_comments.items():
        if values[key] == comment:
            values[key] = ''
    return values
