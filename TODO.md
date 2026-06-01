# PREDICT Ecosystem - TODO List

## Priority: HIGH - Desktop UI/UX Gaps

These backend features exist but have NO user interface:

### Missing UI Components

| Feature | Backend File | Effort | Priority |
|---------|--------------|--------|----------|
| Geofencing Alerts | `geofencing_alerts.py` | 2-3 days | Medium |
| Fuel Tracking Tab | `fuel_tracking.py` | 2-3 days | High |
| Trip Analytics Tab | `trip_analytics.py` | 2-3 days | High |
| Driving Score Display | `driving_score.py` | 1-2 days | Medium |
| Custom Alerts Config | `custom_alerts.py` | 2-3 days | High |
| Multi-Vehicle Comparison | `multi_vehicle_comparison.py` | 2-3 days | Medium |
| Maintenance Reminders Config | `maintenance_reminders.py` | 1-2 days | High |
| Historical Data Management | `historical_data_manager.py` | 1-2 days | Low |

### Notifications Tab Issues

- [ ] Replace mock data with real alerts from `alert_notifications.py`
- [ ] Implement actual filtering logic (currently non-functional)
- [ ] Connect date range filtering
- [ ] Test email sending with real Gmail App Password

### Email Configuration Required

1. Enable 2FA on Google Account
2. Generate App Password at myaccount.google.com/apppasswords
3. Configure in Desktop: Notifications → Preferences → Email Settings

---

## Priority: MEDIUM - Enhancements

### PredictOBD (Android)
- [ ] Add first-launch legal acceptance check in MainActivity
- [ ] Onboarding flow for new users
- [ ] Skeleton loaders instead of spinners

### Predict Guardian (Android)
- [ ] Add first-launch legal acceptance check
- [ ] Onboarding flow explaining guardian features
- [ ] Home screen widget for quick vehicle status

### Predict Desktop (Windows)
- [ ] Welcome wizard for new users
- [ ] Keyboard shortcuts
- [ ] High DPI support for 4K monitors

---

## Priority: LOW - Future Features

- [ ] iOS version of PredictOBD
- [ ] iOS version of Predict Guardian
- [ ] WearOS companion app
- [ ] macOS version of Predict Desktop
- [ ] Linux version of Predict Desktop

---

## Completed

- [x] Legal documents (Terms, Privacy, Data Collection)
- [x] Investor document
- [x] Legal screens in PredictOBD
- [x] Legal screens in Predict Guardian
- [x] Legal API endpoints in server
- [x] API endpoint fixes (profileId vs apiKey)
- [x] Guardian API endpoints (20+)
- [x] Scheduled predictions system
- [x] Component prediction models

---

*Last Updated: January 2026*
