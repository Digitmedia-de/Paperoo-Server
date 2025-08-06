import hashlib
import hmac
import secrets
from functools import wraps
from datetime import datetime, timedelta
from flask import session, redirect, url_for, request, jsonify, render_template
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, config):
        """Initialize the session manager with configuration"""
        self.enabled = config.get('WEB_AUTH_ENABLED', 'false').lower() == 'true'
        self.username = config.get('WEB_USERNAME', '').strip()
        self.password = config.get('WEB_PASSWORD', '')
        self.session_timeout = int(config.get('WEB_SESSION_TIMEOUT', 1440))  # minutes
        self.remember_me_days = int(config.get('WEB_REMEMBER_ME_DAYS', 30))
        
        # IP Whitelist configuration
        self.ip_whitelist_enabled = config.get('WEB_IP_WHITELIST_ENABLED', 'false').lower() == 'true'
        self.allowed_networks = self._parse_ip_whitelist(config.get('WEB_IP_WHITELIST', '192.168.0.0/16,10.0.0.0/8,127.0.0.1'))
        
        # Rate limiting
        self.login_attempts = {}
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 minutes in seconds
    
    def _parse_ip_whitelist(self, whitelist_str):
        """Parse IP whitelist from comma-separated string"""
        import ipaddress
        networks = []
        if not whitelist_str:
            return networks
            
        for item in whitelist_str.split(','):
            item = item.strip()
            if not item:
                continue
            try:
                # Try to parse as network (e.g., 192.168.0.0/24)
                if '/' in item:
                    network = ipaddress.ip_network(item, strict=False)
                    networks.append(network)
                else:
                    # Single IP address - convert to /32 network
                    network = ipaddress.ip_network(item + '/32', strict=False)
                    networks.append(network)
            except ValueError as e:
                logger.warning(f"Invalid IP/network in whitelist: {item} - {e}")
        
        return networks
    
    def is_ip_allowed(self, ip_address):
        """Check if an IP address is allowed to access the web interface"""
        if not self.ip_whitelist_enabled:
            return True  # IP whitelist disabled, allow all
        
        if not self.allowed_networks:
            logger.warning("IP whitelist enabled but no valid networks configured")
            return False
        
        try:
            import ipaddress
            ip = ipaddress.ip_address(ip_address)
            
            # Check if IP is in any allowed network
            for network in self.allowed_networks:
                if ip in network:
                    logger.debug(f"IP {ip_address} allowed (matches {network})")
                    return True
            
            logger.warning(f"IP {ip_address} denied - not in whitelist")
            return False
            
        except ValueError as e:
            logger.error(f"Invalid IP address: {ip_address} - {e}")
            return False
    
    def is_enabled(self):
        """Check if web authentication is enabled"""
        return self.enabled and self.password
    
    def verify_credentials(self, username, password):
        """Verify login credentials with constant-time comparison"""
        if not self.is_enabled():
            return True
        
        # If no username is configured, ignore username check
        username_valid = True
        if self.username:
            username_valid = hmac.compare_digest(username.lower(), self.username.lower())
        
        # Always check password
        password_valid = hmac.compare_digest(password, self.password)
        
        return username_valid and password_valid
    
    def check_rate_limit(self, ip_address):
        """Check if IP is rate limited for login attempts"""
        now = datetime.now()
        
        # Clean old attempts
        self.login_attempts = {
            ip: (count, timestamp) 
            for ip, (count, timestamp) in self.login_attempts.items()
            if (now - timestamp).total_seconds() < self.lockout_duration
        }
        
        if ip_address in self.login_attempts:
            count, timestamp = self.login_attempts[ip_address]
            if count >= self.max_attempts:
                remaining = self.lockout_duration - (now - timestamp).total_seconds()
                if remaining > 0:
                    return False, int(remaining)
        
        return True, 0
    
    def record_login_attempt(self, ip_address, success):
        """Record a login attempt"""
        now = datetime.now()
        
        if success:
            # Clear attempts on successful login
            if ip_address in self.login_attempts:
                del self.login_attempts[ip_address]
        else:
            # Increment failed attempts
            if ip_address in self.login_attempts:
                count, _ = self.login_attempts[ip_address]
                self.login_attempts[ip_address] = (count + 1, now)
            else:
                self.login_attempts[ip_address] = (1, now)
    
    def create_session(self, remember_me=False):
        """Create a new session after successful login"""
        session.permanent = True
        session['authenticated'] = True
        session['login_time'] = datetime.now().isoformat()
        session['remember_me'] = remember_me
        
        if remember_me:
            # Extended session for remember me
            session.permanent_session_lifetime = timedelta(days=self.remember_me_days)
        else:
            # Normal session timeout
            session.permanent_session_lifetime = timedelta(minutes=self.session_timeout)
        
        # Generate new session ID for security
        session['session_id'] = secrets.token_hex(32)
        
        logger.info(f"Session created with remember_me={remember_me}")
    
    def destroy_session(self):
        """Destroy the current session"""
        session.clear()
        logger.info("Session destroyed")
    
    def is_authenticated(self):
        """Check if the current session is authenticated"""
        if not self.is_enabled():
            return True  # If auth is disabled, always authenticated
        
        if not session.get('authenticated'):
            return False
        
        # Check session timeout
        login_time = session.get('login_time')
        if login_time:
            login_dt = datetime.fromisoformat(login_time)
            remember_me = session.get('remember_me', False)
            
            if remember_me:
                timeout = timedelta(days=self.remember_me_days)
            else:
                timeout = timedelta(minutes=self.session_timeout)
            
            if datetime.now() - login_dt > timeout:
                self.destroy_session()
                return False
        
        return True
    
    def require_auth(self, f):
        """Decorator to require authentication for routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # First check IP whitelist for web routes
            if not request.path.startswith('/api/'):
                client_ip = request.remote_addr
                if not self.is_ip_allowed(client_ip):
                    logger.warning(f"Access denied for IP {client_ip} to {request.path}")
                    # For AJAX requests, return JSON
                    if request.is_json:
                        return jsonify({
                            'success': False,
                            'error': 'Access denied',
                            'message': 'Access from your IP address is not allowed'
                        }), 403
                    # For normal requests, show error page
                    return render_template('access_denied.html', client_ip=client_ip), 403
            
            if not self.is_enabled():
                return f(*args, **kwargs)
            
            if not self.is_authenticated():
                # For AJAX requests, return 401
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False,
                        'error': 'Authentication required',
                        'message': 'Please log in to access this resource'
                    }), 401
                
                # For normal requests, redirect to login
                session['next_url'] = request.url
                return redirect(url_for('login'))
            
            # Refresh session activity
            session.modified = True
            return f(*args, **kwargs)
        
        return decorated_function
    
    def get_session_info(self):
        """Get current session information"""
        if not self.is_authenticated():
            return None
        
        login_time = session.get('login_time')
        if login_time:
            login_dt = datetime.fromisoformat(login_time)
            remember_me = session.get('remember_me', False)
            
            if remember_me:
                timeout = timedelta(days=self.remember_me_days)
            else:
                timeout = timedelta(minutes=self.session_timeout)
            
            expires_at = login_dt + timeout
            remaining = (expires_at - datetime.now()).total_seconds()
            
            return {
                'username': self.username or 'admin',
                'login_time': login_time,
                'remember_me': remember_me,
                'expires_at': expires_at.isoformat(),
                'remaining_seconds': max(0, int(remaining))
            }
        
        return None