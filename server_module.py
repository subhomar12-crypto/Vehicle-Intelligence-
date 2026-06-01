"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Server Module
"""

import os
import json
import threading
import time
import http.server
import socketserver
from http import HTTPStatus
from datetime import datetime
import warnings
import sqlite3
import hashlib
import secrets
from typing import Dict, Optional, List, Any, Tuple
from collections import defaultdict, deque
import numpy as np

from config import get_config
CONFIG = get_config()

# Import production integrity systems
try:
    from system_integrity import run_startup_integrity_check
    INTEGRITY_CHECK_AVAILABLE = True
except ImportError:
    INTEGRITY_CHECK_AVAILABLE = False

# Import PySide6 for signals
try:
    from PySide6.QtCore import QObject, Signal
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    print("Warning: PySide6 not available for mobile server signals")

warnings.filterwarnings('ignore')

# Essential Security Configuration
SECURITY_CONFIG = {
    'rate_limit_window': 60,  # 1 minute window
    'rate_limit_max_requests': 100,  # 100 requests per minute per IP
    'max_failed_attempts': 5,  # Lock after 5 failed attempts
    'lockout_duration': 900,  # 15 minutes lockout
    'max_request_size': 10 * 1024 * 1024,  # 10MB max request size
    'session_timeout': 3600,  # 1 hour session timeout
}

class ServerConfig:
    """Server configuration for D: drive operation with essential security"""
    
    def __init__(self):
        # Base paths using CONFIG
        self.BASE_DIR = str(CONFIG.DATA_DIR / "server")
        self.DATA_DIR = os.path.join(self.BASE_DIR, "data")
        self.MOBILE_DATA_DIR = os.path.join(self.DATA_DIR, "mobile_data")
        self.VEHICLE_PROFILES_DIR = os.path.join(self.DATA_DIR, "vehicle_profiles")
        self.AI_MODELS_DIR = os.path.join(self.DATA_DIR, "ai_models")
        self.LOGS_DIR = os.path.join(self.BASE_DIR, "logs")
        self.CONFIG_DIR = os.path.join(self.BASE_DIR, "config")
        self.TEMP_DIR = os.path.join(self.BASE_DIR, "temp")
        
        # Server settings
        self.SERVER_PORT = 8080
        self.SERVER_HOST = "0.0.0.0"
        self.MAX_FILE_SIZE = 100 * 1024 * 1024
        self.ALLOWED_ORIGINS = ["*"]
        
        # Database settings
        self.DATABASE_PATH = os.path.join(self.DATA_DIR, "predictai.db")
        
        # API Security
        self.API_KEYS_FILE = os.path.join(self.CONFIG_DIR, "api_keys.json")
        self.REQUIRE_API_KEY = True
        
        # Essential Security Features
        self.security_enabled = True
        self.failed_attempts = defaultdict(list)
        self.locked_ips = {}
        self.rate_limiter = defaultdict(lambda: {
            'requests': deque(maxlen=SECURITY_CONFIG['rate_limit_max_requests']),
            'window_start': time.time()
        })
        self.audit_log = deque(maxlen=1000)
        self.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Content-Security-Policy': "default-src 'self'"
        }
        
        # Create directories if they don't exist
        self.create_directories()
        self.setup_database()
        self.setup_api_keys()
        
        print("✅ Essential security systems initialized")
    
    def create_directories(self):
        """Create all necessary directories"""
        directories = [
            self.BASE_DIR,
            self.DATA_DIR,
            self.MOBILE_DATA_DIR,
            self.VEHICLE_PROFILES_DIR,
            self.AI_MODELS_DIR,
            self.LOGS_DIR,
            self.CONFIG_DIR,
            self.TEMP_DIR
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
    
    def setup_database(self):
        """Initialize SQLite database for mobile data"""
        try:
            conn = sqlite3.connect(self.DATABASE_PATH)
            cursor = conn.cursor()
            
            # Create mobile data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mobile_vehicle_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT,
                    timestamp TEXT,
                    source TEXT,
                    rpm REAL,
                    speed REAL,
                    coolant_temp REAL,
                    battery_voltage REAL,
                    engine_load REAL,
                    intake_pressure REAL,
                    air_temp REAL,
                    maf_flow REAL,
                    throttle_pos REAL,
                    fuel_pressure REAL,
                    latitude REAL,
                    longitude REAL,
                    acceleration_x REAL,
                    acceleration_y REAL,
                    acceleration_z REAL,
                    raw_data TEXT,
                    health_score REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create API access log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key_hash TEXT,
                    endpoint TEXT,
                    method TEXT,
                    status_code INTEGER,
                    client_ip TEXT,
                    user_agent TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create security events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    details TEXT,
                    client_ip TEXT,
                    user_agent TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_mobile_data_timestamp 
                ON mobile_vehicle_data(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_mobile_data_profile 
                ON mobile_vehicle_data(profile_id)
            ''')
            
            conn.commit()
            conn.close()
            print(f"💾 Database initialized: {self.DATABASE_PATH}")
            
        except Exception as e:
            print(f"❌ Database setup error: {e}")
    
    def setup_api_keys(self):
        """Initialize API keys configuration"""
        try:
            if not os.path.exists(self.API_KEYS_FILE):
                # Generate a default API key (9 characters)
                default_key = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789') for _ in range(9))
                api_keys = {
                    "default": {
                        "key_hash": hashlib.sha256(default_key.encode()).hexdigest(),
                        "name": "Default Mobile App Key",
                        "created": datetime.now().isoformat(),
                        "permissions": ["vehicle_data", "predict", "diagnostic"]
                    }
                }
                
                with open(self.API_KEYS_FILE, 'w') as f:
                    json.dump(api_keys, f, indent=2)
                
                print(f"🔑 Default API key generated: {default_key}")
                print("⚠️  Save this key for mobile app configuration!")
            
        except Exception as e:
            print(f"❌ API keys setup error: {e}")
    
    def validate_api_key(self, api_key: str, required_permission: str = None) -> bool:
        """Validate API key with enhanced security checks"""
        try:
            if not self.REQUIRE_API_KEY:
                return True
                
            if not api_key:
                return False
            
            # Get client IP for security checks (will be passed separately)
            client_ip = None  # This will be set by the request handler
            
            with open(self.API_KEYS_FILE, 'r') as f:
                api_keys = json.load(f)
            
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            for key_name, key_data in api_keys.items():
                if key_data['key_hash'] == key_hash:
                    if required_permission:
                        return required_permission in key_data.get('permissions', [])
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ API key validation error: {e}")
            return False
    
    def validate_api_key_with_security(self, api_key: str, required_permission: str = None, client_ip: str = None) -> Tuple[bool, Dict[str, Any]]:
        """Enhanced API key validation with security features"""
        try:
            if not self.REQUIRE_API_KEY:
                return True, {'status': 'security_disabled'}
                
            if not api_key:
                self._log_security_event('missing_api_key', 'No API key provided', client_ip)
                return False, {'error': 'API key required'}
            
            # Check IP lockout
            if client_ip and client_ip in self.locked_ips:
                lockout_info = self.locked_ips[client_ip]
                if time.time() < lockout_info['unlock_time']:
                    remaining_time = int(lockout_info['unlock_time'] - time.time())
                    self._log_security_event('ip_locked', f'Locked IP: {client_ip}, remaining: {remaining_time}s', client_ip)
                    return False, {'error': f'IP locked. Try again in {remaining_time} seconds'}
            
            # Check rate limiting
            if client_ip and not self._check_rate_limit(client_ip):
                self._log_security_event('rate_limit_exceeded', f'Rate limit exceeded: {client_ip}', client_ip)
                return False, {'error': 'Rate limit exceeded. Try again later'}
            
            # Validate API key
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            with open(self.API_KEYS_FILE, 'r') as f:
                api_keys = json.load(f)
            
            key_found = False
            key_data = None
            
            for key_name, key_info in api_keys.items():
                if key_info['key_hash'] == key_hash:
                    key_found = True
                    key_data = key_info
                    key_data['key_name'] = key_name
                    break
            
            if not key_found:
                self._log_failed_attempt(client_ip, 'invalid_api_key')
                return False, {'error': 'Invalid API key'}
            
            # Check permissions
            if required_permission and required_permission not in key_data.get('permissions', []):
                self._log_security_event('permission_denied', f'Insufficient permissions: {required_permission}', client_ip)
                return False, {'error': f'Insufficient permissions. Required: {required_permission}'}
            
            # Clear failed attempts for this IP
            if client_ip in self.failed_attempts:
                del self.failed_attempts[client_ip]
            
            self._log_security_event('api_success', f'API key validated: {key_data.get("name", "unknown")}', client_ip)
            
            return True, {
                'key_name': key_data.get('name', 'unknown'),
                'permissions': key_data.get('permissions', []),
                'status': 'valid'
            }
            
        except Exception as e:
            self._log_security_event('validation_error', f'API key validation error: {str(e)}', client_ip)
            return False, {'error': 'Validation error'}
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client has exceeded rate limit"""
        try:
            if not client_ip:
                return True
            
            current_time = time.time()
            client_data = self.rate_limiter[client_ip]
            
            # Clean old requests outside the window
            while (client_data['requests'] and 
                   current_time - client_data['window_start'] > SECURITY_CONFIG['rate_limit_window']):
                client_data['requests'].popleft()
            
            # Check if rate limit exceeded
            if len(client_data['requests']) >= SECURITY_CONFIG['rate_limit_max_requests']:
                # Reset window start time
                client_data['window_start'] = current_time
                return False
            
            # Add current request
            client_data['requests'].append(current_time)
            
            return True
            
        except Exception as e:
            print(f"❌ Error checking rate limit: {e}")
            return True  # Fail open - allow request if rate limiting fails
    
    def _log_failed_attempt(self, client_ip: str, reason: str):
        """Log failed authentication attempt"""
        try:
            if not client_ip:
                return
            
            current_time = time.time()
            self.failed_attempts[client_ip].append({
                'timestamp': current_time,
                'reason': reason
            })
            
            # Check if should lock IP
            recent_failures = [
                attempt for attempt in self.failed_attempts[client_ip]
                if current_time - attempt['timestamp'] < SECURITY_CONFIG['lockout_duration']
            ]
            
            if len(recent_failures) >= SECURITY_CONFIG['max_failed_attempts']:
                # Lock IP
                self.locked_ips[client_ip] = {
                    'locked_at': current_time,
                    'unlock_time': current_time + SECURITY_CONFIG['lockout_duration'],
                    'reason': 'Too many failed attempts'
                }
                
                self._log_security_event('ip_locked', f'IP locked: {client_ip}, reason: {reason}', client_ip)
            
            # Clean old failed attempts
            self.failed_attempts[client_ip] = [
                attempt for attempt in self.failed_attempts[client_ip]
                if current_time - attempt['timestamp'] < SECURITY_CONFIG['lockout_duration'] * 2  # Keep slightly longer for analysis
            ]
            
        except Exception as e:
            print(f"❌ Error logging failed attempt: {e}")
    
    def _log_security_event(self, event_type: str, details: str, client_ip: str = None, user_agent: str = None):
        """Log security event"""
        try:
            event = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'details': details,
                'client_ip': client_ip,
                'user_agent': user_agent
            }
            
            # Add to audit log
            self.audit_log.append(event)
            
            # Keep only recent events in memory
            if len(self.audit_log) > 1000:
                self.audit_log = self.audit_log[-1000:]
            
            # Log to database
            self._log_security_to_database(event)
            
        except Exception as e:
            print(f"❌ Error logging security event: {e}")
    
    def _log_security_to_database(self, event: Dict[str, Any]):
        """Log security event to database"""
        try:
            conn = sqlite3.connect(self.DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO security_events 
                (event_type, details, client_ip, user_agent)
                VALUES (?, ?, ?, ?)
            ''', (
                event['event_type'],
                event['details'],
                event['client_ip'],
                event.get('user_agent', '')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error writing security event to database: {e}")
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get security status summary"""
        try:
            current_time = time.time()
            
            # Calculate recent statistics
            recent_events = [
                e for e in self.audit_log
                if (datetime.now() - datetime.fromisoformat(e['timestamp'])).total_seconds() < 86400  # Last 24 hours
            ]
            
            # Count events by type
            event_counts = {}
            for event in recent_events:
                event_type = event.get('event_type', 'unknown')
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            return {
                'security_enabled': self.security_enabled,
                'locked_ips_count': len(self.locked_ips),
                'recent_events_24h': len(recent_events),
                'event_counts': event_counts,
                'rate_limiting_active': True,
                'failed_attempts_24h': event_counts.get('failed_attempt', 0),
                'blocked_requests_24h': event_counts.get('rate_limit_exceeded', 0) + event_counts.get('ip_locked', 0)
            }
            
        except Exception as e:
            print(f"❌ Error getting security status: {e}")
            return {
                'security_enabled': False,
                'error': str(e)
            }
    
    def log_api_access(self, api_key_hash: str, endpoint: str, method: str, 
                      status_code: int, client_ip: str, user_agent: str):
        """Log API access for security monitoring"""
        try:
            conn = sqlite3.connect(self.DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO api_access_log 
                (api_key_hash, endpoint, method, status_code, client_ip, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (api_key_hash, endpoint, method, status_code, client_ip, user_agent))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ API access logging error: {e}")
    
    def get_network_info(self):
        """Get network information for server access"""
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            return {
                "local_ip": local_ip,
                "hostname": hostname,
                "server_url": f"http://{local_ip}:{self.SERVER_PORT}",
                "base_directory": self.BASE_DIR
            }
        except:
            return {
                "local_ip": "127.0.0.1",
                "hostname": "localhost",
                "server_url": f"http://127.0.0.1:{self.SERVER_PORT}",
                "base_directory": self.BASE_DIR
            }
    
    def save_config(self):
        """Save configuration to file"""
        config_file = os.path.join(self.CONFIG_DIR, "server_config.json")
        config_data = {
            "server_port": self.SERVER_PORT,
            "base_directory": self.BASE_DIR,
            "data_directories": {
                "mobile_data": self.MOBILE_DATA_DIR,
                "vehicle_profiles": self.VEHICLE_PROFILES_DIR,
                "ai_models": self.AI_MODELS_DIR,
                "logs": self.LOGS_DIR
            },
            "network_info": self.get_network_info(),
            "database_path": self.DATABASE_PATH,
            "security_enabled": self.security_enabled
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"💾 Configuration saved to: {config_file}")
        return config_file

# Global configuration instance
config = ServerConfig()

if HAS_PYQT:
    class DDriveMobileDataServer(QObject):
        """Enhanced mobile data server for D: drive operation with essential security"""

        # Signals for real-time data integration
        mobile_data_received = Signal(dict)  # Emits when Android data arrives
        server_status_changed = Signal(bool)  # Emits when server starts/stops
        connection_status = Signal(str, str)  # Emits (device_id, status)

        def __init__(self, port=8080, ai_system=None):
            super().__init__()
            self.config = config
            self.port = port
            self.ai_system = ai_system
            self.server = None
            self.server_thread = None
            self.is_running = False
            self.collected_data = []
            self.active_profile = None  # Current loaded profile

            # Update server configuration
            self.config.SERVER_PORT = port

            print(f"📁 D: Drive Server initialized at: {self.config.BASE_DIR}")
            print(f"🔒 Essential security: ENABLED")

        def set_active_profile(self, profile_name):
            """Set the currently active profile for data association"""
            self.active_profile = profile_name
            print(f"📱 Mobile server profile set to: {profile_name}")

        def _sanitize_vehicle_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
            """Sanitize vehicle data to prevent injection attacks"""
            try:
                sanitized = {}

                # Define allowed fields and their expected types
                allowed_fields = {
                    'profile_id': str,
                    'timestamp': str,
                    'source': str,
                    'rpm': (int, float),
                    'speed': (int, float),
                    'coolant_temp': (int, float),
                    'battery_voltage': (int, float),
                    'engine_load': (int, float),
                    'intake_pressure': (int, float),
                    'air_temp': (int, float),
                    'maf_flow': (int, float),
                    'throttle_pos': (int, float),
                    'fuel_pressure': (int, float),
                    'latitude': (int, float),
                    'longitude': (int, float),
                    'acceleration_x': (int, float),
                    'acceleration_y': (int, float),
                    'acceleration_z': (int, float),
                    'vin': str,
                    'license_plate': str,
                    'owner_info': str,
                    'obd': dict,        # Allow nested OBD data
                    'dtc_list': list    # Allow DTC codes
                }

                for field, value in data.items():
                    if field in allowed_fields:
                        expected_type = allowed_fields[field]

                        # Type validation
                        if expected_type == str:
                            # Basic sanitization for strings
                            sanitized_value = str(value).strip()
                            # Limit length to prevent abuse
                            sanitized[field] = sanitized_value[:255]
                        elif expected_type in (int, float):
                            try:
                                sanitized[field] = float(value)
                            except (ValueError, TypeError):
                                sanitized[field] = 0.0  # Default safe value
                        elif expected_type in (dict, list):
                            sanitized[field] = value  # Allow complex types
                        else:
                            sanitized[field] = value

                return sanitized

            except Exception as e:
                print(f"❌ Error sanitizing vehicle data: {e}")
                return data  # Return original data if sanitization fails

        def get_security_status(self) -> Dict[str, Any]:
            """Get comprehensive security status"""
            return self.config.get_security_status()

        def start_server(self):
            """Start the mobile data server on D: drive with essential security"""
            try:
                # Run startup integrity check before server starts
                if INTEGRITY_CHECK_AVAILABLE:
                    print("Running startup integrity check...")
                    passed, report = run_startup_integrity_check()

                    if not passed:
                        violations = report.get('violations', [])
                        critical = [v for v in violations if v.get('severity') == 'critical']

                        if critical:
                            print(f"CRITICAL: {len(critical)} integrity violations detected")
                            for v in critical[:3]:  # Show first 3
                                print(f"  - {v.get('description', 'Unknown violation')}")
                            print("Server startup blocked. Run 'python system_integrity.py --repair' to fix.")
                            return False
                        else:
                            print(f"Integrity check: {len(violations)} non-critical issues (auto-repaired)")
                    else:
                        print("Startup integrity check passed")

                # Create custom handler class
                class MobileDataHandler(http.server.SimpleHTTPRequestHandler):
                    ai_system = self.ai_system
                    server_instance = self
                    config = self.config

                    def _get_api_key(self):
                        """Extract API key from headers"""
                        auth_header = self.headers.get('Authorization', '')
                        if auth_header.startswith('Bearer '):
                            return auth_header[7:]
                        return self.headers.get('X-API-Key', '')

                    def _authenticate(self, required_permission=None):
                        """Enhanced authentication with security features"""
                        try:
                            api_key = self._get_api_key()
                            client_ip = self.client_address[0] if self.client_address else None
                            user_agent = self.headers.get('User-Agent', 'Unknown')

                            # Use enhanced security validation
                            is_valid, key_data = self.config.validate_api_key_with_security(
                                api_key, required_permission, client_ip
                            )

                            if not is_valid:
                                self.send_error(401, key_data.get('error', 'Authentication failed'))
                                return False

                            # Log access (original functionality preserved)
                            key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else 'anonymous'
                            self.config.log_api_access(
                                key_hash, self.path, self.command,
                                200, client_ip, user_agent
                            )
                            return True

                        except Exception as e:
                            client_ip = self.client_address[0] if self.client_address else None
                            self.config._log_security_event('authentication_error', f'Auth error: {str(e)}', client_ip)
                            self.send_error(401, "Authentication failed")
                            return False

                    def _add_security_headers(self):
                        """Add security headers to response"""
                        for header, value in self.config.security_headers.items():
                            self.send_header(header, value)

                        # Add CORS headers (preserve existing functionality)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key')

                    def do_GET(self):
                        """Handle GET requests with security"""
                        if self.path == '/status':
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self._add_security_headers()
                            self.end_headers()
                    
                            status = {
                                'status': 'running',
                                'service': 'Car AI Mobile Data Server - D: Drive',
                                'timestamp': datetime.now().isoformat(),
                                'data_received': len(self.server_instance.collected_data),
                                'server_info': self.config.get_network_info(),
                                'storage_path': self.config.BASE_DIR,
                                'security_enabled': self.config.security_enabled
                            }
                    
                            self.wfile.write(json.dumps(status).encode())
                
                        elif self.path == '/config':
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self._add_security_headers()
                            self.end_headers()
                    
                            config_info = {
                                'base_directory': self.config.BASE_DIR,
                                'port': self.config.SERVER_PORT,
                                'data_directories': {
                                    'mobile_data': self.config.MOBILE_DATA_DIR,
                                    'vehicle_profiles': self.config.VEHICLE_PROFILES_DIR,
                                    'ai_models': self.config.AI_MODELS_DIR
                                },
                                'database_path': self.config.DATABASE_PATH,
                                'security': {
                                    'enabled': self.config.security_enabled,
                                    'api_key_required': self.config.REQUIRE_API_KEY
                                }
                            }
                    
                            self.wfile.write(json.dumps(config_info).encode())
                
                        elif self.path == '/security/status':
                            # New security status endpoint
                            if not self._authenticate('diagnostic'):
                                return

                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self._add_security_headers()
                            self.end_headers()

                            security_status = self.server_instance.get_security_status()
                            self.wfile.write(json.dumps(security_status).encode())

                        # ===== NEW DESKTOP CLIENT ENDPOINTS =====

                        elif self.path == '/api/health':
                            # Health check endpoint (no auth required)
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self._add_security_headers()
                            self.end_headers()

                            health = {
                                'status': 'healthy',
                                'timestamp': datetime.now().isoformat(),
                                'service': 'Predict AI Server',
                                'version': '1.0.0'
                            }
                            self.wfile.write(json.dumps(health).encode())

                        elif self.path == '/api/profiles':
                            # List all vehicle profiles
                            if not self._authenticate('vehicle_data'):
                                return

                            try:
                                profiles = self.server_instance.get_all_profiles()
                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self._add_security_headers()
                                self.end_headers()
                                self.wfile.write(json.dumps(profiles).encode())
                            except Exception as e:
                                self.send_error(500, f"Error: {str(e)}")

                        elif self.path.startswith('/api/profiles/') and '/latest' in self.path:
                            # Get latest data for a vehicle profile
                            # Format: /api/profiles/{profile_id}/latest
                            if not self._authenticate('vehicle_data'):
                                return

                            try:
                                profile_id = self.path.split('/')[3]
                                data = self.server_instance.get_mobile_data_by_profile(profile_id, limit=1)

                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self._add_security_headers()
                                self.end_headers()

                                response = {
                                    'profile_id': profile_id,
                                    'data': data[0] if data else None,
                                    'timestamp': datetime.now().isoformat()
                                }
                                self.wfile.write(json.dumps(response).encode())
                            except Exception as e:
                                self.send_error(500, f"Error: {str(e)}")

                        elif self.path.startswith('/api/profiles/') and '/since/' in self.path:
                            # Get new data since timestamp
                            # Format: /api/profiles/{profile_id}/since/{timestamp}
                            if not self._authenticate('vehicle_data'):
                                return

                            try:
                                parts = self.path.split('/')
                                profile_id = parts[3]
                                since_timestamp = parts[5]

                                data = self.server_instance.get_mobile_data_since(profile_id, since_timestamp)

                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self._add_security_headers()
                                self.end_headers()

                                response = {
                                    'profile_id': profile_id,
                                    'since': since_timestamp,
                                    'count': len(data),
                                    'data': data,
                                    'timestamp': datetime.now().isoformat()
                                }
                                self.wfile.write(json.dumps(response).encode())
                            except Exception as e:
                                self.send_error(500, f"Error: {str(e)}")

                        elif self.path.startswith('/api/profiles/') and '/sessions' in self.path:
                            # Get session list for a profile
                            # Format: /api/profiles/{profile_id}/sessions
                            if not self._authenticate('vehicle_data'):
                                return

                            try:
                                profile_id = self.path.split('/')[3]
                                sessions = self.server_instance.get_mobile_sessions_by_profile(profile_id)

                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self._add_security_headers()
                                self.end_headers()

                                response = {
                                    'profile_id': profile_id,
                                    'sessions': sessions,
                                    'count': len(sessions),
                                    'timestamp': datetime.now().isoformat()
                                }
                                self.wfile.write(json.dumps(response).encode())
                            except Exception as e:
                                self.send_error(500, f"Error: {str(e)}")

                        elif self.path == '/api/stats':
                            # Get server statistics
                            if not self._authenticate('vehicle_data'):
                                return

                            try:
                                stats = self.server_instance.get_database_stats()

                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self._add_security_headers()
                                self.end_headers()

                                response = {
                                    'database': stats,
                                    'server': self.server_instance.get_server_info(),
                                    'timestamp': datetime.now().isoformat()
                                }
                                self.wfile.write(json.dumps(response).encode())
                            except Exception as e:
                                self.send_error(500, f"Error: {str(e)}")

                        else:
                            self.send_response(404)
                            self._add_security_headers()
                            self.end_headers()
            
                    def do_POST(self):
                        """Handle POST requests from mobile apps with enhanced security"""
                        if self.path == '/api/vehicle-data':
                            self._handle_vehicle_data()
                        elif self.path == '/api/predict':
                            self._handle_prediction()
                        elif self.path == '/api/diagnostic':
                            self._handle_diagnostic()
                        else:
                            self.send_response(404)
                            self._add_security_headers()
                            self.end_headers()
            
                    def _handle_vehicle_data(self):
                        """Handle vehicle data submission with security enhancements"""
                        try:
                            # Authenticate request
                            if not self._authenticate('vehicle_data'):
                                return
                    
                            content_length = int(self.headers.get('Content-Length', 0))
                            if content_length == 0:
                                self.send_error(400, "Empty request body")
                                return
                    
                            # Check request size limit
                            if content_length > SECURITY_CONFIG['max_request_size']:
                                self.send_error(413, "Request too large")
                                return
                        
                            post_data = self.rfile.read(content_length)
                            mobile_data = json.loads(post_data.decode('utf-8'))
                    
                            # Sanitize input data
                            sanitized_data = self.server_instance._sanitize_vehicle_data(mobile_data)

                            # Add to collected_data for real-time access
                            if hasattr(self.server_instance, 'collected_data'):
                                self.server_instance.collected_data.append(mobile_data)

                            # Save directly to database (original functionality preserved)
                            success = self.server_instance.save_to_database(sanitized_data)
                    
                            # Send response
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self._add_security_headers()
                            self.end_headers()
                    
                            response = {
                                'status': 'success' if success else 'error',
                                'message': 'Data saved to database' if success else 'Error saving data',
                                'timestamp': datetime.now().isoformat(),
                                'database_location': self.config.DATABASE_PATH if success else None
                            }
                    
                            self.wfile.write(json.dumps(response).encode())
                    
                        except json.JSONDecodeError:
                            client_ip = self.client_address[0] if self.client_address else None
                            self.config._log_security_event('invalid_json', 'Invalid JSON in vehicle data', client_ip)
                            self.send_error(400, "Invalid JSON data")
                        except Exception as e:
                            client_ip = self.client_address[0] if self.client_address else None
                            self.config._log_security_event('data_processing_error', f'Error processing data: {str(e)}', client_ip)
                            self.send_error(400, f"Error processing data: {str(e)}")
            
                    def _handle_prediction(self):
                        """Handle AI prediction requests with security"""
                        try:
                            # Authenticate request
                            if not self._authenticate('predict'):
                                return
                    
                            content_length = int(self.headers.get('Content-Length', 0))
                            post_data = self.rfile.read(content_length)
                            prediction_data = json.loads(post_data.decode('utf-8'))
                    
                            # Use internal AI system for prediction (original functionality preserved)
                            prediction_result = self.server_instance.get_ai_prediction(prediction_data)
                    
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self._add_security_headers()
                            self.end_headers()
                            self.wfile.write(json.dumps(prediction_result).encode())
                    
                        except Exception as e:
                            client_ip = self.client_address[0] if self.client_address else None
                            self.config._log_security_event('prediction_error', f'Prediction error: {str(e)}', client_ip)
                            self.send_error(400, f"Prediction error: {str(e)}")
            
                    def _handle_diagnostic(self):
                        """Handle diagnostic requests with security"""
                        try:
                            # Authenticate request
                            if not self._authenticate('diagnostic'):
                                return
                    
                            content_length = int(self.headers.get('Content-Length', 0))
                            post_data = self.rfile.read(content_length)
                            diagnostic_data = json.loads(post_data.decode('utf-8'))
                    
                            # Perform basic diagnostic analysis (original functionality preserved)
                            diagnostic_result = self.server_instance.perform_diagnostic(diagnostic_data)
                    
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self._add_security_headers()
                            self.end_headers()
                            self.wfile.write(json.dumps(diagnostic_result).encode())
                    
                        except Exception as e:
                            client_ip = self.client_address[0] if self.client_address else None
                            self.config._log_security_event('diagnostic_error', f'Diagnostic error: {str(e)}', client_ip)
                            self.send_error(400, f"Diagnostic error: {str(e)}")
            
                    def do_OPTIONS(self):
                        """Handle OPTIONS requests for CORS with security headers"""
                        self.send_response(200)
                        self._add_security_headers()
                        self.end_headers()
            
                    def log_message(self, format, *args):
                        """Custom log message format"""
                        print(f"📱 Mobile Server - {format % args}")

                # Create and start server
                self.server = socketserver.TCPServer(("", self.port), MobileDataHandler)
                self.is_running = True

                # Start server in a separate thread
                self.server_thread = threading.Thread(target=self.server.serve_forever)
                self.server_thread.daemon = True
                self.server_thread.start()

                print(f"📱 D: Drive Mobile Server started on port {self.port}")
                print(f"💾 Data storage: {self.config.BASE_DIR}")
                print(f"🔐 API Key protection: {'ENABLED' if self.config.REQUIRE_API_KEY else 'DISABLED'}")
                print(f"🛡️  Essential security: ENABLED")
                print(f"   ├─ Rate limiting: {SECURITY_CONFIG['rate_limit_max_requests']} requests/minute")
                print(f"   ├─ IP lockout: {SECURITY_CONFIG['max_failed_attempts']} failed attempts")
                print(f"   ├─ Input sanitization: ACTIVE")
                print(f"   └─ Security headers: ACTIVE")
                return True

            except Exception as e:
                print(f"❌ Failed to start D: Drive server: {e}")
                return False
    
    def stop_server(self):
        """Stop the mobile data server"""
        if self.server:
            self.is_running = False
            self.server.shutdown()
            self.server.server_close()
            print("🛑 D: Drive Mobile Server stopped")
    
    def save_to_database(self, data: Dict) -> bool:
        """Save mobile data directly to SQLite database"""
        try:
            conn = sqlite3.connect(self.config.DATABASE_PATH)
            cursor = conn.cursor()
            
            # Extract vehicle data fields
            profile_id = data.get('profile_id', 'mobile_unknown')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            # Insert into database
            cursor.execute('''
                INSERT INTO mobile_vehicle_data 
                (profile_id, timestamp, source, rpm, speed, coolant_temp, battery_voltage,
                 engine_load, intake_pressure, air_temp, maf_flow, throttle_pos, fuel_pressure,
                 latitude, longitude, acceleration_x, acceleration_y, acceleration_z,
                 raw_data, health_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                profile_id,
                timestamp,
                data.get('source', 'mobile_app'),
                data.get('rpm'),
                data.get('speed'),
                data.get('coolant_temp'),
                data.get('battery_voltage'),
                data.get('engine_load'),
                data.get('intake_pressure'),
                data.get('air_temp'),
                data.get('maf_flow'),
                data.get('throttle_pos'),
                data.get('fuel_pressure'),
                data.get('latitude'),
                data.get('longitude'),
                data.get('acceleration_x'),
                data.get('acceleration_y'),
                data.get('acceleration_z'),
                json.dumps(data),  # Store raw data as JSON
                data.get('health_score', self._calculate_health_score(data))
            ))
            
            conn.commit()
            conn.close()
            
            # Also save to JSON file for backup
            self._save_json_backup(data)
            
            print(f"💾 Mobile data saved to database: {profile_id} at {timestamp}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving mobile data to database: {e}")
            return False
    
    def _save_json_backup(self, data: Dict):
        """Save JSON backup of mobile data"""
        try:
            timestamp = datetime.now().isoformat().replace(':', '-').replace('.', '-')
            filename = f"mobile_backup_{timestamp}.json"
            filepath = os.path.join(self.config.MOBILE_DATA_DIR, filename)
            
            data_with_metadata = {
                'timestamp': timestamp,
                'data': data,
                'source': 'mobile_app',
                'database_saved': True
            }
            
            with open(filepath, 'w') as f:
                json.dump(data_with_metadata, f, indent=2)
                
        except Exception as e:
            print(f"❌ JSON backup error: {e}")
    
    def get_ai_prediction(self, prediction_data: Dict) -> Dict:
        """Get prediction from internal AI system only"""
        try:
            # Use internal AI system if available
            if (self.ai_system and 
                hasattr(self.ai_system, 'ai_engine') and 
                self.ai_system.ai_engine.csv_models):
                
                # Convert mobile data to AI input format
                ai_input = self._prepare_ai_input(prediction_data)
                
                # Get prediction from AI engine
                prediction, probability, explanation = self.ai_system.ai_engine.predict_from_csv_model(
                    ai_input, 'ensemble'
                )
                
                return {
                    'prediction': int(prediction),
                    'confidence': float(probability) if isinstance(probability, (int, float)) else float(np.max(probability)),
                    'probabilities': probability.tolist() if hasattr(probability, 'tolist') else probability,
                    'explanation': explanation,
                    'timestamp': datetime.now().isoformat(),
                    'model_used': 'ensemble',
                    'ai_source': 'internal'
                }
            else:
                # Fallback to rule-based prediction
                return self._get_rule_based_prediction(prediction_data)
                
        except Exception as e:
            print(f"❌ AI prediction error: {e}")
            return {
                'prediction': -1,
                'confidence': 0.0,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'ai_source': 'error'
            }
    
    def _prepare_ai_input(self, mobile_data: Dict) -> Dict:
        """Prepare mobile data for AI model input"""
        # Map mobile data fields to AI model expected features
        feature_mapping = {
            'rpm': 'rpm',
            'speed': 'speed', 
            'coolant_temp': 'coolant_temp',
            'battery_voltage': 'voltage',
            'engine_load': 'engine_load',
            'intake_pressure': 'intake_pressure',
            'air_temp': 'air_temp',
            'maf_flow': 'maf_flow'
        }
        
        ai_input = {}
        for mobile_key, ai_key in feature_mapping.items():
            if mobile_key in mobile_data:
                ai_input[ai_key] = mobile_data[mobile_key]
        
        return ai_input
    
    def _get_rule_based_prediction(self, data: Dict) -> Dict:
        """Fallback rule-based prediction when AI is unavailable"""
        health_score = self._calculate_health_score(data)
        
        if health_score >= 80:
            prediction = 0  # Good
            confidence = 0.85
            explanation = "Vehicle operating within normal parameters"
        elif health_score >= 60:
            prediction = 1  # Warning
            confidence = 0.70
            explanation = "Minor issues detected, monitor closely"
        else:
            prediction = 2  # Critical
            confidence = 0.90
            explanation = "Immediate attention required"
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'explanation': explanation,
            'health_score': health_score,
            'timestamp': datetime.now().isoformat(),
            'model_used': 'rule_based',
            'ai_source': 'rule_based_fallback'
        }
    
    def _calculate_health_score(self, data: Dict) -> float:
        """Calculate health score from mobile data"""
        score = 100.0
        
        # Deduct points for various issues
        if data.get('coolant_temp', 0) > 100:
            score -= 20
        
        if data.get('battery_voltage', 0) < 12.0:
            score -= 30
            
        if data.get('rpm', 0) > 4000:
            score -= 10
            
        if data.get('engine_load', 0) > 80:
            score -= 15
            
        return max(0.0, score)
    
    def perform_diagnostic(self, diagnostic_data):
        """Perform diagnostic analysis on vehicle data"""
        try:
            # Basic diagnostic checks
            issues = []
            recommendations = []
            
            # Check engine temperature
            if 'engine_temp' in diagnostic_data:
                temp = diagnostic_data['engine_temp']
                if temp > 100:
                    issues.append("Engine running hot")
                    recommendations.append("Check coolant level and radiator")
                elif temp < 70:
                    issues.append("Engine running cold")
                    recommendations.append("Allow engine to warm up properly")
            
            # Check battery voltage
            if 'battery_voltage' in diagnostic_data:
                voltage = diagnostic_data['battery_voltage']
                if voltage < 11.5:
                    issues.append("Low battery voltage")
                    recommendations.append("Check battery and charging system")
                elif voltage > 14.5:
                    issues.append("High battery voltage")
                    recommendations.append("Check voltage regulator")
            
            # Check RPM
            if 'rpm' in diagnostic_data:
                rpm = diagnostic_data['rpm']
                if rpm > 4000:
                    issues.append("High RPM detected")
                    recommendations.append("Consider shifting to higher gear")
            
            return {
                'diagnostic_timestamp': datetime.now().isoformat(),
                'issues_found': issues,
                'recommendations': recommendations,
                'overall_status': 'good' if not issues else 'attention_needed',
                'issues_count': len(issues)
            }
            
        except Exception as e:
            return {
                'diagnostic_timestamp': datetime.now().isoformat(),
                'error': str(e),
                'overall_status': 'diagnostic_failed'
            }
    
    def get_database_stats(self):
        """Get database statistics"""
        try:
            conn = sqlite3.connect(self.config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM mobile_vehicle_data")
            total_records = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT profile_id) FROM mobile_vehicle_data")
            unique_vehicles = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(timestamp) FROM mobile_vehicle_data")
            latest_record = cursor.fetchone()[0]

            conn.close()

            return {
                'total_records': total_records,
                'unique_vehicles': unique_vehicles,
                'latest_record': latest_record,
                'database_path': self.config.DATABASE_PATH
            }

        except Exception as e:
            return {'error': str(e)}

    def get_mobile_data_by_profile(self, profile_id: str, limit: int = 100) -> List[Dict]:
        """
        Get latest mobile data for a specific profile

        Args:
            profile_id: Vehicle profile identifier
            limit: Maximum number of records to return

        Returns:
            List of data records, newest first
        """
        try:
            conn = sqlite3.connect(self.config.DATABASE_PATH)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM mobile_vehicle_data
                WHERE profile_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (profile_id, limit))

            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dictionaries
            return [dict(row) for row in rows]

        except Exception as e:
            print(f"❌ Error querying mobile data: {e}")
            return []

    def get_mobile_sessions_by_profile(self, profile_id: str) -> List[Dict]:
        """
        Get summary of all mobile sessions for a profile

        Returns:
            List of session summaries with date, duration, record count
        """
        try:
            conn = sqlite3.connect(self.config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    DATE(timestamp) as session_date,
                    COUNT(*) as record_count,
                    MIN(timestamp) as start_time,
                    MAX(timestamp) as end_time,
                    AVG(rpm) as avg_rpm,
                    AVG(speed) as avg_speed
                FROM mobile_vehicle_data
                WHERE profile_id = ?
                GROUP BY DATE(timestamp)
                ORDER BY session_date DESC
            ''', (profile_id,))

            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    'date': row[0],
                    'records': row[1],
                    'start': row[2],
                    'end': row[3],
                    'avg_rpm': row[4],
                    'avg_speed': row[5]
                })

            conn.close()
            return sessions

        except Exception as e:
            print(f"❌ Error getting sessions: {e}")
            return []

    def get_mobile_data_by_date_range(self, profile_id: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get mobile data for a specific date range

        Args:
            profile_id: Vehicle profile identifier
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        try:
            conn = sqlite3.connect(self.config.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM mobile_vehicle_data
                WHERE profile_id = ?
                AND DATE(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp ASC
            ''', (profile_id, start_date, end_date))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            print(f"❌ Error querying date range: {e}")
            return []

    def export_mobile_data_to_csv(self, profile_id: str, output_file: str) -> bool:
        """
        Export mobile data to CSV file

        Args:
            profile_id: Vehicle profile identifier
            output_file: Path to output CSV file

        Returns:
            True if successful, False otherwise
        """
        try:
            import csv

            data = self.get_mobile_data_by_profile(profile_id, limit=10000)

            if not data:
                return False

            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for row in data:
                    writer.writerow(row)

            print(f"✅ Exported {len(data)} records to {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error exporting to CSV: {e}")
            return False

    def get_all_profiles(self) -> List[str]:
        """
        Get list of all vehicle profiles from database

        Returns:
            List of profile IDs
        """
        try:
            conn = sqlite3.connect(self.config.DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT DISTINCT profile_id FROM mobile_vehicle_data
                ORDER BY profile_id
            ''')

            profiles = [row[0] for row in cursor.fetchall()]
            conn.close()

            return profiles

        except Exception as e:
            print(f"❌ Error getting profiles: {e}")
            return []

    def get_mobile_data_since(self, profile_id: str, since_timestamp: str, limit: int = 1000) -> List[Dict]:
        """
        Get mobile data since a specific timestamp

        Args:
            profile_id: Vehicle profile identifier
            since_timestamp: ISO 8601 timestamp
            limit: Maximum number of records to return

        Returns:
            List of data records newer than timestamp
        """
        try:
            conn = sqlite3.connect(self.config.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM mobile_vehicle_data
                WHERE profile_id = ?
                AND timestamp > ?
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (profile_id, since_timestamp, limit))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            print(f"❌ Error querying data since timestamp: {e}")
            return []

    def get_server_info(self):
        """Get comprehensive server information"""
        network_info = self.config.get_network_info()
        
        return {
            'server_running': self.is_running,
            'port': self.port,
            'base_directory': self.config.BASE_DIR,
            'network_info': network_info,
            'database_stats': self.get_database_stats(),
            'api_security': {
                'enabled': self.config.REQUIRE_API_KEY,
                'keys_file': self.config.API_KEYS_FILE
            },
            'enhanced_security': {
                'enabled': self.config.security_enabled,
                'rate_limiting': True,
                'input_sanitization': True,
                'security_headers': True,
                'audit_logging': True
            },
            'endpoints': {
                'status': f"{network_info['server_url']}/status",
                'vehicle_data': f"{network_info['server_url']}/api/vehicle-data",
                'prediction': f"{network_info['server_url']}/api/predict",
                'diagnostic': f"{network_info['server_url']}/api/diagnostic",
                'config': f"{network_info['server_url']}/config",
                'security_status': f"{network_info['server_url']}/security/status"
            }
        }


# Example usage and testing
if __name__ == "__main__":
    # Test the enhanced server
    print("🚗 Starting Enhanced Mobile Data Server Test...")
    
    server = DDriveMobileDataServer(port=8080)
    
    # Start server
    if server.start_server():
        print("✅ Server started successfully!")
        
        # Display server info
        info = server.get_server_info()
        print(f"📊 Database: {info['database_stats']}")
        print(f"🔐 Security: {info['api_security']}")
        print(f"🛡️  Enhanced Security: {info['enhanced_security']}")
        print(f"🌐 Endpoints: {info['endpoints']}")
        
        # Display security status
        security_status = server.get_security_status()
        print(f"🔒 Security Status: {security_status}")
        
        # Keep server running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop_server()
            print("🛑 Server stopped by user")
    else:
        print("❌ Failed to start server")