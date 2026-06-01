# PREDICT Ecosystem - Implementation TODO List

## Document Purpose
This document provides detailed implementation tasks for all 3 PREDICT programs. Each task includes:
- Specific files to modify
- Implementation details
- Dependencies
- Testing requirements

---

# PROGRAM 1: PREDICT DESKTOP (C:\D Drive\Predict)

## PHASE 1: Core Backend Verification (Week 1-2)

### 1.1 LLM Data Edit Functionality
**Files:** `llm_assistant.py`, `llm_api_server.py`, `unified_ai_module.py`

**Task:** Verify and document the special prompts that allow LLM to edit AI module data for failed predictions.

**Implementation:**
```python
# Expected prompt format (verify in llm_assistant.py):
# "ADMIN_EDIT: Correction for prediction [prediction_id]
#  Actual outcome: [component] failed on [date]
#  Original prediction: [predicted_date]
#  Adjust model parameters for [vehicle_type]"

# The LLM should:
# 1. Parse the correction data
# 2. Update the training dataset
# 3. Trigger incremental model retraining
# 4. Log the correction for audit

# Check for existing implementation in:
# - ai_auto_retraining.py
# - enhanced_ai_learning.py
# - feedback_collector.py
```

**Testing:**
- [ ] Send test correction prompt
- [ ] Verify training data updated
- [ ] Confirm model retrained
- [ ] Check audit log entry

### 1.2 UI-Backend Connection Audit
**Files:** `main_pyside.py`, all `*_tab.py` files

**Task:** Audit all 18 tabs and verify backend connections are working.

**Checklist:**
```
Tab                     | Backend Module          | Status
------------------------|------------------------|--------
Connection Tab          | obd_connection_manager | [ ]
Live Data Tab           | server_module          | [ ]
DTC Tab                 | dtc_module             | [ ]
Data Management Tab     | data_management        | [ ]
Reports Tab             | pdf_exporter           | [ ]
Service History Tab     | service_history        | [ ]
Devices Tab             | device management      | [ ]
AI Training Tab         | ai_auto_retraining     | [ ]
Advanced Features Tab   | various                | [ ]
Chat Tab                | llm_assistant          | [ ]
Notifications Tab       | alert_notifications    | [ ]
PID Learning Tab        | pid_learning           | [ ]
Settings Tab            | config                 | [ ]
Subscription Tab        | subscription_manager   | [ ]
User Management Tab     | user_management        | [ ]
Server Tab              | server_module          | [ ]
Cloud Sync Tab          | cloud_sync             | [ ]
Customer Management Tab | customer_management    | [ ]
```

### 1.3 Automated Prediction Pipeline
**Files:** `predictive_failure_engine.py`, `enhanced_prediction_engine.py`, `lstm_predictor.py`

**Task:** Create scheduled prediction runner that processes all vehicles daily.

**Implementation:**
```python
# New file: scheduled_predictions.py

import schedule
import time
from vehicle_module import get_all_active_vehicles
from predictive_failure_engine import PredictiveFailureEngine
from lstm_predictor import LSTMPredictor
from database import save_prediction, get_latest_telemetry

def run_daily_predictions():
    """Run predictions for all active vehicles."""
    vehicles = get_all_active_vehicles()
    engine = PredictiveFailureEngine()
    lstm = LSTMPredictor()

    for vehicle in vehicles:
        try:
            # Get latest 60 days of telemetry
            telemetry = get_latest_telemetry(vehicle.id, days=60)

            if len(telemetry) < 7:
                continue  # Need minimum 7 days data

            # Run ensemble prediction
            prediction = engine.predict(telemetry)

            # Run LSTM prediction if enough data
            if len(telemetry) >= 30:
                lstm_pred = lstm.predict(telemetry)
                prediction = merge_predictions(prediction, lstm_pred)

            # Save to database
            save_prediction(
                vehicle_id=vehicle.id,
                prediction=prediction,
                confidence=prediction.confidence,
                generated_at=datetime.now()
            )

            # Check for critical alerts
            if prediction.requires_immediate_attention():
                send_alert(vehicle, prediction)

        except Exception as e:
            logger.error(f"Prediction failed for {vehicle.id}: {e}")

# Schedule daily at 2 AM
schedule.every().day.at("02:00").do(run_daily_predictions)
```

---

## PHASE 2: Prediction Engine Enhancement (Week 2-4)

### 2.1 Brake Wear Prediction Algorithm
**Files:** `predictive_failure_engine.py`, `unified_ai_module.py`

**Task:** Implement comprehensive brake wear prediction using temperature and driving patterns.

**Implementation:**
```python
# Add to predictive_failure_engine.py

class BrakePredictionModel:
    """Predicts brake pad/rotor wear based on sensor data and driving patterns."""

    # OEM average specifications (configurable per vehicle)
    DEFAULT_BRAKE_LIFE_KM = 50000  # Average brake pad life
    MAX_SAFE_BRAKE_TEMP = 300  # Celsius
    CRITICAL_TEMP_THRESHOLD = 400  # Fade temperature

    def __init__(self, vehicle_spec: dict = None):
        self.brake_life_km = vehicle_spec.get('brake_life_km', self.DEFAULT_BRAKE_LIFE_KM) if vehicle_spec else self.DEFAULT_BRAKE_LIFE_KM

    def calculate_wear(self, telemetry_data: list) -> dict:
        """
        Calculate brake wear and predict remaining life.

        Args:
            telemetry_data: List of readings with:
                - brake_temp_front (float): Front brake temperature in Celsius
                - brake_temp_rear (float): Rear brake temperature in Celsius
                - deceleration (float): Deceleration rate in m/s²
                - speed (float): Vehicle speed in km/h
                - mileage_km (float): Current odometer reading
                - last_brake_service_km (float): Mileage at last brake service

        Returns:
            dict with:
                - remaining_life_percent (float): 0-100
                - predicted_failure_date (date): Estimated failure date
                - failure_window_days (tuple): (min_days, max_days)
                - confidence (float): 0-1 confidence score
                - severity (str): 'normal', 'warning', 'critical'
                - recommendation (str): Action recommendation
        """
        if not telemetry_data:
            return None

        # Extract metrics
        temps = [r.get('brake_temp_front', 0) for r in telemetry_data]
        decels = [r.get('deceleration', 0) for r in telemetry_data]
        current_km = telemetry_data[-1].get('mileage_km', 0)
        last_service_km = telemetry_data[0].get('last_brake_service_km', 0)

        # Calculate wear factors
        km_since_service = current_km - last_service_km

        # 1. Distance-based wear (base factor)
        distance_wear = km_since_service / self.brake_life_km

        # 2. Temperature stress factor (high temps = faster wear)
        avg_temp = sum(temps) / len(temps) if temps else 0
        max_temp = max(temps) if temps else 0
        high_temp_ratio = sum(1 for t in temps if t > 200) / len(temps) if temps else 0
        temp_stress = (avg_temp / self.MAX_SAFE_BRAKE_TEMP) * (1 + high_temp_ratio)

        # 3. Driving intensity (harsh braking = faster wear)
        harsh_brakes = sum(1 for d in decels if d > 4.0)  # > 4 m/s² is harsh
        total_brakes = sum(1 for d in decels if d > 0.5)
        harsh_ratio = harsh_brakes / total_brakes if total_brakes > 0 else 0
        intensity_factor = 1 + (harsh_ratio * 0.5)  # Up to 50% faster wear

        # 4. Combined wear calculation
        total_wear = distance_wear * temp_stress * intensity_factor
        remaining_life = max(0, 1 - total_wear)

        # 5. Predict remaining distance and time
        if km_since_service > 0:
            avg_daily_km = km_since_service / len(set(r.get('date') for r in telemetry_data))
            remaining_km = remaining_life * self.brake_life_km
            remaining_days = remaining_km / avg_daily_km if avg_daily_km > 0 else 365
        else:
            remaining_days = 365  # Default to 1 year if no data

        # 6. Determine severity and recommendation
        if remaining_life < 0.1:
            severity = 'critical'
            recommendation = 'IMMEDIATE: Schedule brake service within 7 days'
            window = (0, 7)
        elif remaining_life < 0.25:
            severity = 'warning'
            recommendation = 'Schedule brake inspection within 30 days'
            window = (7, 30)
        elif remaining_life < 0.5:
            severity = 'attention'
            recommendation = 'Plan brake service in next 60 days'
            window = (30, 60)
        else:
            severity = 'normal'
            recommendation = 'Brakes in good condition'
            window = (60, 180)

        # 7. Confidence calculation
        data_quality = min(1.0, len(telemetry_data) / 30)  # Need 30 days for full confidence
        sensor_coverage = sum(1 for r in telemetry_data if r.get('brake_temp_front')) / len(telemetry_data)
        confidence = data_quality * sensor_coverage * 0.85  # Cap at 85%

        return {
            'component': 'brakes',
            'remaining_life_percent': remaining_life * 100,
            'predicted_failure_date': datetime.now() + timedelta(days=remaining_days),
            'failure_window_days': window,
            'confidence': confidence,
            'severity': severity,
            'recommendation': recommendation,
            'factors': {
                'distance_wear': distance_wear,
                'temp_stress': temp_stress,
                'intensity_factor': intensity_factor,
                'km_since_service': km_since_service
            }
        }
```

