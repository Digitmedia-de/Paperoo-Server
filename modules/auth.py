import hashlib
import logging
import secrets
from functools import wraps

from flask import g, jsonify, request

logger = logging.getLogger(__name__)


class AuthManager:
    def __init__(self, api_key, database):
        self.api_key = api_key
        self.database = database
        if api_key:
            database.ensure_legacy_api_key(
                self.hash_api_key(api_key),
                api_key[:12],
                'Standard API key (.env)',
            )

    @staticmethod
    def hash_api_key(api_key):
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    def verify_api_key(self, provided_key):
        key_record = self.database.get_api_key_by_hash(self.hash_api_key(provided_key))
        if key_record:
            return key_record
        if not self.api_key and not self.database.has_active_api_keys():
            return None
        return False

    def require_api_key(self, f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            api_key = None
            if auth_header:
                if auth_header.startswith('Bearer '):
                    api_key = auth_header[7:]
                elif ' ' not in auth_header:
                    api_key = auth_header
            if not api_key:
                api_key = request.headers.get('X-API-Key')
            if not api_key:
                return jsonify({
                    'success': False,
                    'error': 'Authentication required',
                    'message': 'Please provide an API key using "Authorization: Bearer YOUR_API_KEY" header',
                }), 401

            key_record = self.verify_api_key(api_key)
            if key_record is False:
                return jsonify({
                    'success': False,
                    'error': 'Invalid API key',
                    'message': 'The provided API key is invalid',
                }), 403

            g.api_key_record = key_record
            if key_record:
                try:
                    self.database.record_api_key_usage(key_record['id'])
                except Exception as e:
                    logger.error(f'Could not record API key usage: {str(e)}')
            return f(*args, **kwargs)

        return decorated_function

    @staticmethod
    def generate_api_key(length=32):
        return secrets.token_urlsafe(length)
