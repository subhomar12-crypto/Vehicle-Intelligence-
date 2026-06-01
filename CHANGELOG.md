# Changelog

All notable changes to PREDICT will be documented in this file.

## Version 5.0.0 (2026-01-10)

### Phase 4: Analytics & Reports Enhancement
- Added real-time interactive charts using pyqtgraph
- Implemented 6 chart types: Fuel Efficiency, Maintenance Costs, DTC Categories, Driving Score, Temperature History, RPM Histogram
- Enhanced dashboard with live data widgets
- Implemented global search functionality
- Added CSV export for all charts

### Phase 5: Settings & Configuration Completion
- Added comprehensive settings tab with General, OBD, Notifications, and AI sections
- Implemented settings save/load for all categories
- Added theme switching (Dark/Light)
- Added notification preferences (In-App, Email, SMS, Push)
- Added Help/About tab with documentation, changelog, and system information

## Version 4.0.0 (2026-01-05)

### Phase 3: Dashboard Integration & Multi-Vehicle Support
- Added vehicle switcher in main window
- Implemented multi-vehicle profile management
- Added sync status indicator
- Integrated voice command system
- Added remote command controls

### Phase 2: New Dashboard Tabs
- Created Fuel Tracking tab with MPG tracking
- Created Driving Score tab with behavior analysis
- Created Geofencing tab with zone management
- Created ESP32 Sensors tab with live readings
- Created Maintenance Reminders tab
- Created Recall Alerts tab with NHTSA integration

## Version 3.0.0 (2025-12-20)

### Phase 1: Core Infrastructure & Backend Wiring
- Wired push notification manager with Firebase/OneSignal
- Wired SMS notification manager with Twilio
- Connected maintenance history API to database
- Implemented real OBD DTC retrieval
- Connected DTC learning to alert system

## Version 2.0.0 (2025-12-10)

### Major Updates
- AI-powered predictions with LSTM models
- Real-time OBD-II data streaming
- PDF report generation
- Cloud synchronization
- Multi-language support

## Version 1.0.0 (2025-11-15)

### Initial Release
- Basic OBD-II connection
- Live data display
- DTC code reading
- Simple dashboard