### 2.2 Battery Degradation Prediction
**Files:** `predictive_failure_engine.py`

**Implementation:**
```python
class BatteryPredictionModel:
    """Predicts battery health and failure based on voltage patterns and temperature."""

    NOMINAL_VOLTAGE = 12.6  # Fully charged 12V battery
    MIN_HEALTHY_VOLTAGE = 12.2  # Minimum healthy resting voltage
    CRANKING_VOLTAGE_HEALTHY = 10.5  # Healthy cranking voltage
    TYPICAL_BATTERY_LIFE_MONTHS = 48  # 4 years typical

    def calculate_health(self, telemetry_data: list, battery_age_months: int = None) -> dict:
        """
        Calculate battery health and predict failure.

        Args:
            telemetry_data: List of readings with:
                - battery_voltage (float): Current voltage
                - ambient_temp (float): Outside temperature
                - engine_running (bool): Is engine on
                - timestamp (datetime): Reading time
        """
        voltages = [r.get('battery_voltage', 12.0) for r in telemetry_data if r.get('battery_voltage')]
        temps = [r.get('ambient_temp', 20) for r in telemetry_data if r.get('ambient_temp')]

        if not voltages:
            return None

        # 1. Voltage health
        resting_voltages = [v for r, v in zip(telemetry_data, voltages)
                          if not r.get('engine_running', True)]
        avg_resting = sum(resting_voltages) / len(resting_voltages) if resting_voltages else self.NOMINAL_VOLTAGE
        voltage_health = min(1.0, (avg_resting - 11.5) / (self.NOMINAL_VOLTAGE - 11.5))

        # 2. Temperature stress (extreme temps degrade battery)
        extreme_hot = sum(1 for t in temps if t > 35) / len(temps) if temps else 0
        extreme_cold = sum(1 for t in temps if t < 0) / len(temps) if temps else 0
        temp_stress = 1 - (extreme_hot * 0.3 + extreme_cold * 0.2)

        # 3. Age factor
        if battery_age_months:
            age_factor = max(0, 1 - (battery_age_months / self.TYPICAL_BATTERY_LIFE_MONTHS))
        else:
            age_factor = 0.7  # Assume middle-aged if unknown

        # 4. Voltage stability (erratic = degraded)
        voltage_std = statistics.stdev(voltages) if len(voltages) > 1 else 0
        stability_factor = max(0, 1 - (voltage_std * 2))

        # 5. Combined health score
        health_score = (voltage_health * 0.4 + temp_stress * 0.1 +
                       age_factor * 0.3 + stability_factor * 0.2)

        # 6. Predict failure
        if health_score < 0.3:
            severity = 'critical'
            days_remaining = (0, 14)
            recommendation = 'CRITICAL: Battery replacement needed immediately'
        elif health_score < 0.5:
            severity = 'warning'
            days_remaining = (14, 45)
            recommendation = 'Schedule battery test and likely replacement within 2 weeks'
        elif health_score < 0.7:
            severity = 'attention'
            days_remaining = (45, 90)
            recommendation = 'Monitor battery health, consider testing'
        else:
            severity = 'normal'
            days_remaining = (90, 365)
            recommendation = 'Battery in good condition'

        # Cold start risk assessment
        cold_start_risk = 'low'
        if health_score < 0.6 and any(t < 5 for t in temps[-7:] if t):
            cold_start_risk = 'high'
        elif health_score < 0.7:
            cold_start_risk = 'moderate'

        return {
            'component': 'battery',
            'health_percent': health_score * 100,
            'failure_window_days': days_remaining,
            'cold_start_risk': cold_start_risk,
            'severity': severity,
            'recommendation': recommendation,
            'confidence': min(0.9, len(voltages) / 100),
            'metrics': {
                'avg_resting_voltage': avg_resting,
                'voltage_stability': stability_factor,
                'temp_stress_factor': temp_stress
            }
        }
```

### 2.3 Oil Change Prediction
**Files:** `predictive_failure_engine.py`

**Implementation:**
```python
class OilPredictionModel:
    """Predicts oil degradation and optimal change intervals."""

    # Default intervals by oil type
    OIL_INTERVALS = {
        'conventional': 5000,      # km
        'synthetic_blend': 8000,
        'full_synthetic': 12000,
        'high_mileage': 7000
    }

    def calculate_oil_life(self, telemetry_data: list,
                          oil_type: str = 'full_synthetic',
                          last_change_km: float = 0) -> dict:
        """
        Calculate remaining oil life based on conditions.

        Args:
            telemetry_data: List with oil_temp, rpm, speed, mileage_km
            oil_type: Type of oil used
            last_change_km: Mileage at last oil change
        """
        base_interval = self.OIL_INTERVALS.get(oil_type, 8000)

        current_km = telemetry_data[-1].get('mileage_km', 0)
        km_since_change = current_km - last_change_km

        # 1. Base distance factor
        distance_used = km_since_change / base_interval

        # 2. High temperature factor (degrades oil faster)
        oil_temps = [r.get('oil_temp', 90) for r in telemetry_data]
        avg_temp = sum(oil_temps) / len(oil_temps) if oil_temps else 90
        high_temp_time = sum(1 for t in oil_temps if t > 110) / len(oil_temps) if oil_temps else 0
        temp_factor = 1 + (high_temp_time * 0.5)  # Up to 50% faster degradation

        # 3. Driving style factor
        rpms = [r.get('rpm', 2000) for r in telemetry_data]
        avg_rpm = sum(rpms) / len(rpms) if rpms else 2000
        high_rpm_ratio = sum(1 for r in rpms if r > 4000) / len(rpms) if rpms else 0
        style_factor = 1 + (high_rpm_ratio * 0.3)

        # 4. Short trip penalty (oil doesn't reach optimal temp)
        speeds = [r.get('speed', 0) for r in telemetry_data]
        # Estimate trips by speed patterns (many 0s = many start/stops)
        zero_count = sum(1 for s in speeds if s == 0)
        short_trip_ratio = zero_count / len(speeds) if speeds else 0
        short_trip_factor = 1 + (short_trip_ratio * 0.2) if short_trip_ratio > 0.3 else 1

        # 5. Combined degradation
        effective_use = distance_used * temp_factor * style_factor * short_trip_factor
        remaining_life = max(0, 1 - effective_use)

        # 6. Calculate remaining km and days
        remaining_km = remaining_life * base_interval
        if km_since_change > 0:
            days_since_change = len(set(r.get('date') for r in telemetry_data))
            km_per_day = km_since_change / days_since_change if days_since_change > 0 else 30
            remaining_days = remaining_km / km_per_day if km_per_day > 0 else 180
        else:
            remaining_days = 180

        # 7. Severity and recommendation
        if remaining_life < 0.1:
            severity = 'critical'
            recommendation = 'Oil change overdue - schedule immediately'
        elif remaining_life < 0.25:
            severity = 'warning'
            recommendation = 'Oil change due soon - schedule within 1 week'
        elif remaining_life < 0.5:
            severity = 'attention'
            recommendation = f'Oil change in approximately {int(remaining_km)} km'
        else:
            severity = 'normal'
            recommendation = 'Oil in good condition'

        return {
            'component': 'oil',
            'remaining_life_percent': remaining_life * 100,
            'remaining_km': remaining_km,
            'remaining_days': remaining_days,
            'next_change_date': datetime.now() + timedelta(days=remaining_days),
            'severity': severity,
            'recommendation': recommendation,
            'confidence': 0.8,
            'factors': {
                'distance_factor': distance_used,
                'temp_factor': temp_factor,
                'style_factor': style_factor,
                'short_trip_factor': short_trip_factor
            }
        }
```

