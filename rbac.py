"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Role-Based Access Control (RBAC)

Role-Based Access Control (RBAC)
Manages user roles and permissions for the PredictOBD system.
"""

import logging
import sqlite3
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import json

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class Role(Enum):
    """System roles with different access levels"""
    ADMIN = "admin"           # Full system access
    TECHNICIAN = "technician" # Vehicle diagnostics, read/write data
    CUSTOMER = "customer"     # Read-only access to their vehicles
    CO_GUARDIAN = "co_guardian"  # Co-guardian: customer access plus predictions and reports
    VIEWER = "viewer"         # Read-only, limited access


class Permission(Enum):
    """Granular permissions"""
    # Vehicle permissions
    VIEW_VEHICLES = "view_vehicles"
    EDIT_VEHICLES = "edit_vehicles"
    DELETE_VEHICLES = "delete_vehicles"
    CREATE_VEHICLES = "create_vehicles"

    # Data permissions
    VIEW_OBD_DATA = "view_obd_data"
    EXPORT_DATA = "export_data"
    DELETE_DATA = "delete_data"

    # Diagnostic permissions
    RUN_DIAGNOSTICS = "run_diagnostics"
    CLEAR_DTCS = "clear_dtcs"
    VIEW_PREDICTIONS = "view_predictions"

    # Report permissions
    GENERATE_REPORTS = "generate_reports"
    VIEW_REPORTS = "view_reports"

    # Service permissions
    LOG_SERVICE = "log_service"
    VIEW_SERVICE_HISTORY = "view_service_history"

    # Admin permissions
    MANAGE_USERS = "manage_users"
    MANAGE_SUBSCRIPTIONS = "manage_subscriptions"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    SYSTEM_SETTINGS = "system_settings"
    MANAGE_API_KEYS = "manage_api_keys"

    # AI permissions
    RETRAIN_AI = "retrain_ai"
    VIEW_AI_METRICS = "view_ai_metrics"


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions

    Role.TECHNICIAN: {
        Permission.VIEW_VEHICLES,
        Permission.EDIT_VEHICLES,
        Permission.CREATE_VEHICLES,
        Permission.VIEW_OBD_DATA,
        Permission.EXPORT_DATA,
        Permission.RUN_DIAGNOSTICS,
        Permission.CLEAR_DTCS,
        Permission.VIEW_PREDICTIONS,
        Permission.GENERATE_REPORTS,
        Permission.VIEW_REPORTS,
        Permission.LOG_SERVICE,
        Permission.VIEW_SERVICE_HISTORY,
        Permission.VIEW_AI_METRICS,
    },

    Role.CUSTOMER: {
        Permission.VIEW_VEHICLES,
        Permission.VIEW_OBD_DATA,
        Permission.VIEW_PREDICTIONS,
        Permission.VIEW_REPORTS,
        Permission.VIEW_SERVICE_HISTORY,
    },

    Role.CO_GUARDIAN: {
        Permission.VIEW_VEHICLES,
        Permission.VIEW_OBD_DATA,
        Permission.VIEW_PREDICTIONS,
        Permission.VIEW_REPORTS,
        Permission.VIEW_SERVICE_HISTORY,
        Permission.GENERATE_REPORTS,
    },

    Role.VIEWER: {
        Permission.VIEW_VEHICLES,
        Permission.VIEW_OBD_DATA,
        Permission.VIEW_REPORTS,
    },
}


@dataclass
class User:
    """User account"""
    user_id: int
    username: str
    email: str
    role: Role
    customer_id: Optional[int]  # Associated customer (for customer role)
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class RBACManager:
    """
    Manages users, roles, and permissions.

    Features:
    - User management (create, update, delete)
    - Role assignment
    - Permission checking
    - Vehicle access control
    - Audit logging
    """

    def __init__(self):
        self.db_path = CONFIG.DATA_DIR / "rbac.db"
        self._init_database()
        logger.info("RBACManager initialized")

    def _init_database(self):
        """Initialize RBAC database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        # Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'customer',
                customer_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                last_login TEXT
            )
        ''')

        # User-Vehicle access table (for granular vehicle access)
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_vehicle_access (
                user_id INTEGER,
                profile_id INTEGER,
                access_level TEXT DEFAULT 'view',
                granted_at TEXT,
                granted_by INTEGER,
                PRIMARY KEY (user_id, profile_id)
            )
        ''')

        # Session tokens table
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER,
                created_at TEXT,
                expires_at TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
        ''')

        # Access audit log
        c.execute('''
            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                resource TEXT,
                resource_id TEXT,
                result TEXT,
                timestamp TEXT,
                ip_address TEXT
            )
        ''')

        # Create default admin user if none exists
        c.execute('SELECT COUNT(*) FROM users WHERE role = ?', (Role.ADMIN.value,))
        if c.fetchone()[0] == 0:
            self._create_default_admin(c)

        conn.commit()
        conn.close()

    def _create_default_admin(self, cursor):
        """Create default admin user"""
        default_password = "admin123"  # Should be changed on first login
        password_hash = hashlib.sha256(default_password.encode()).hexdigest()

        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        ''', ('admin', 'admin@localhost', password_hash, Role.ADMIN.value, datetime.now().isoformat()))

        logger.warning("Default admin user created - username: admin, password: admin123 (CHANGE THIS!)")

    def create_user(self, username: str, email: str, password: str, role: Role,
                    customer_id: int = None, created_by: int = None) -> Optional[int]:
        """Create a new user"""
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT INTO users (username, email, password_hash, role, customer_id, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            ''', (username, email, password_hash, role.value, customer_id, datetime.now().isoformat()))

            user_id = c.lastrowid
            conn.commit()
            conn.close()

            self._log_access(created_by, 'create_user', 'user', str(user_id), 'success')
            logger.info(f"Created user: {username} with role {role.value}")
            return user_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Error creating user: {e}")
            return None

    def authenticate(self, username: str, password: str, ip_address: str = None) -> Optional[str]:
        """
        Authenticate user and return session token.

        Returns:
            Session token if authentication successful, None otherwise
        """
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                SELECT user_id, is_active FROM users
                WHERE username = ? AND password_hash = ?
            ''', (username, password_hash))

            row = c.fetchone()
            if not row:
                self._log_access(None, 'login_failed', 'auth', username, 'failed', ip_address)
                conn.close()
                return None

            user_id, is_active = row
            if not is_active:
                self._log_access(user_id, 'login_disabled', 'auth', username, 'failed', ip_address)
                conn.close()
                return None

            # Create session token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now().replace(hour=23, minute=59, second=59)

            c.execute('''
                INSERT INTO sessions (token, user_id, created_at, expires_at, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (token, user_id, datetime.now().isoformat(), expires_at.isoformat(), ip_address))

            # Update last login
            c.execute('UPDATE users SET last_login = ? WHERE user_id = ?',
                      (datetime.now().isoformat(), user_id))

            conn.commit()
            conn.close()

            self._log_access(user_id, 'login', 'auth', username, 'success', ip_address)
            return token

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    def validate_session(self, token: str) -> Optional[User]:
        """Validate session token and return user"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('''
                SELECT u.user_id, u.username, u.email, u.role, u.customer_id, u.is_active,
                       u.created_at, u.last_login, s.expires_at
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.token = ?
            ''', (token,))

            row = c.fetchone()
            conn.close()

            if not row:
                return None

            # Check expiration
            if datetime.fromisoformat(row['expires_at']) < datetime.now():
                self.logout(token)
                return None

            return User(
                user_id=row['user_id'],
                username=row['username'],
                email=row['email'],
                role=Role(row['role']),
                customer_id=row['customer_id'],
                is_active=bool(row['is_active']),
                created_at=datetime.fromisoformat(row['created_at']),
                last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None
            )

        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return None

    def logout(self, token: str):
        """Invalidate session token"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute('DELETE FROM sessions WHERE token = ?', (token,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Logout error: {e}")

    def has_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has a specific permission"""
        if not user.is_active:
            return False

        role_permissions = ROLE_PERMISSIONS.get(user.role, set())
        return permission in role_permissions

    def check_vehicle_access(self, user: User, profile_id: int, required_level: str = 'view') -> bool:
        """
        Check if user has access to a specific vehicle.

        Args:
            user: The user to check
            profile_id: Vehicle profile ID
            required_level: 'view', 'edit', or 'admin'

        Returns:
            True if user has access
        """
        # Admins have access to all vehicles
        if user.role == Role.ADMIN:
            return True

        # Technicians have access to all vehicles
        if user.role == Role.TECHNICIAN:
            return True

        # Check explicit vehicle access
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                SELECT access_level FROM user_vehicle_access
                WHERE user_id = ? AND profile_id = ?
            ''', (user.user_id, profile_id))

            row = c.fetchone()
            conn.close()

            if row:
                access_level = row[0]
                levels = {'view': 1, 'edit': 2, 'admin': 3}
                return levels.get(access_level, 0) >= levels.get(required_level, 1)

        except Exception as e:
            logger.error(f"Vehicle access check error: {e}")

        return False

    def grant_vehicle_access(self, user_id: int, profile_id: int, access_level: str,
                             granted_by: int) -> bool:
        """Grant vehicle access to a user"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT OR REPLACE INTO user_vehicle_access
                (user_id, profile_id, access_level, granted_at, granted_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, profile_id, access_level, datetime.now().isoformat(), granted_by))

            conn.commit()
            conn.close()

            self._log_access(granted_by, 'grant_access', 'vehicle', str(profile_id),
                             f'granted to user {user_id}')
            return True

        except Exception as e:
            logger.error(f"Error granting vehicle access: {e}")
            return False

    def revoke_vehicle_access(self, user_id: int, profile_id: int, revoked_by: int) -> bool:
        """Revoke vehicle access from a user"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                DELETE FROM user_vehicle_access
                WHERE user_id = ? AND profile_id = ?
            ''', (user_id, profile_id))

            conn.commit()
            conn.close()

            self._log_access(revoked_by, 'revoke_access', 'vehicle', str(profile_id),
                             f'revoked from user {user_id}')
            return True

        except Exception as e:
            logger.error(f"Error revoking vehicle access: {e}")
            return False

    def get_user_vehicles(self, user: User) -> List[int]:
        """Get list of vehicle profile IDs user has access to"""
        # Admins and technicians have access to all
        if user.role in (Role.ADMIN, Role.TECHNICIAN):
            return []  # Empty means all

        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                SELECT profile_id FROM user_vehicle_access
                WHERE user_id = ?
            ''', (user.user_id,))

            profile_ids = [row[0] for row in c.fetchall()]
            conn.close()
            return profile_ids

        except Exception as e:
            logger.error(f"Error getting user vehicles: {e}")
            return []

    def get_all_users(self) -> List[User]:
        """Get all users"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('SELECT * FROM users')
            rows = c.fetchall()
            conn.close()

            return [
                User(
                    user_id=row['user_id'],
                    username=row['username'],
                    email=row['email'],
                    role=Role(row['role']),
                    customer_id=row['customer_id'],
                    is_active=bool(row['is_active']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None
                )
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []

    def update_user_role(self, user_id: int, new_role: Role, updated_by: int) -> bool:
        """Update user's role"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('UPDATE users SET role = ? WHERE user_id = ?',
                      (new_role.value, user_id))

            conn.commit()
            conn.close()

            self._log_access(updated_by, 'update_role', 'user', str(user_id), f'new role: {new_role.value}')
            return True

        except Exception as e:
            logger.error(f"Error updating user role: {e}")
            return False

    def deactivate_user(self, user_id: int, deactivated_by: int) -> bool:
        """Deactivate a user account"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('UPDATE users SET is_active = 0 WHERE user_id = ?', (user_id,))

            # Invalidate all sessions
            c.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))

            conn.commit()
            conn.close()

            self._log_access(deactivated_by, 'deactivate_user', 'user', str(user_id), 'success')
            return True

        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False

    def _log_access(self, user_id: int, action: str, resource: str, resource_id: str,
                    result: str, ip_address: str = None):
        """Log access event"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT INTO access_log (user_id, action, resource, resource_id, result, timestamp, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, action, resource, resource_id, result, datetime.now().isoformat(), ip_address))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error logging access: {e}")

    def get_access_logs(self, user_id: int = None, days: int = 7) -> List[Dict[str, Any]]:
        """Get access logs"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).isoformat()

            if user_id:
                c.execute('''
                    SELECT * FROM access_log
                    WHERE user_id = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT 1000
                ''', (user_id, cutoff))
            else:
                c.execute('''
                    SELECT * FROM access_log
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT 1000
                ''', (cutoff,))

            rows = c.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting access logs: {e}")
            return []


# Singleton instance
_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """Get the singleton RBACManager instance."""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


def require_permission(permission: Permission):
    """Decorator to require a permission for a function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get user from kwargs or first arg
            user = kwargs.get('user') or (args[0] if args else None)
            if not user or not isinstance(user, User):
                raise PermissionError("Authentication required")

            rbac = get_rbac_manager()
            if not rbac.has_permission(user, permission):
                raise PermissionError(f"Permission denied: {permission.value}")

            return func(*args, **kwargs)
        return wrapper
    return decorator
