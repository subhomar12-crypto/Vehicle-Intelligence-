"""
Background task functions for ARQ worker.

All task functions accept ctx as first argument (ARQ context)
and should return a result dict with at least {"success": bool}.
"""

from .email_tasks import (
    send_email,
    send_verification_email,
    send_password_reset_email,
    send_bulk_emails,
)

from .fcm_tasks import (
    send_push_notification,
    send_bulk_push,
    send_guardian_alert,
    update_fcm_token,
)

from .pdf_tasks import (
    generate_vehicle_report,
    generate_fleet_report,
    cleanup_old_reports,
)

from .backup_tasks import (
    backup_database,
    restore_database,
    cleanup_old_backups,
    verify_backup,
)

from .cleanup_tasks import (
    gdpr_cleanup,
    cleanup_old_vehicle_data,
    cleanup_expired_codes,
    cleanup_idempotency_cache,
    cleanup_failed_operations,
    cleanup_orphaned_files,
    generate_retention_report,
)

__all__ = [
    # Email tasks
    "send_email",
    "send_verification_email",
    "send_password_reset_email",
    "send_bulk_emails",
    
    # FCM tasks
    "send_push_notification",
    "send_bulk_push",
    "send_guardian_alert",
    "update_fcm_token",
    
    # PDF tasks
    "generate_vehicle_report",
    "generate_fleet_report",
    "cleanup_old_reports",
    
    # Backup tasks
    "backup_database",
    "restore_database",
    "cleanup_old_backups",
    "verify_backup",
    
    # Cleanup tasks
    "gdpr_cleanup",
    "cleanup_old_vehicle_data",
    "cleanup_expired_codes",
    "cleanup_idempotency_cache",
    "cleanup_failed_operations",
    "cleanup_orphaned_files",
    "generate_retention_report",
]