### 2.4 General Wear Components
**Files:** `predictive_failure_engine.py`

**Components to implement:**
```python
# Air Filter Prediction
# - Based on: km driven, dusty conditions (intake temp spikes), MAF readings
# - Typical life: 20,000-40,000 km

# Spark Plugs Prediction
# - Based on: km driven, misfires (via DTC), fuel trim readings
# - Typical life: 40,000-100,000 km (depends on type)

# Transmission Fluid
# - Based on: km driven, transmission temp, shift quality
# - Typical life: 60,000-100,000 km

# Coolant
# - Based on: km driven, coolant temp patterns, thermostat behavior
# - Typical life: 50,000-100,000 km or 2-5 years

# Timing Belt (if applicable)
# - Based on: km driven, engine hours, age
# - Typical life: 90,000-150,000 km

# Implementation pattern same as above - each with specific sensor inputs
```

---

## PHASE 3: Profile & API Key Management (Week 3-4)

### 3.1 Hierarchical Profile System
**Files:** `profile_manager.py`, `api_key_sync.py`, `customer_management_tab.py`

**Task:** Implement parent-child profile relationships with automatic API key generation.

**Database Schema Update:**
```sql
-- Add to vehicle_profiles.db

CREATE TABLE IF NOT EXISTS profile_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_profile_id TEXT NOT NULL,      -- Guardian/Fleet owner
    child_profile_id TEXT NOT NULL,       -- Driver/Vehicle
    relationship_type TEXT NOT NULL,      -- 'guardian', 'fleet_vehicle', 'self_guardian'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    permissions TEXT,                      -- JSON: what parent can access
    consent_given BOOLEAN DEFAULT FALSE,
    consent_date TIMESTAMP,
    FOREIGN KEY (parent_profile_id) REFERENCES profiles(profile_id),
    FOREIGN KEY (child_profile_id) REFERENCES profiles(profile_id)
);

CREATE TABLE IF NOT EXISTS api_key_tiers (
    tier_name TEXT PRIMARY KEY,
    auto_approve BOOLEAN DEFAULT FALSE,
    max_linked_profiles INTEGER DEFAULT 1,
    features TEXT,                         -- JSON array of features
    price_qar DECIMAL(10,2)
);

-- Tier configuration (Hybrid: Auto for Basic, Manual for Premium)
INSERT INTO api_key_tiers VALUES ('basic', TRUE, 3, '["view_data", "dtc_read"]', 0);
INSERT INTO api_key_tiers VALUES ('premium', FALSE, 10, '["view_data", "dtc_read", "predictions", "llm_chat"]', 99);
INSERT INTO api_key_tiers VALUES ('fleet', FALSE, 100, '["full_access"]', 499);
```

**Implementation:**
```python
# api_key_sync.py additions

class ProfileHierarchyManager:
    """Manages parent-child profile relationships and API key generation."""

    def create_guardian_profile(self, guardian_data: dict) -> dict:
        """
        Create a new Guardian/Fleet owner profile.

        Args:
            guardian_data: {
                'name': str,
                'email': str,
                'phone': str,
                'tier': 'basic' | 'premium' | 'fleet'
            }
        """
        # Check tier for auto-approval
        tier = guardian_data.get('tier', 'basic')
        auto_approve = self._check_auto_approve(tier)

        # Generate profile
        profile_id = str(uuid.uuid4())

        if auto_approve:
            # Auto-generate Guardian API key
            api_key = self._generate_api_key('GUARD', profile_id)
            status = 'active'
        else:
            api_key = None
            status = 'pending_approval'

        # Save to database
        self._save_profile(profile_id, guardian_data, api_key, status)

        # Notify admin if pending
        if not auto_approve:
            self._notify_admin_pending_approval(profile_id, guardian_data)

        return {
            'profile_id': profile_id,
            'api_key': api_key,
            'status': status,
            'tier': tier
        }

    def link_child_profile(self, parent_profile_id: str, child_data: dict) -> dict:
        """
        Create and link a child profile (driver/vehicle) to parent.

        Args:
            parent_profile_id: Guardian's profile ID
            child_data: {
                'name': str,
                'vehicle_info': dict,  # make, model, year, vin
                'driver_info': dict    # optional driver details
            }
        """
        # Verify parent exists and has capacity
        parent = self._get_profile(parent_profile_id)
        if not parent:
            raise ValueError("Parent profile not found")

        linked_count = self._get_linked_count(parent_profile_id)
        max_linked = self._get_tier_limit(parent['tier'])

        if linked_count >= max_linked:
            raise ValueError(f"Maximum linked profiles ({max_linked}) reached for this tier")

        # Create child profile
        child_profile_id = str(uuid.uuid4())
        child_api_key = self._generate_api_key('OBD', child_profile_id)

        # Create relationship
        relationship_id = self._create_relationship(
            parent_profile_id,
            child_profile_id,
            'guardian'
        )

        # Save child profile
        self._save_profile(child_profile_id, child_data, child_api_key, 'pending_consent')

        # Send consent request to driver (if driver info provided)
        if child_data.get('driver_info', {}).get('email'):
            self._send_consent_request(child_profile_id, child_data['driver_info']['email'])

        return {
            'child_profile_id': child_profile_id,
            'child_api_key': child_api_key,
            'relationship_id': relationship_id,
            'status': 'pending_consent'
        }
```

### 3.2 UI for Profile Hierarchy
**File:** `customer_management_tab.py`

**Implementation:**
```python
# Add to customer_management_tab.py

class ProfileHierarchyWidget(QWidget):
    """Visual tree showing Admin → Fleet/Parents → Drivers/Children."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Tree view for hierarchy
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Profile', 'Type', 'Status', 'API Key', 'Actions'])
        self.tree.setDragDropMode(QTreeWidget.InternalMove)  # Enable drag-drop
        layout.addWidget(self.tree)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.btn_add_guardian = QPushButton("Add Guardian/Fleet Owner")
        self.btn_add_vehicle = QPushButton("Add Vehicle to Selected")
        self.btn_approve = QPushButton("Approve Selected")
        self.btn_generate_key = QPushButton("Regenerate API Key")

        btn_layout.addWidget(self.btn_add_guardian)
        btn_layout.addWidget(self.btn_add_vehicle)
        btn_layout.addWidget(self.btn_approve)
        btn_layout.addWidget(self.btn_generate_key)
        layout.addLayout(btn_layout)

        # Connect signals
        self.btn_add_guardian.clicked.connect(self.add_guardian_dialog)
        self.btn_add_vehicle.clicked.connect(self.add_vehicle_dialog)
        self.btn_approve.clicked.connect(self.approve_selected)
        self.btn_generate_key.clicked.connect(self.regenerate_key)

    def load_hierarchy(self):
        """Load profile hierarchy from database."""
        self.tree.clear()

        # Get all guardian profiles
        guardians = self.hierarchy_manager.get_guardians()

        for guardian in guardians:
            guardian_item = QTreeWidgetItem([
                guardian['name'],
                guardian['tier'],
                guardian['status'],
                guardian['api_key'][:8] + '...' if guardian['api_key'] else 'Pending',
                ''
            ])
            guardian_item.setData(0, Qt.UserRole, guardian['profile_id'])

            # Add children
            children = self.hierarchy_manager.get_children(guardian['profile_id'])
            for child in children:
                child_item = QTreeWidgetItem([
                    child['name'],
                    'Vehicle',
                    child['status'],
                    child['api_key'][:8] + '...',
                    ''
                ])
                child_item.setData(0, Qt.UserRole, child['profile_id'])
                guardian_item.addChild(child_item)

            self.tree.addTopLevelItem(guardian_item)

        self.tree.expandAll()
```

