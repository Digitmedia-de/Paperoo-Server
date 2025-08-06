from functools import wraps
from flask import request, jsonify
import hashlib
import hmac
import time

class AuthManager:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def verify_api_key(self, provided_key):
        """Verify if provided API key matches configured key"""
        if not self.api_key:
            return True  # No API key configured, allow all requests
        
        return hmac.compare_digest(provided_key, self.api_key)
    
    def require_api_key(self, f):
        """Decorator to require API key for routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check for Bearer token in Authorization header (preferred)
            auth_header = request.headers.get('Authorization')
            api_key = None
            
            if auth_header:
                # Check for Bearer token format
                if auth_header.startswith('Bearer '):
                    api_key = auth_header[7:]  # Remove 'Bearer ' prefix
                # Also support direct API key in Authorization header
                elif not ' ' in auth_header:
                    api_key = auth_header
            
            # Fallback to X-API-Key header for backward compatibility
            if not api_key:
                api_key = request.headers.get('X-API-Key')
            
            # Also check in query parameters as fallback
            if not api_key:
                api_key = request.args.get('api_key')
            
            # Verify API key
            if not api_key:
                return jsonify({
                    'success': False,
                    'error': 'Authentication required',
                    'message': 'Please provide an API key using "Authorization: Bearer YOUR_API_KEY" header'
                }), 401
            
            if not self.verify_api_key(api_key):
                return jsonify({
                    'success': False,
                    'error': 'Invalid API key',
                    'message': 'The provided API key is invalid'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    def generate_api_key(self, length=32):
        """Generate a random API key"""
        import secrets
        return secrets.token_urlsafe(length)