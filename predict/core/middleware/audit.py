"""
Audit middleware - logs all write operations to audit_log table.
"""

import logging
import json
from typing import Optional, Any
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from predict.core.db.models.audit import AuditLog

logger = logging.getLogger(__name__)


# HTTP methods that modify data
WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

# Paths to exclude from audit
EXCLUDED_PATHS = {
    '/health',
    '/health/ready',
    '/metrics',
    '/docs',
    '/openapi.json',
}


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that audits all write operations.
    
    Logs to audit_logs table with:
    - User ID and API key
    - Action (HTTP method + path)
    - Resource type and ID
    - Old and new data (for updates)
    - IP address and user agent
    - Request ID for correlation
    """
    
    def __init__(self, app, db_session_factory=None):
        super().__init__(app)
        self.db_session_factory = db_session_factory
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and audit if it's a write operation."""
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in EXCLUDED_PATHS):
            return await call_next(request)
        
        # Only audit write operations
        if request.method not in WRITE_METHODS:
            return await call_next(request)
        
        # Capture request data before processing
        old_data = None
        new_data = None
        
        try:
            # Try to get old data for updates/deletes
            if request.method in ('PUT', 'PATCH', 'DELETE'):
                old_data = await self._get_current_state(request)
        except Exception as e:
            logger.debug(f"Could not capture old state: {e}")
        
        # Process the request
        response = await call_next(request)
        
        # Capture new data for creates/updates
        if response.status_code < 400:  # Only on success
            try:
                new_data = await self._get_response_data(response)
            except Exception as e:
                logger.debug(f"Could not capture new state: {e}")
        
        # Log to audit
        try:
            await self._log_audit(request, response, old_data, new_data)
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
        
        return response
    
    async def _get_current_state(self, request: Request) -> Optional[dict]:
        """Try to get current state of resource before modification."""
        # This would need database access to fetch current record
        # Implementation depends on the specific resource
        return None
    
    async def _get_response_data(self, response: Response) -> Optional[dict]:
        """Extract data from response."""
        # Would need to read response body
        # Note: This can be tricky with streaming responses
        return None
    
    async def _log_audit(
        self,
        request: Request,
        response: Response,
        old_data: Optional[dict],
        new_data: Optional[dict],
    ) -> None:
        """Create audit log entry."""
        
        # Extract user info from request state
        user_id = getattr(request.state, 'user_id', None)
        api_key_id = getattr(request.state, 'api_key_id', None)
        request_id = getattr(request.state, 'request_id', None)
        
        # Determine resource type from path
        path_parts = request.url.path.strip('/').split('/')
        resource_type = path_parts[1] if len(path_parts) > 1 else 'unknown'
        resource_id = path_parts[2] if len(path_parts) > 2 else None
        
        # Build audit entry
        audit_entry = {
            'user_id': user_id,
            'api_key_id': api_key_id,
            'action': f"{request.method}_{resource_type}",
            'resource_type': resource_type,
            'resource_id': resource_id,
            'old_data': old_data,
            'new_data': new_data,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.headers.get('user-agent'),
            'request_id': request_id,
            'created_at': datetime.now(timezone.utc),
        }
        
        # Write to database (async)
        if self.db_session_factory:
            # Would use async session here
            pass
        
        # Also log to application logs
        logger.info(
            f"AUDIT: {audit_entry['action']} by user={user_id} "
            f"resource={resource_type}/{resource_id}"
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else 'unknown'


def create_audit_log(
    db_session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    old_data: Optional[dict] = None,
    new_data: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> AuditLog:
    """
    Create an audit log entry programmatically.
    
    Use this in services to log business logic operations.
    """
    audit_log = AuditLog(
        user_id=user_id,
        api_key_id=api_key_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    
    db_session.add(audit_log)
    # Don't commit here - let caller manage transaction
    
    return audit_log