---

## PHASE 4: UI/UX Enhancements (Week 4-5)

### 4.1 Dashboard Redesign
**File:** `main_pyside.py`, new file `dashboard_widget.py`

**Task:** Create main dashboard showing all vehicles with health scores.

**Implementation:**
```python
# dashboard_widget.py

class VehicleHealthDashboard(QWidget):
    """Main dashboard showing all vehicles with health scores and predictions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Summary cards row
        summary_layout = QHBoxLayout()
        self.total_vehicles_card = SummaryCard("Total Vehicles", "0", "#2196F3")
        self.critical_card = SummaryCard("Critical Alerts", "0", "#f44336")
        self.warnings_card = SummaryCard("Warnings", "0", "#FF9800")
        self.healthy_card = SummaryCard("Healthy", "0", "#4CAF50")

        summary_layout.addWidget(self.total_vehicles_card)
        summary_layout.addWidget(self.critical_card)
        summary_layout.addWidget(self.warnings_card)
        summary_layout.addWidget(self.healthy_card)
        layout.addLayout(summary_layout)

        # Vehicle grid
        self.vehicle_grid = QScrollArea()
        self.vehicle_grid_widget = QWidget()
        self.vehicle_grid_layout = QGridLayout(self.vehicle_grid_widget)
        self.vehicle_grid.setWidget(self.vehicle_grid_widget)
        self.vehicle_grid.setWidgetResizable(True)
        layout.addWidget(self.vehicle_grid)

    def load_vehicles(self):
        """Load all vehicles and display health cards."""
        vehicles = get_all_vehicles_with_predictions()

        row, col = 0, 0
        for vehicle in vehicles:
            card = VehicleHealthCard(vehicle)
            self.vehicle_grid_layout.addWidget(card, row, col)
            col += 1
            if col >= 3:  # 3 columns
                col = 0
                row += 1

        # Update summary cards
        self.total_vehicles_card.set_value(str(len(vehicles)))
        self.critical_card.set_value(str(sum(1 for v in vehicles if v.severity == 'critical')))
        self.warnings_card.set_value(str(sum(1 for v in vehicles if v.severity == 'warning')))
        self.healthy_card.set_value(str(sum(1 for v in vehicles if v.severity == 'normal')))


class VehicleHealthCard(QFrame):
    """Individual vehicle health card with predictions."""

    def __init__(self, vehicle_data: dict, parent=None):
        super().__init__(parent)
        self.vehicle = vehicle_data
        self.setup_ui()

    def setup_ui(self):
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setStyleSheet(self._get_style())

        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        name_label = QLabel(f"{self.vehicle['make']} {self.vehicle['model']}")
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # Online indicator
        online_dot = QLabel("●")
        online_dot.setStyleSheet(f"color: {'#4CAF50' if self.vehicle.get('online') else '#9E9E9E'};")

        header.addWidget(name_label)
        header.addStretch()
        header.addWidget(online_dot)
        layout.addLayout(header)

        # Health score gauge
        self.health_gauge = CircularGauge(self.vehicle.get('health_score', 0))
        layout.addWidget(self.health_gauge, alignment=Qt.AlignCenter)

        # Predictions summary
        predictions = self.vehicle.get('predictions', [])
        if predictions:
            pred_label = QLabel(f"{len(predictions)} active predictions")
            pred_label.setStyleSheet("color: #FF9800;")
            layout.addWidget(pred_label)

            # Show most urgent
            urgent = min(predictions, key=lambda p: p.get('days_remaining', 999))
            urgent_label = QLabel(f"⚠️ {urgent['component']}: {urgent['days_remaining']} days")
            layout.addWidget(urgent_label)
        else:
            no_pred = QLabel("No pending issues")
            no_pred.setStyleSheet("color: #4CAF50;")
            layout.addWidget(no_pred)

        # Action button
        btn = QPushButton("View Details")
        btn.clicked.connect(lambda: self.open_details(self.vehicle['id']))
        layout.addWidget(btn)
```

### 4.2 Prediction Timeline View
**File:** New file `prediction_timeline.py`

**Implementation:**
```python
class PredictionTimelineWidget(QWidget):
    """Visual timeline showing predicted failures over 7-30-60-90 days."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.predictions = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Timeline header with day markers
        timeline_header = QHBoxLayout()
        for day in [7, 14, 30, 60, 90]:
            marker = QLabel(f"{day}d")
            marker.setAlignment(Qt.AlignCenter)
            timeline_header.addWidget(marker)
        layout.addLayout(timeline_header)

        # Timeline bar
        self.timeline_bar = QFrame()
        self.timeline_bar.setMinimumHeight(100)
        self.timeline_bar.setStyleSheet("background: #1a1a1a; border-radius: 8px;")
        layout.addWidget(self.timeline_bar)

        # Prediction list below timeline
        self.prediction_list = QListWidget()
        layout.addWidget(self.prediction_list)

    def set_predictions(self, predictions: list):
        """Display predictions on timeline."""
        self.predictions = predictions
        self.prediction_list.clear()

        for pred in sorted(predictions, key=lambda p: p.get('days_remaining', 999)):
            item = QListWidgetItem()
            widget = PredictionListItem(pred)
            item.setSizeHint(widget.sizeHint())
            self.prediction_list.addItem(item)
            self.prediction_list.setItemWidget(item, widget)

        self.update_timeline_bar()

    def update_timeline_bar(self):
        """Draw predictions on the timeline bar."""
        # Implementation: Paint colored markers at appropriate positions
        # based on days_remaining for each prediction
        pass
```

---

## PHASE 5: Automation (Week 5-6)

### 5.1 Daily Prediction Scheduler
**File:** New file `prediction_scheduler.py`

**Implementation:**
```python
import threading
import schedule
import time
from datetime import datetime, timedelta

class PredictionScheduler:
    """Schedules and runs daily prediction jobs."""

    def __init__(self, prediction_engine, notification_service):
        self.engine = prediction_engine
        self.notifier = notification_service
        self.running = False
        self.thread = None

    def start(self):
        """Start the scheduler in background thread."""
        if self.running:
            return

        self.running = True

        # Schedule daily prediction run at 2 AM
        schedule.every().day.at("02:00").do(self.run_all_predictions)

        # Schedule hourly check for critical vehicles
        schedule.every().hour.do(self.check_critical)

        # Start background thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the scheduler."""
        self.running = False

    def _run_loop(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def run_all_predictions(self):
        """Run predictions for all active vehicles."""
        vehicles = get_all_active_vehicles()
        results = []

        for vehicle in vehicles:
            try:
                prediction = self.engine.predict_all_components(vehicle.id)
                save_prediction(vehicle.id, prediction)

                # Check for alerts
                for component, pred in prediction.items():
                    if pred['severity'] in ['critical', 'warning']:
                        self.notifier.queue_alert(vehicle, component, pred)

                results.append({'vehicle_id': vehicle.id, 'status': 'success'})
            except Exception as e:
                results.append({'vehicle_id': vehicle.id, 'status': 'error', 'error': str(e)})

        # Send summary report
        self.notifier.send_daily_summary(results)

    def check_critical(self):
        """Hourly check for vehicles needing immediate attention."""
        critical = get_critical_predictions()
        for pred in critical:
            if pred['days_remaining'] <= 3:
                self.notifier.send_urgent_alert(pred)
```

### 5.2 Notification System
**File:** `alert_notifications.py` (enhance existing)

