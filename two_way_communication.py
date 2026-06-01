"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Two Way Communication

Two-Way Communication System
Enables desktop ↔ mobile app bidirectional messaging
- Desktop can send commands to mobile (diagnostic requests, settings changes)
- Mobile can request actions from desktop (PDF generation, data export)
- Real-time command queue with response tracking
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import deque
import uuid

logger = logging.getLogger(__name__)


class TwoWayCommunicationHub:
    """
    Manages bidirectional communication between desktop and mobile app

    Desktop → Mobile Commands:
    - Request diagnostic scan
    - Clear fault codes
    - Update settings
    - Send notifications
    - Request status update

    Mobile → Desktop Requests:
    - Generate PDF report
    - Export data
    - Trigger AI analysis
    - Request historical data
    """

    def __init__(self):
        """Initialize communication hub"""

        # Command queues (per profile)
        self.desktop_to_mobile_queues = {}  # profile_id -> deque of commands
        self.mobile_to_desktop_queues = {}  # profile_id -> deque of requests

        # Command tracking
        self.pending_commands = {}  # command_id -> command_info
        self.command_responses = {}  # command_id -> response

        # Command history (last 100 per profile)
        self.command_history = {}  # profile_id -> deque of commands

        # Lock for thread safety
        self.lock = threading.Lock()

        # Auto-cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()

        logger.info("Two-Way Communication Hub initialized")

    # ==================== DESKTOP → MOBILE ====================

    def send_command_to_mobile(self, profile_id: int, command_type: str,
                               parameters: Dict[str, Any] = None,
                               priority: str = 'normal',
                               timeout_seconds: int = 60) -> Dict[str, Any]:
        """
        Send command from desktop to mobile app

        Args:
            profile_id: Target profile ID
            command_type: Command type (diagnostic_scan, clear_codes, etc.)
            parameters: Command parameters
            priority: Command priority (low, normal, high, urgent)
            timeout_seconds: Command timeout

        Returns:
            Command info with command_id
        """
        try:
            with self.lock:
                # Generate command ID
                command_id = f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

                # Create command object
                command = {
                    'command_id': command_id,
                    'profile_id': profile_id,
                    'command_type': command_type,
                    'parameters': parameters or {},
                    'priority': priority,
                    'status': 'queued',
                    'created_at': datetime.now().isoformat(),
                    'expires_at': (datetime.now() + timedelta(seconds=timeout_seconds)).isoformat(),
                    'timeout_seconds': timeout_seconds,
                    'direction': 'desktop_to_mobile'
                }

                # Initialize queue if needed
                if profile_id not in self.desktop_to_mobile_queues:
                    self.desktop_to_mobile_queues[profile_id] = deque(maxlen=50)

                # Add to queue
                self.desktop_to_mobile_queues[profile_id].append(command)

                # Track pending command
                self.pending_commands[command_id] = command

                # Add to history
                if profile_id not in self.command_history:
                    self.command_history[profile_id] = deque(maxlen=100)
                self.command_history[profile_id].append(command)

                logger.info(f"Command sent to mobile: {command_type} (ID: {command_id})")

                return {
                    'success': True,
                    'command_id': command_id,
                    'status': 'queued',
                    'message': f"Command queued for mobile app"
                }

        except Exception as e:
            logger.error(f"Error sending command to mobile: {e}")
            return {'success': False, 'error': str(e)}

    def get_pending_commands_for_mobile(self, profile_id: int) -> List[Dict[str, Any]]:
        """
        Get pending commands for mobile app (polling endpoint)

        Args:
            profile_id: Profile ID

        Returns:
            List of pending commands
        """
        try:
            with self.lock:
                if profile_id not in self.desktop_to_mobile_queues:
                    return []

                queue = self.desktop_to_mobile_queues[profile_id]
                pending = []

                # Get all queued commands
                for command in queue:
                    if command['status'] == 'queued':
                        # Mark as delivered
                        command['status'] = 'delivered'
                        command['delivered_at'] = datetime.now().isoformat()
                        pending.append(command)

                return pending

        except Exception as e:
            logger.error(f"Error getting pending commands: {e}")
            return []

    def receive_command_response(self, command_id: str, response: Dict[str, Any]) -> bool:
        """
        Receive response from mobile app for a command

        Args:
            command_id: Command ID
            response: Response data from mobile

        Returns:
            Success status
        """
        try:
            with self.lock:
                if command_id not in self.pending_commands:
                    logger.warning(f"Response for unknown command: {command_id}")
                    return False

                # Update command status
                command = self.pending_commands[command_id]
                command['status'] = response.get('status', 'completed')
                command['response'] = response
                command['completed_at'] = datetime.now().isoformat()

                # Store response
                self.command_responses[command_id] = response

                logger.info(f"Command response received: {command_id} - {response.get('status')}")

                return True

        except Exception as e:
            logger.error(f"Error receiving command response: {e}")
            return False

    # ==================== MOBILE → DESKTOP ====================

    def send_request_to_desktop(self, profile_id: int, request_type: str,
                                parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send request from mobile app to desktop

        Args:
            profile_id: Profile ID
            request_type: Request type (generate_pdf, export_data, etc.)
            parameters: Request parameters

        Returns:
            Request info with request_id
        """
        try:
            with self.lock:
                # Generate request ID
                request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

                # Create request object
                request = {
                    'request_id': request_id,
                    'profile_id': profile_id,
                    'request_type': request_type,
                    'parameters': parameters or {},
                    'status': 'received',
                    'created_at': datetime.now().isoformat(),
                    'direction': 'mobile_to_desktop'
                }

                # Initialize queue if needed
                if profile_id not in self.mobile_to_desktop_queues:
                    self.mobile_to_desktop_queues[profile_id] = deque(maxlen=50)

                # Add to queue
                self.mobile_to_desktop_queues[profile_id].append(request)

                logger.info(f"Request received from mobile: {request_type} (ID: {request_id})")

                return {
                    'success': True,
                    'request_id': request_id,
                    'status': 'received',
                    'message': 'Request received by desktop'
                }

        except Exception as e:
            logger.error(f"Error receiving request from mobile: {e}")
            return {'success': False, 'error': str(e)}

    def get_pending_requests_from_mobile(self, profile_id: int = None) -> List[Dict[str, Any]]:
        """
        Get pending requests from mobile app (for desktop to process)

        Args:
            profile_id: Profile ID (None = all profiles)

        Returns:
            List of pending requests
        """
        try:
            with self.lock:
                pending = []

                if profile_id:
                    # Get requests for specific profile
                    if profile_id in self.mobile_to_desktop_queues:
                        queue = self.mobile_to_desktop_queues[profile_id]
                        pending.extend([r for r in queue if r['status'] == 'received'])
                else:
                    # Get all pending requests
                    for queue in self.mobile_to_desktop_queues.values():
                        pending.extend([r for r in queue if r['status'] == 'received'])

                return pending

        except Exception as e:
            logger.error(f"Error getting pending requests: {e}")
            return []

    def mark_request_processing(self, request_id: str) -> bool:
        """
        Mark request as being processed

        Args:
            request_id: Request ID

        Returns:
            Success status
        """
        try:
            with self.lock:
                # Find request in queues
                for queue in self.mobile_to_desktop_queues.values():
                    for request in queue:
                        if request['request_id'] == request_id:
                            request['status'] = 'processing'
                            request['processing_started_at'] = datetime.now().isoformat()
                            return True

                return False

        except Exception as e:
            logger.error(f"Error marking request processing: {e}")
            return False

    def complete_request(self, request_id: str, result: Dict[str, Any]) -> bool:
        """
        Mark request as completed with result

        Args:
            request_id: Request ID
            result: Result data

        Returns:
            Success status
        """
        try:
            with self.lock:
                # Find request in queues
                for queue in self.mobile_to_desktop_queues.values():
                    for request in queue:
                        if request['request_id'] == request_id:
                            request['status'] = 'completed'
                            request['result'] = result
                            request['completed_at'] = datetime.now().isoformat()
                            logger.info(f"Request completed: {request_id}")
                            return True

                return False

        except Exception as e:
            logger.error(f"Error completing request: {e}")
            return False

    # ==================== STATUS & MONITORING ====================

    def get_command_status(self, command_id: str) -> Dict[str, Any]:
        """
        Get status of a command

        Args:
            command_id: Command ID

        Returns:
            Command status
        """
        try:
            with self.lock:
                if command_id in self.pending_commands:
                    command = self.pending_commands[command_id]
                    return {
                        'command_id': command_id,
                        'status': command['status'],
                        'command_type': command['command_type'],
                        'created_at': command['created_at'],
                        'response': self.command_responses.get(command_id)
                    }

                return {'status': 'not_found', 'error': 'Command not found'}

        except Exception as e:
            logger.error(f"Error getting command status: {e}")
            return {'status': 'error', 'error': str(e)}

    def get_communication_stats(self, profile_id: int = None) -> Dict[str, Any]:
        """
        Get communication statistics

        Args:
            profile_id: Profile ID (None = all profiles)

        Returns:
            Statistics dictionary
        """
        try:
            with self.lock:
                stats = {
                    'desktop_to_mobile': {
                        'queued': 0,
                        'delivered': 0,
                        'completed': 0,
                        'failed': 0
                    },
                    'mobile_to_desktop': {
                        'received': 0,
                        'processing': 0,
                        'completed': 0,
                        'failed': 0
                    }
                }

                # Count desktop → mobile
                queues_to_check = [self.desktop_to_mobile_queues.get(profile_id)] if profile_id else self.desktop_to_mobile_queues.values()

                for queue in queues_to_check:
                    if queue:
                        for cmd in queue:
                            status = cmd['status']
                            if status in stats['desktop_to_mobile']:
                                stats['desktop_to_mobile'][status] += 1

                # Count mobile → desktop
                queues_to_check = [self.mobile_to_desktop_queues.get(profile_id)] if profile_id else self.mobile_to_desktop_queues.values()

                for queue in queues_to_check:
                    if queue:
                        for req in queue:
                            status = req['status']
                            if status in stats['mobile_to_desktop']:
                                stats['mobile_to_desktop'][status] += 1

                return stats

        except Exception as e:
            logger.error(f"Error getting communication stats: {e}")
            return {}

    def get_command_history(self, profile_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get command history for profile

        Args:
            profile_id: Profile ID
            limit: Maximum commands to return

        Returns:
            List of commands
        """
        try:
            with self.lock:
                if profile_id not in self.command_history:
                    return []

                history = list(self.command_history[profile_id])
                history.reverse()  # Most recent first

                return history[:limit]

        except Exception as e:
            logger.error(f"Error getting command history: {e}")
            return []

    # ==================== PREDEFINED COMMANDS ====================

    def request_diagnostic_scan(self, profile_id: int) -> Dict[str, Any]:
        """Request mobile app to perform diagnostic scan"""
        return self.send_command_to_mobile(
            profile_id,
            'diagnostic_scan',
            parameters={'scan_type': 'full'},
            priority='high'
        )

    def request_clear_codes(self, profile_id: int, code_ids: List[str] = None) -> Dict[str, Any]:
        """Request mobile app to clear fault codes"""
        return self.send_command_to_mobile(
            profile_id,
            'clear_codes',
            parameters={'code_ids': code_ids or []},
            priority='high'
        )

    def request_status_update(self, profile_id: int) -> Dict[str, Any]:
        """Request mobile app to send status update"""
        return self.send_command_to_mobile(
            profile_id,
            'status_update',
            parameters={},
            priority='normal'
        )

    def send_notification_to_mobile(self, profile_id: int, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Send push notification to mobile app"""
        return self.send_command_to_mobile(
            profile_id,
            'push_notification',
            parameters={'notification': notification},
            priority='urgent'
        )

    def update_mobile_settings(self, profile_id: int, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update settings on mobile app"""
        return self.send_command_to_mobile(
            profile_id,
            'update_settings',
            parameters={'settings': settings},
            priority='low'
        )

    # ==================== CLEANUP ====================

    def _cleanup_loop(self):
        """Background cleanup of expired commands"""
        while True:
            try:
                time.sleep(300)  # Every 5 minutes
                self._cleanup_expired_commands()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(60)

    def _cleanup_expired_commands(self):
        """Remove expired commands from tracking"""
        try:
            with self.lock:
                now = datetime.now()
                expired = []

                # Find expired commands
                for command_id, command in self.pending_commands.items():
                    expires_at = datetime.fromisoformat(command['expires_at'])

                    if now > expires_at and command['status'] not in ['completed', 'failed']:
                        command['status'] = 'expired'
                        expired.append(command_id)

                # Clean up
                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired commands")

        except Exception as e:
            logger.error(f"Error cleaning up commands: {e}")

    def clear_completed_commands(self, profile_id: int = None, older_than_hours: int = 24):
        """
        Clear completed commands older than specified hours

        Args:
            profile_id: Profile ID (None = all)
            older_than_hours: Age threshold in hours
        """
        try:
            with self.lock:
                cutoff = datetime.now() - timedelta(hours=older_than_hours)
                removed = 0

                # Clean desktop → mobile queues
                queues = [self.desktop_to_mobile_queues.get(profile_id)] if profile_id else self.desktop_to_mobile_queues.values()

                for queue in queues:
                    if queue:
                        to_remove = []
                        for cmd in queue:
                            if cmd['status'] in ['completed', 'failed', 'expired']:
                                completed_at = datetime.fromisoformat(cmd.get('completed_at', cmd['created_at']))
                                if completed_at < cutoff:
                                    to_remove.append(cmd)

                        for cmd in to_remove:
                            queue.remove(cmd)
                            removed += 1

                # Clean mobile → desktop queues
                queues = [self.mobile_to_desktop_queues.get(profile_id)] if profile_id else self.mobile_to_desktop_queues.values()

                for queue in queues:
                    if queue:
                        to_remove = []
                        for req in queue:
                            if req['status'] in ['completed', 'failed']:
                                completed_at = datetime.fromisoformat(req.get('completed_at', req['created_at']))
                                if completed_at < cutoff:
                                    to_remove.append(req)

                        for req in to_remove:
                            queue.remove(req)
                            removed += 1

                if removed > 0:
                    logger.info(f"Cleared {removed} old commands/requests")

        except Exception as e:
            logger.error(f"Error clearing completed commands: {e}")
