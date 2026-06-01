# Predict OBD - Operational Runbooks

## Production Operations Manual
Version 1.0 | Last Updated: 2024-12-24

---

## Table of Contents
1. [Backup and Restore Procedures](#1-backup-and-restore-procedures)
2. [Subscription Failure Handling](#2-subscription-failure-handling)
3. [Customer Deletion Procedures](#3-customer-deletion-procedures)
4. [Monitoring and Alerting](#4-monitoring-and-alerting)
5. [Emergency Procedures](#5-emergency-procedures)

---

## 1. Backup and Restore Procedures

### 1.1 Backup Strategy Overview

| Backup Type | Frequency | Retention | Contents |
|------------|-----------|-----------|----------|
| Daily | 02:00 AM | 7 days | Critical data only |
| Weekly | Sunday 02:00 AM | 4 weeks | Critical + reports + predictions |
| Monthly | 1st of month | 12 months | Full system backup |

### 1.2 Manual Backup Procedure

```python
from enterprise_backup import get_backup_manager

# Create immediate backup
manager = get_backup_manager()
success, message, metadata = manager.create_backup(
    backup_type="daily",  # or "weekly", "monthly"
    description="Pre-maintenance backup",
    verify=True
)

print(f"Backup: {message}")
print(f"Verified: {metadata.verified}")
```

**Command Line:**
```bash
python -c "from enterprise_backup import create_backup; print(create_backup('daily'))"
```

### 1.3 Restore Procedure

#### Step 1: Identify Backup to Restore
```python
from enterprise_backup import get_backup_manager

manager = get_backup_manager()
backups = manager.list_backups()

for b in backups[:5]:
    print(f"{b['backup_id']}: {b['created_at']} - {b['status']}")
```

#### Step 2: Verify Backup Integrity (Mandatory)
```python
success, report = manager.verify_restore_integrity(backup_id)

if not success:
    print("ABORT: Backup verification failed")
    print(report)
else:
    print("Backup verification passed - safe to restore")
```

#### Step 3: Perform Restore
```python
# CRITICAL: Stop all services before restore
# python -c "import server_module; server_module.stop()"

success, message = manager.restore_backup(
    backup_id="daily_20241224_020000",
    restore_path=None,  # None = original location
    verify_first=True
)

print(message)

# Restart services after restore
# python -c "import server_module; server_module.start()"
```

### 1.4 Restore Verification Checklist

After every restore, verify:

- [ ] API keys file exists and is valid JSON
- [ ] Customer subscription files are accessible
- [ ] Database connections work
- [ ] API endpoints respond correctly
- [ ] Audit logs are intact
- [ ] AI model registry is valid

**Verification Script:**
```python
from system_integrity import SystemIntegrityChecker
checker = SystemIntegrityChecker()
report = checker.run_all_checks()
print(report)
```

---

## 2. Subscription Failure Handling

### 2.1 Payment Failure Response

When a payment fails, the system automatically:
1. Logs the failure in subscription audit log
2. Sets subscription status to `expired`
3. Sets payment_status to `failed`
4. Blocks access to protected endpoints

**Operator Actions Required:**

#### Step 1: Identify Affected Customer
```python
from subscription_manager import get_subscription_manager

manager = get_subscription_manager()
sub = manager.load_subscription("customer_123")

print(f"Status: {sub.status}")
print(f"Payment: {sub.payment_status}")
print(f"Expired: {sub.end_date}")
```

#### Step 2: Contact Customer
- Email customer about payment failure
- Provide payment update link
- Document communication in audit log

#### Step 3: Manual Renewal (After Payment Received)
```python
success, message = manager.renew_subscription(
    customer_id="customer_123",
    payment_succeeded=True,
    payment_details={
        "method": "manual_bank_transfer",
        "confirmation": "CONF123456",
        "received_by": "operator_name"
    },
    renewed_by="operator_name"
)

print(message)
```

### 2.2 Grace Period Handling

Default grace period: **0 days** (immediate expiration)

To implement a grace period:
```python
# In subscription_manager.py, modify renewal logic to check:
# if (now - end_date).days <= GRACE_PERIOD_DAYS:
#     continue_service = True
```

### 2.3 Subscription Recovery Script

For bulk recovery after payment system outage:
```python
from pathlib import Path
from subscription_manager import get_subscription_manager
from config import get_config

def recover_subscriptions(customer_ids: list, days_to_add: int, reason: str):
    """Recover multiple subscriptions after outage."""
    manager = get_subscription_manager()

    for customer_id in customer_ids:
        success, msg = manager.renew_subscription(
            customer_id=customer_id,
            payment_succeeded=True,
            payment_details={
                "recovery_reason": reason,
                "days_added": days_to_add
            },
            renewed_by="system_recovery"
        )
        print(f"{customer_id}: {msg}")
```

---

## 3. Customer Deletion Procedures

### 3.1 Soft Delete (Default - GDPR Compliant)

Soft delete preserves data for 30 days before permanent removal.

```python
from customer_isolation import get_isolation_enforcer

enforcer = get_isolation_enforcer()
success, message = enforcer.delete_customer_data(
    customer_id="customer_123",
    soft_delete=True,  # 30-day recovery period
    deleted_by="operator_name"
)

print(message)
```

**What Happens:**
1. Customer directory renamed to `customer_123_deleted_TIMESTAMP`
2. Reports directory renamed similarly
3. Audit log entry created
4. Data preserved for 30-day recovery window

### 3.2 Customer Recovery (Within 30 Days)

```python
from directory_manager import DirectoryManager
from config import get_config

config = get_config()
manager = DirectoryManager()

# Find deleted customer directory
deleted_dirs = list(config.CUSTOMERS_DIR.glob("customer_123_deleted_*"))

if deleted_dirs:
    deleted_dir = deleted_dirs[0]
    original_name = "customer_123"

    # Restore customer
    import shutil
    shutil.move(str(deleted_dir), str(config.CUSTOMERS_DIR / original_name))

    print(f"Customer {original_name} recovered")
```

### 3.3 Permanent Delete (Hard Delete)

**WARNING:** This action is irreversible.

```python
success, message = enforcer.delete_customer_data(
    customer_id="customer_123",
    soft_delete=False,  # PERMANENT - NO RECOVERY
    deleted_by="operator_name"
)
```

**Pre-Deletion Checklist:**
- [ ] Confirm customer identity
- [ ] Verify GDPR deletion request documentation
- [ ] Export customer data if required by retention policy
- [ ] Get supervisor approval
- [ ] Create backup before deletion

### 3.4 Deletion with Active Subscription

If customer has active subscription:

```python
from subscription_manager import get_subscription_manager

# Step 1: Cancel subscription first
sub_manager = get_subscription_manager()
sub_manager.cancel_subscription(
    customer_id="customer_123",
    reason="customer_deletion_request",
    cancelled_by="operator"
)

# Step 2: Revoke all API keys
from api_key_manager import revoke_all_customer_keys
revoke_all_customer_keys("customer_123")

# Step 3: Delete customer data
enforcer.delete_customer_data("customer_123", soft_delete=True)
```

### 3.5 Cleanup of Soft-Deleted Customers

Run monthly to permanently delete customers past 30-day recovery:

```python
from datetime import datetime, timedelta
from config import get_config
import shutil
import re

config = get_config()
cutoff = datetime.now() - timedelta(days=30)

for dir in config.CUSTOMERS_DIR.iterdir():
    if "_deleted_" in dir.name:
        # Extract timestamp from name: customer_id_deleted_YYYYMMDDTHHMMSS
        match = re.search(r'_deleted_(\d{8}T\d{6})', dir.name)
        if match:
            timestamp = datetime.strptime(match.group(1), '%Y%m%dT%H%M%S')
            if timestamp < cutoff:
                shutil.rmtree(dir)
                print(f"Permanently deleted: {dir.name}")
```

---

## 4. Monitoring and Alerting

### 4.1 Critical Alerts (Immediate Response Required)

| Alert | Trigger | Response Time |
|-------|---------|---------------|
| Audit Log Integrity Failure | Checksum mismatch | 15 minutes |
| Subscription Enforcement Bypass | Access without valid subscription | 5 minutes |
| API Key Leak Detected | Key found in unauthorized location | Immediate |
| Backup Failure | 2 consecutive failed backups | 1 hour |
| Database Corruption | Integrity check failure | 30 minutes |

### 4.2 Setting Up Monitoring

```python
from monitoring_alerts import get_alert_manager

alerts = get_alert_manager()

# Configure alert handlers
alerts.add_email_handler("ops@company.com")
alerts.add_webhook_handler("https://slack.webhook.url")

# Start monitoring
alerts.start()
```

### 4.3 Manual Health Check

```python
from system_integrity import SystemIntegrityChecker

checker = SystemIntegrityChecker()
report = checker.run_all_checks()

print("=== System Health Report ===")
print(f"Overall Status: {'HEALTHY' if report['healthy'] else 'UNHEALTHY'}")

for check_name, result in report['checks'].items():
    status = "OK" if result['passed'] else "FAILED"
    print(f"  {check_name}: {status}")
    if not result['passed']:
        print(f"    Error: {result['error']}")
```

### 4.4 Audit Log Integrity Monitoring

```python
from audit_logger import verify_all_logs

results = verify_all_logs()

if not results['verified']:
    print("CRITICAL: Audit log tampering detected!")
    print(f"Tampered files: {results['tampered_files']}")
    # Trigger immediate alert
```

---

## 5. Emergency Procedures

### 5.1 Service Outage Response

1. **Identify scope of outage**
   ```python
   from system_integrity import SystemIntegrityChecker
   checker = SystemIntegrityChecker()
   checker.run_all_checks()
   ```

2. **Check service status**
   ```bash
   netstat -an | findstr 8000
   netstat -an | findstr 8001
   ```

3. **Review recent logs**
   ```python
   from pathlib import Path
   logs = sorted(Path("PredictData/logs/error").glob("*.log"))[-1]
   print(logs.read_text()[-5000:])
   ```

4. **Restart services**
   ```bash
   python server_module.py restart
   ```

### 5.2 Data Breach Response

1. **Immediate Actions (First 15 minutes):**
   - Revoke all active API keys
   - Disable external access
   - Document timeline

   ```python
   # Emergency key revocation
   from config import get_config
   import json

   config = get_config()

   # Backup current keys
   import shutil
   shutil.copy(config.API_KEYS_FILE, config.API_KEYS_FILE.with_suffix('.backup'))

   # Clear all keys
   with open(config.API_KEYS_FILE, 'w') as f:
       json.dump({}, f)

   print("All API keys revoked")
   ```

2. **Investigation (First hour):**
   - Export audit logs
   - Identify affected data
   - Determine breach vector

3. **Remediation:**
   - Rotate all secrets
   - Notify affected customers
   - Document incident

### 5.3 Ransomware/Corruption Recovery

1. **STOP all services immediately**
2. **Isolate affected systems**
3. **Identify last known good backup**
   ```python
   from enterprise_backup import get_backup_manager
   manager = get_backup_manager()

   # Find verified backups
   for b in manager.list_backups():
       if b['verified']:
           print(f"Verified backup: {b['backup_id']} - {b['created_at']}")
   ```

4. **Verify backup before restore**
5. **Perform restore to clean system**
6. **Verify integrity after restore**

### 5.4 Contact Information

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-Call Engineer | [Configure] | Immediate |
| System Administrator | [Configure] | 15 minutes |
| Security Officer | [Configure] | For breaches |
| Management | [Configure] | Major incidents |

---

## Appendix A: Quick Reference Commands

### Backup
```bash
# Create backup
python -c "from enterprise_backup import create_backup; print(create_backup())"

# List backups
python -c "from enterprise_backup import get_backup_manager; print(get_backup_manager().list_backups())"
```

### Subscription
```bash
# Check subscription
python -c "from subscription_manager import get_subscription_manager; m=get_subscription_manager(); print(m.get_subscription_info('CUSTOMER_ID'))"

# Expire subscription
python -c "from subscription_manager import get_subscription_manager; m=get_subscription_manager(); print(m.expire_subscription('CUSTOMER_ID', 'manual'))"
```

### Integrity
```bash
# Run integrity check
python -c "from system_integrity import SystemIntegrityChecker; c=SystemIntegrityChecker(); print(c.run_all_checks())"

# Verify audit logs
python -c "from audit_logger import verify_all_logs; print(verify_all_logs())"
```

---

*End of Operational Runbooks*