**Implementation:**
```python
class NotificationService:
    """Handles all notifications (email, push, SMS)."""

    def __init__(self, config):
        self.email_config = config.get('email', {})
        self.firebase_config = config.get('firebase', {})
        self.queue = []

    def queue_alert(self, vehicle, component, prediction):
        """Queue an alert for batch sending."""
        self.queue.append({
            'vehicle': vehicle,
            'component': component,
            'prediction': prediction,
            'queued_at': datetime.now()
        })

    def process_queue(self):
        """Process queued alerts - send in batches."""
        if not self.queue:
            return

        # Group by owner
        by_owner = {}
        for alert in self.queue:
            owner_id = alert['vehicle'].owner_id
            if owner_id not in by_owner:
                by_owner[owner_id] = []
            by_owner[owner_id].append(alert)

        # Send batch emails
        for owner_id, alerts in by_owner.items():
            owner = get_profile(owner_id)
            self.send_email_batch(owner, alerts)

        self.queue = []

    def send_email_batch(self, owner, alerts):
        """Send batch email with all alerts."""
        # Implementation using SMTP
        pass

    def send_push_notification(self, profile_id, title, body, data=None):
        """Send push notification via Firebase."""
        # Get FCM token
        fcm_token = get_fcm_token(profile_id)
        if not fcm_token:
            return

        # Send via Firebase
        message = {
            'token': fcm_token,
            'notification': {
                'title': title,
                'body': body
            },
            'data': data or {}
        }
        # Firebase Admin SDK send
        pass

    def send_urgent_alert(self, prediction):
        """Send immediate alert for critical predictions."""
        vehicle = get_vehicle(prediction['vehicle_id'])
        owner = get_profile(vehicle.owner_id)

        title = f"⚠️ URGENT: {prediction['component'].title()} Alert"
        body = f"{vehicle.make} {vehicle.model}: {prediction['recommendation']}"

        # Send push immediately
        self.send_push_notification(owner.id, title, body, {
            'type': 'urgent_prediction',
            'vehicle_id': vehicle.id,
            'component': prediction['component']
        })

        # Also send email
        self.send_urgent_email(owner, vehicle, prediction)
```

### 5.3 Server Sync
**File:** `api_key_sync.py` (enhance existing)

**Implementation:**
```python
class ServerSyncManager:
    """Bidirectional sync between desktop and OBD server."""

    def __init__(self, server_url="https://predict.previlium.com"):
        self.server_url = server_url
        self.last_sync = None

    def sync_predictions_to_server(self):
        """Push local predictions to server for mobile access."""
        # Get predictions updated since last sync
        predictions = get_predictions_since(self.last_sync)

        for pred in predictions:
            response = requests.post(
                f"{self.server_url}/api/predictions/update",
                json={
                    'profile_id': pred['profile_id'],
                    'component': pred['component'],
                    'severity': pred['severity'],
                    'days_remaining': pred['days_remaining'],
                    'confidence': pred['confidence'],
                    'recommendation': pred['recommendation'],
                    'generated_at': pred['generated_at'].isoformat()
                },
                headers={'X-API-Key': ADMIN_API_KEY}
            )

        self.last_sync = datetime.now()

    def pull_telemetry_from_server(self):
        """Pull latest telemetry data from server."""
        response = requests.get(
            f"{self.server_url}/api/telemetry/latest",
            params={'since': self.last_sync.isoformat() if self.last_sync else None},
            headers={'X-API-Key': ADMIN_API_KEY}
        )

        if response.status_code == 200:
            telemetry_batch = response.json()
            for record in telemetry_batch:
                save_telemetry_local(record)

    def sync_profiles(self):
        """Bidirectional profile sync."""
        # Pull new profiles from server
        server_profiles = self.get_server_profiles()
        local_profiles = get_local_profiles()

        # Compare and merge
        for sp in server_profiles:
            if sp['id'] not in [lp['id'] for lp in local_profiles]:
                create_local_profile(sp)
            else:
                # Update if server version newer
                local = next(lp for lp in local_profiles if lp['id'] == sp['id'])
                if sp['updated_at'] > local['updated_at']:
                    update_local_profile(sp)

        # Push local changes to server
        for lp in local_profiles:
            if lp['sync_pending']:
                self.push_profile_to_server(lp)
```

---

# PROGRAM 2: PredictOBD Android App

## PHASE 1: Background Auto-Connect (Week 1-2)

### 1.1 Enhanced Foreground Service
**File:** `service/OBDForegroundService.kt`

**Implementation:**
```kotlin
@AndroidEntryPoint
class OBDForegroundService : Service() {

    @Inject lateinit var connectionManager: DeviceConnectionManager
    @Inject lateinit var telemetryManager: TelemetryManager
    @Inject lateinit var prefsManager: OBDDevicePreferences

    private val reconnectHandler = Handler(Looper.getMainLooper())
    private var reconnectAttempts = 0
    private val MAX_RECONNECT_ATTEMPTS = 10
    private val RECONNECT_INTERVAL_MS = 30_000L  // 30 seconds (balanced mode)

    private val reconnectRunnable = object : Runnable {
        override fun run() {
            if (connectionManager.connectionState.value != ConnectionState.Connected) {
                attemptReconnect()
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, createNotification("Initializing..."))

        // Start monitoring connection state
        observeConnectionState()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startMonitoring()
            ACTION_STOP -> stopMonitoring()
            ACTION_RECONNECT -> attemptReconnect()
        }
        return START_STICKY  // Restart if killed
    }

    private fun startMonitoring() {
        // Get last connected device
        val lastDevice = prefsManager.getLastConnectedDevice()

        if (lastDevice != null) {
            connectToDevice(lastDevice)
        } else {
            // Scan for known devices
            scanForKnownDevices()
        }
    }

    private fun connectToDevice(device: BluetoothDevice) {
        lifecycleScope.launch {
            try {
                updateNotification("Connecting to ${device.name}...")

                val connected = connectionManager.connect(device)

                if (connected) {
                    reconnectAttempts = 0
                    updateNotification("Connected to ${device.name}")
                    startDataCollection()
                } else {
                    scheduleReconnect()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Connection failed", e)
                scheduleReconnect()
            }
        }
    }

    private fun scheduleReconnect() {
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++
            val delay = RECONNECT_INTERVAL_MS * reconnectAttempts.coerceAtMost(3)

            updateNotification("Reconnecting in ${delay/1000}s (attempt $reconnectAttempts)")
            reconnectHandler.postDelayed(reconnectRunnable, delay)
        } else {
            updateNotification("Connection failed - tap to retry")
        }
    }

    private fun attemptReconnect() {
        val lastDevice = prefsManager.getLastConnectedDevice()
        lastDevice?.let { connectToDevice(it) }
    }

    private fun startDataCollection() {
        telemetryManager.startCollection(
            interval = 1000L,  // 1 second
            onData = { data ->
                // Data collected
            },
            onError = { error ->
                if (error is ConnectionLostException) {
                    scheduleReconnect()
                }
            }
        )
    }

    private fun observeConnectionState() {
        lifecycleScope.launch {
            connectionManager.connectionState.collect { state ->
                when (state) {
                    ConnectionState.Connected -> {
                        updateNotification("Connected - Collecting data")
                    }
                    ConnectionState.Disconnected -> {
                        updateNotification("Disconnected")
                        scheduleReconnect()
                    }
                    ConnectionState.Connecting -> {
                        updateNotification("Connecting...")
                    }
                    ConnectionState.Error -> {
                        updateNotification("Connection error")
                        scheduleReconnect()
                    }
                }
            }
        }
    }

    private fun createNotification(text: String): Notification {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "OBD Monitoring",
            NotificationManager.IMPORTANCE_LOW
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("PREDICT OBD")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_car)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val TAG = "OBDForegroundService"
        const val NOTIFICATION_ID = 1001
        const val CHANNEL_ID = "obd_monitoring"
        const val ACTION_START = "com.omar.predictobd.START"
        const val ACTION_STOP = "com.omar.predictobd.STOP"
        const val ACTION_RECONNECT = "com.omar.predictobd.RECONNECT"
    }
}
```

### 1.2 Boot Receiver
**File:** New file `receivers/BootReceiver.kt`

**Implementation:**
```kotlin
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            // Check if auto-connect is enabled
            val prefs = OBDDevicePreferences(context)

            if (prefs.isAutoConnectEnabled()) {
                // Start foreground service
                val serviceIntent = Intent(context, OBDForegroundService::class.java).apply {
                    action = OBDForegroundService.ACTION_START
                }

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(serviceIntent)
                } else {
                    context.startService(serviceIntent)
                }
            }
        }
    }
}
```

**AndroidManifest.xml addition:**
```xml
<receiver
    android:name=".receivers.BootReceiver"
    android:enabled="true"
    android:exported="false">
    <intent-filter>
        <action android:name="android.intent.action.BOOT_COMPLETED" />
    </intent-filter>
</receiver>
```

---

## PHASE 2: DTC Auto-Reporting (Week 2-3)

### 2.1 DTC Scanner Worker
**File:** `workers/DTCScanWorker.kt`

**Implementation:**
```kotlin
@HiltWorker
class DTCScanWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val obdConnection: OBDConnection,
    private val dtcRepository: DTCRepository,
    private val apiService: PredictApiService,
    private val notificationManager: NotificationManager
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            // Scan for DTCs
            val dtcResult = obdConnection.readDTCs()

            if (dtcResult.isSuccess) {
                val newDTCs = dtcResult.getOrNull() ?: emptyList()

                // Get previously known DTCs
                val knownDTCs = dtcRepository.getActiveDTCs()

                // Find new DTCs
                val brandNewDTCs = newDTCs.filter { new ->
                    knownDTCs.none { known -> known.code == new.code }
                }

                // Save all current DTCs locally
                dtcRepository.updateDTCs(newDTCs)

                // Report new DTCs to server
                if (brandNewDTCs.isNotEmpty()) {
                    reportDTCsToServer(brandNewDTCs)
                    showDTCNotification(brandNewDTCs)
                }
            }

            Result.success()
        } catch (e: Exception) {
            if (runAttemptCount < 3) {
                Result.retry()
            } else {
                Result.failure()
            }
        }
    }

    private suspend fun reportDTCsToServer(dtcs: List<DTCCode>) {
        val profileId = getCurrentProfileId()

        for (dtc in dtcs) {
            try {
                val response = apiService.submitDTC(
                    profileId = profileId,
                    request = DTCSubmitRequest(
                        code = dtc.code,
                        description = dtc.description,
                        severity = dtc.severity,
                        freezeFrame = dtc.freezeFrame
                    )
                )

                if (response.isSuccessful) {
                    Log.d(TAG, "DTC ${dtc.code} reported to server")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to report DTC ${dtc.code}", e)
                // Queue for later retry
                dtcRepository.markPendingUpload(dtc.code)
            }
        }
    }

    private fun showDTCNotification(dtcs: List<DTCCode>) {
        val criticalCount = dtcs.count { it.severity == "critical" }
        val title = if (criticalCount > 0) {
            "⚠️ ${criticalCount} Critical DTC Detected!"
        } else {
            "${dtcs.size} New Diagnostic Code(s)"
        }

        val body = dtcs.joinToString("\n") { "${it.code}: ${it.description}" }

        val notification = NotificationCompat.Builder(applicationContext, DTC_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(if (dtcs.size == 1) body else "${dtcs.size} codes detected")
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setSmallIcon(R.drawable.ic_warning)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(createDTCDetailsIntent(dtcs))
            .build()

        notificationManager.notify(DTC_NOTIFICATION_ID, notification)
    }

    companion object {
        const val TAG = "DTCScanWorker"
        const val DTC_CHANNEL_ID = "dtc_alerts"
        const val DTC_NOTIFICATION_ID = 2001

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<DTCScanWorker>(
                15, TimeUnit.MINUTES,  // Run every 15 minutes
                5, TimeUnit.MINUTES    // Flex interval
            )
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "dtc_scan",
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )
        }
    }
}
```

---

## PHASE 3: LLM Chat Enhancement (Week 3-4)

### 3.1 Vehicle-Aware Chat
**File:** `ui/screens/ChatScreen.kt`, `network/AIServiceClient.kt`

**Implementation:**
```kotlin
// AIServiceClient.kt
class AIServiceClient(
    private val apiService: PredictApiService,
    private val vehicleRepository: VehicleRepository,
    private val dtcRepository: DTCRepository,
    private val telemetryManager: TelemetryManager
) {
    suspend fun sendMessage(
        message: String,
        conversationId: String? = null
    ): Result<ChatResponse> {
        // Build vehicle context
        val vehicleContext = buildVehicleContext()

        val request = ChatRequest(
            message = message,
            profile_id = getCurrentProfileId(),
            vehicle_context = vehicleContext,
            conversation_id = conversationId,
            stream = false
        )

        return try {
            val response = apiService.sendChatMessage(
                apiKey = getApiKey(),
                request = request
            )

            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception(response.errorBody()?.string()))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private suspend fun buildVehicleContext(): VehicleContext {
        val profile = vehicleRepository.getCurrentProfile()
        val latestTelemetry = telemetryManager.getLatestReading()
        val activeDTCs = dtcRepository.getActiveDTCs()

        return VehicleContext(
            make = profile?.make,
            model = profile?.model,
            year = profile?.year,
            vin = profile?.vin,
            rpm = latestTelemetry?.rpm,
            speed = latestTelemetry?.speed,
            coolant_temp = latestTelemetry?.coolantTemp,
            oil_temp = latestTelemetry?.oilTemp,
            dtc_codes = activeDTCs.map { it.code },
            dtc_count = activeDTCs.size,
            last_update = latestTelemetry?.timestamp
        )
    }
}

// ChatScreen.kt addition
@Composable
fun ChatScreen(
    viewModel: ChatViewModel = hiltViewModel()
) {
    // ... existing UI code ...

    // Add "Ask about DTC" quick action
    if (activeDTCs.isNotEmpty()) {
        LazyRow(
            modifier = Modifier.padding(horizontal = 16.dp)
        ) {
            items(activeDTCs) { dtc ->
                SuggestionChip(
                    onClick = {
                        viewModel.sendMessage(
                            "What does the fault code ${dtc.code} mean for my ${vehicle.year} ${vehicle.make} ${vehicle.model}?"
                        )
                    },
                    label = { Text("Ask about ${dtc.code}") }
                )
            }
        }
    }
}
```

---

## PHASE 4: Offline Data Reliability (Week 4-5)

### 4.1 Enhanced Offline Queue
**File:** `sync/OfflineDataManager.kt`

**Implementation:**
```kotlin
class OfflineDataManager(
    private val database: PredictDatabase,
    private val apiService: PredictApiService,
    private val connectivityManager: ConnectivityManager
) {
    private val offlineDao = database.offlineQueueDao()

    suspend fun queueTelemetry(data: TelemetryData, priority: Priority = Priority.NORMAL) {
        // Compress data
        val compressed = compressData(data)

        // Check for duplicates
        val existing = offlineDao.findByHash(data.hash())
        if (existing != null) {
            // Update existing with newer data
            offlineDao.update(existing.copy(data = compressed, updatedAt = System.currentTimeMillis()))
            return
        }

        // Add to queue
        val entity = OfflineQueueEntity(
            type = QueueType.TELEMETRY,
            data = compressed,
            priority = priority.ordinal,
            createdAt = System.currentTimeMillis(),
            retryCount = 0,
            dataHash = data.hash()
        )

        offlineDao.insert(entity)

        // Trigger sync if online
        if (isOnline()) {
            syncQueue()
        }
    }

    suspend fun queueDTC(dtc: DTCCode) {
        // DTCs get high priority
        val entity = OfflineQueueEntity(
            type = QueueType.DTC,
            data = Json.encodeToString(dtc),
            priority = Priority.HIGH.ordinal,
            createdAt = System.currentTimeMillis(),
            retryCount = 0
        )

        offlineDao.insert(entity)

        if (isOnline()) {
            syncQueue()
        }
    }

    suspend fun syncQueue() {
        // Get items ordered by priority (HIGH first) and age
        val items = offlineDao.getPendingItems()

        for (item in items) {
            try {
                val success = when (item.type) {
                    QueueType.TELEMETRY -> syncTelemetry(item)
                    QueueType.DTC -> syncDTC(item)
                    QueueType.PROFILE -> syncProfile(item)
                    else -> false
                }

                if (success) {
                    offlineDao.delete(item)
                } else {
                    // Increment retry count
                    offlineDao.update(item.copy(
                        retryCount = item.retryCount + 1,
                        lastAttempt = System.currentTimeMillis()
                    ))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Sync failed for item ${item.id}", e)

                // Mark as failed after 5 retries
                if (item.retryCount >= 5) {
                    offlineDao.update(item.copy(status = QueueStatus.FAILED))
                }
            }
        }
    }

    private fun compressData(data: TelemetryData): String {
        // Use GZIP compression
        val json = Json.encodeToString(data)
        val compressed = ByteArrayOutputStream().use { baos ->
            GZIPOutputStream(baos).use { gzip ->
                gzip.write(json.toByteArray())
            }
            Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP)
        }
        return compressed
    }

    private fun isOnline(): Boolean {
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    enum class Priority {
        LOW, NORMAL, HIGH, CRITICAL
    }

    enum class QueueType {
        TELEMETRY, DTC, PROFILE, CHAT, MAINTENANCE
    }

    enum class QueueStatus {
        PENDING, SYNCING, SYNCED, FAILED
    }
}
```

---

# PROGRAM 3: Predict Guardian App

## PHASE 1: Authentication (Week 1)

### 1.1 Login Implementation
**File:** `ui/LoginActivity.kt`

**Implementation:**
```kotlin
class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    private val apiService by lazy { GuardianRetrofitClient.apiService }
    private val prefsManager by lazy { GuardianPrefsManager(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Check existing session
        if (prefsManager.hasValidToken()) {
            navigateToMain()
            return
        }

        setupUI()
    }

    private fun setupUI() {
        binding.btnLogin.setOnClickListener {
            val email = binding.etEmail.text.toString()
            val password = binding.etPassword.text.toString()

            if (validateInput(email, password)) {
                performLogin(email, password)
            }
        }

        binding.tvRegister.setOnClickListener {
            startActivity(Intent(this, RegisterActivity::class.java))
        }
    }

    private fun performLogin(email: String, password: String) {
        binding.progressBar.visibility = View.VISIBLE
        binding.btnLogin.isEnabled = false

        lifecycleScope.launch {
            try {
                val response = apiService.login(
                    LoginRequest(email = email, password = password)
                )

                if (response.isSuccessful) {
                    val authResponse = response.body()!!

                    // Save token
                    prefsManager.saveAuthToken(authResponse.token)
                    prefsManager.saveGuardianId(authResponse.guardianId)
                    prefsManager.saveEmail(email)

                    navigateToMain()
                } else {
                    val error = response.errorBody()?.string()
                    showError(parseError(error))
                }
            } catch (e: Exception) {
                showError("Connection failed. Please check your internet.")
            } finally {
                binding.progressBar.visibility = View.GONE
                binding.btnLogin.isEnabled = true
            }
        }
    }

    private fun navigateToMain() {
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }
}
```

### 1.2 Vehicle Linking
**File:** `ui/LinkVehicleActivity.kt` (new file)

**Implementation:**
```kotlin
class LinkVehicleActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLinkVehicleBinding
    private val apiService by lazy { GuardianRetrofitClient.apiService }
    private val prefsManager by lazy { GuardianPrefsManager(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLinkVehicleBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupUI()
    }

    private fun setupUI() {
        binding.btnLink.setOnClickListener {
            val apiKey = binding.etApiKey.text.toString()

            if (apiKey.isNotBlank()) {
                linkVehicle(apiKey)
            } else {
                binding.etApiKey.error = "Please enter the vehicle API key"
            }
        }

        binding.btnScanQR.setOnClickListener {
            // Launch QR scanner
            startQRScanner()
        }
    }

    private fun linkVehicle(apiKey: String) {
        binding.progressBar.visibility = View.VISIBLE

        lifecycleScope.launch {
            try {
                val response = apiService.linkVehicle(
                    token = "Bearer ${prefsManager.getAuthToken()}",
                    request = LinkVehicleRequest(vehicleApiKey = apiKey)
                )

                if (response.isSuccessful) {
                    val linkResponse = response.body()!!

                    // Show consent request sent message
                    showSuccessDialog(
                        title = "Link Request Sent",
                        message = "A consent request has been sent to the driver of ${linkResponse.vehicleName}. " +
                                "You will be notified once they approve."
                    )
                } else {
                    val error = response.errorBody()?.string()
                    showError(parseError(error))
                }
            } catch (e: Exception) {
                showError("Connection failed.")
            } finally {
                binding.progressBar.visibility = View.GONE
            }
        }
    }
}
```

---

## PHASE 2: Real-Time Monitoring (Week 2-3)

### 2.1 WebSocket Integration
**File:** `network/GuardianWebSocketClient.kt` (new file)

**Implementation:**
```kotlin
class GuardianWebSocketClient(
    private val prefsManager: GuardianPrefsManager,
    private val onVehicleUpdate: (VehicleUpdate) -> Unit,
    private val onAlert: (GuardianAlert) -> Unit,
    private val onConnectionChange: (Boolean) -> Unit
) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .pingInterval(30, TimeUnit.SECONDS)
        .build()

    private val reconnectHandler = Handler(Looper.getMainLooper())
    private var reconnectDelay = 1000L

    fun connect() {
        val request = Request.Builder()
            .url("wss://predict.previlium.com/ws/guardian")
            .addHeader("Authorization", "Bearer ${prefsManager.getAuthToken()}")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                reconnectDelay = 1000L
                onConnectionChange(true)

                // Subscribe to linked vehicles
                subscribeToVehicles()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(text)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                onConnectionChange(false)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                onConnectionChange(false)
                scheduleReconnect()
            }
        })
    }

    private fun handleMessage(text: String) {
        try {
            val message = Json.decodeFromString<WebSocketMessage>(text)

            when (message.type) {
                "vehicle_update" -> {
                    val update = Json.decodeFromString<VehicleUpdate>(message.data)
                    onVehicleUpdate(update)
                }
                "alert" -> {
                    val alert = Json.decodeFromString<GuardianAlert>(message.data)
                    onAlert(alert)
                }
                "command_response" -> {
                    // Handle command acknowledgment
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse message", e)
        }
    }

    private fun subscribeToVehicles() {
        val linkedVehicles = prefsManager.getLinkedVehicleIds()
        val subscribeMessage = mapOf(
            "type" to "subscribe",
            "vehicles" to linkedVehicles
        )
        webSocket?.send(Json.encodeToString(subscribeMessage))
    }

    private fun scheduleReconnect() {
        reconnectHandler.postDelayed({
            connect()
        }, reconnectDelay)

        reconnectDelay = (reconnectDelay * 2).coerceAtMost(30000L)
    }

    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        webSocket = null
    }

    companion object {
        const val TAG = "GuardianWebSocket"
    }
}
```

### 2.2 Map Integration
**File:** `ui/VehicleDetailActivity.kt`

**Implementation:**
```kotlin
class VehicleDetailActivity : AppCompatActivity(), OnMapReadyCallback {

    private lateinit var binding: ActivityVehicleDetailBinding
    private lateinit var googleMap: GoogleMap
    private var vehicleMarker: Marker? = null
    private var routePolyline: Polyline? = null

    private lateinit var webSocketClient: GuardianWebSocketClient
    private val vehicleId by lazy { intent.getStringExtra(EXTRA_VEHICLE_ID)!! }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityVehicleDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Initialize map
        val mapFragment = supportFragmentManager.findFragmentById(R.id.map) as SupportMapFragment
        mapFragment.getMapAsync(this)

        setupWebSocket()
        loadVehicleDetails()
    }

    override fun onMapReady(map: GoogleMap) {
        googleMap = map
        googleMap.uiSettings.isZoomControlsEnabled = true

        // Initial position
        val initialPosition = LatLng(25.2854, 51.5310)  // Qatar
        googleMap.moveCamera(CameraUpdateFactory.newLatLngZoom(initialPosition, 12f))
    }

    private fun setupWebSocket() {
        webSocketClient = GuardianWebSocketClient(
            prefsManager = GuardianPrefsManager(this),
            onVehicleUpdate = { update ->
                runOnUiThread {
                    if (update.vehicleId == vehicleId) {
                        updateVehiclePosition(update)
                        updateMetrics(update)
                    }
                }
            },
            onAlert = { alert ->
                runOnUiThread {
                    if (alert.vehicleId == vehicleId) {
                        showAlertBanner(alert)
                    }
                }
            },
            onConnectionChange = { connected ->
                runOnUiThread {
                    binding.connectionIndicator.setImageResource(
                        if (connected) R.drawable.ic_online else R.drawable.ic_offline
                    )
                }
            }
        )
        webSocketClient.connect()
    }

    private fun updateVehiclePosition(update: VehicleUpdate) {
        val position = LatLng(update.latitude, update.longitude)

        if (vehicleMarker == null) {
            vehicleMarker = googleMap.addMarker(
                MarkerOptions()
                    .position(position)
                    .icon(BitmapDescriptorFactory.fromResource(R.drawable.ic_car_marker))
                    .rotation(update.heading)
                    .anchor(0.5f, 0.5f)
            )
            googleMap.animateCamera(CameraUpdateFactory.newLatLngZoom(position, 15f))
        } else {
            // Animate marker movement
            animateMarker(vehicleMarker!!, position, update.heading)
        }

        // Update route if tracking
        if (isTrackingRoute) {
            routePoints.add(position)
            updateRoutePolyline()
        }
    }

    private fun updateMetrics(update: VehicleUpdate) {
        binding.tvSpeed.text = "${update.speed} km/h"
        binding.tvRpm.text = "${update.rpm} RPM"
        binding.tvDirection.text = getDirectionName(update.heading)
        binding.tvLastUpdate.text = "Updated ${formatTimeAgo(update.timestamp)}"

        // Color code speed
        val speedColor = when {
            update.speed > 120 -> Color.RED
            update.speed > 80 -> Color.YELLOW
            else -> Color.WHITE
        }
        binding.tvSpeed.setTextColor(speedColor)
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocketClient.disconnect()
    }

    companion object {
        const val EXTRA_VEHICLE_ID = "vehicle_id"
    }
}
```

---

## PHASE 3: Alerts & Push Notifications (Week 3-4)

### 3.1 Firebase Setup
**File:** `services/GuardianFirebaseService.kt` (new file)

**Implementation:**
```kotlin
class GuardianFirebaseService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        // Send token to server
        sendTokenToServer(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        // Handle data payload
        message.data.let { data ->
            when (data["type"]) {
                "alert" -> handleAlert(data)
                "command_response" -> handleCommandResponse(data)
                "consent_update" -> handleConsentUpdate(data)
            }
        }

        // Handle notification payload
        message.notification?.let { notification ->
            showNotification(notification.title, notification.body, message.data)
        }
    }

    private fun handleAlert(data: Map<String, String>) {
        val alert = GuardianAlert(
            id = data["alert_id"] ?: "",
            vehicleId = data["vehicle_id"] ?: "",
            type = data["alert_type"] ?: "",
            severity = data["severity"] ?: "info",
            message = data["message"] ?: "",
            timestamp = data["timestamp"]?.toLongOrNull() ?: System.currentTimeMillis()
        )

        // Save to local database
        AlertRepository.getInstance(this).insert(alert)

        // Show notification with appropriate priority
        val priority = when (alert.severity) {
            "critical" -> NotificationCompat.PRIORITY_MAX
            "warning" -> NotificationCompat.PRIORITY_HIGH
            else -> NotificationCompat.PRIORITY_DEFAULT
        }

        showAlertNotification(alert, priority)
    }

    private fun showAlertNotification(alert: GuardianAlert, priority: Int) {
        val channelId = if (alert.severity == "critical") {
            CRITICAL_CHANNEL_ID
        } else {
            ALERT_CHANNEL_ID
        }

        val intent = Intent(this, VehicleDetailActivity::class.java).apply {
            putExtra(VehicleDetailActivity.EXTRA_VEHICLE_ID, alert.vehicleId)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }

        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_alert)
            .setContentTitle(getAlertTitle(alert))
            .setContentText(alert.message)
            .setPriority(priority)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .build()

        // Vibrate pattern for critical alerts
        if (alert.severity == "critical") {
            val vibrator = getSystemService(Vibrator::class.java)
            vibrator?.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 500, 200, 500), -1))
        }

        NotificationManagerCompat.from(this).notify(alert.hashCode(), notification)
    }

    private fun sendTokenToServer(token: String) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val prefs = GuardianPrefsManager(this@GuardianFirebaseService)
                val authToken = prefs.getAuthToken() ?: return@launch

                GuardianRetrofitClient.apiService.updateFCMToken(
                    token = "Bearer $authToken",
                    request = UpdateFCMTokenRequest(fcmToken = token)
                )
            } catch (e: Exception) {
                Log.e(TAG, "Failed to update FCM token", e)
            }
        }
    }

    companion object {
        const val TAG = "GuardianFirebase"
        const val CRITICAL_CHANNEL_ID = "critical_alerts"
        const val ALERT_CHANNEL_ID = "guardian_alerts"
    }
}
```

---

## TESTING CHECKLIST

### Desktop App
- [ ] LLM responds correctly to prediction correction prompts
- [ ] All 18 tabs have working backend connections
- [ ] Prediction pipeline runs successfully
- [ ] Brake prediction algorithm validated with test data
- [ ] Battery prediction algorithm validated
- [ ] Oil change prediction validated
- [ ] Profile hierarchy creates correct relationships
- [ ] API keys sync between desktop and server
- [ ] Daily scheduler runs at configured time
- [ ] Email notifications sent successfully
- [ ] Push notifications received on mobile

### PredictOBD Android
- [ ] Auto-connect works on app restart
- [ ] Auto-connect works after device reboot
- [ ] OBD reconnection works after connection loss
- [ ] DTCs scanned and saved locally
- [ ] DTCs uploaded to server
- [ ] DTC notifications displayed
- [ ] Chat includes vehicle context
- [ ] Offline queue stores data when disconnected
- [ ] Offline data syncs when reconnected
- [ ] Data compression working

### Guardian Android
- [ ] Login successful with valid credentials
- [ ] Login fails gracefully with invalid credentials
- [ ] JWT token stored securely
- [ ] Vehicle linking sends consent request
- [ ] WebSocket connects and receives updates
- [ ] Map displays vehicle location
- [ ] Location updates animate smoothly
- [ ] Alerts received via push notification
- [ ] Critical alerts vibrate device
- [ ] Geofence creation works

---

## DEPENDENCIES TO ADD

### Desktop (requirements.txt)
```
schedule>=1.2.0
firebase-admin>=6.0.0
apscheduler>=3.10.0
```

### Android (build.gradle.kts)
```kotlin
// Guardian app
implementation("com.google.android.gms:play-services-maps:18.2.0")
implementation("com.google.firebase:firebase-messaging-ktx:23.4.0")

// PredictOBD app
implementation("androidx.work:work-runtime-ktx:2.9.0")
implementation("com.google.firebase:firebase-messaging-ktx:23.4.0")
```

---

## ESTIMATED EFFORT

| Phase | Program | Tasks | Complexity |
|-------|---------|-------|------------|
| 1 | Desktop | Core Backend | Medium |
| 2 | Desktop | Prediction Engine | High |
| 3 | Desktop | Profile Management | Medium |
| 4 | Desktop | UI/UX | Medium |
| 5 | Desktop | Automation | Medium |
| 1 | PredictOBD | Background Service | High |
| 2 | PredictOBD | DTC Reporting | Medium |
| 3 | PredictOBD | LLM Chat | Medium |
| 4 | PredictOBD | Offline Data | Medium |
| 1 | Guardian | Authentication | Low |
| 2 | Guardian | Real-Time Map | High |
| 3 | Guardian | Alerts/Push | Medium |

---

*Document generated: 2026-01-07*
*Version: 1.0*
