# COPYRIGHT DEPOSIT MATERIAL
## PREDICT Desktop - Vehicle Intelligence Analytics Platform
### STABLE CODE SECTIONS (Will Not Change)

---

**Copyright Registration Case:** 1-15073479562
**Copyright Claimant:** Omar Ahmad Sobeh
**Date of Creation:** January 2026
**Type of Work:** Computer Software (Literary Work)

---

## WORK IDENTIFICATION

**Title:** PREDICT Desktop - Vehicle Intelligence Analytics Platform

**Nature of Work:** Professional Windows desktop application for AI-powered vehicle predictive maintenance and real-time diagnostic analysis

**Technology Stack:**
- Language: Python 3.x
- GUI Framework: PySide6 (Qt for Python)
- AI/ML: TensorFlow, Keras, scikit-learn
- Database: SQLite with SQLAlchemy
- Total Lines of Code: ~60,000
- Total Files: ~150+

---

## SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    PREDICT Desktop                          │
│              Vehicle Intelligence Platform                   │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│   AI Engine    │  │  OBD Reader │  │  Data Manager   │
│                │  │             │  │                 │
│ • LSTM Neural  │  │ • Real-time │  │ • SQLite DB     │
│ • CNN-LSTM     │  │ • 50+ PIDs  │  │ • Export CSV    │
│ • Physics AI   │  │ • DTC codes │  │ • PDF Reports   │
└────────────────┘  └─────────────┘  └─────────────────┘
```

---

## KEY FEATURES

### 1. AI-Powered Predictive Maintenance
- LSTM Neural Networks for failure prediction
- CNN-LSTM hybrid architecture
- Physics-constrained AI validation
- Multi-component failure analysis
- 30-60 day prediction horizon

### 2. Real-Time Vehicle Monitoring
- Live OBD-II data streaming (50+ parameters)
- RPM, coolant temp, oil temp, battery voltage
- Engine load, throttle position, fuel pressure
- Real-time visualization with gauges
- Historical data trending

### 3. Diagnostic Capabilities
- DTC (Diagnostic Trouble Code) reading
- Code lookup database
- Severity classification
- Multi-system analysis
- Freeze frame data

### 4. Professional UI/UX
- Dark theme with modern design
- Interactive dashboards
- Real-time charts and graphs
- Multi-vehicle management
- Customizable alerts

### 5. Data Management
- SQLite database storage
- CSV export functionality
- PDF report generation
- Cloud sync capabilities
- Data encryption

---

## PROPRIETARY ALGORITHMS

This software contains the following proprietary and confidential algorithms:

1. **Physics-Constrained LSTM** - Custom neural network implementation
2. **Multi-Sensor Fusion Algorithm** - Proprietary data correlation
3. **Adaptive Threshold Prediction** - Vehicle-specific wear analysis
4. **Failure Cascade Detection** - Secondary failure prediction
5. **Confidence Interval Calculation** - Bayesian approach
6. **Real-Time Anomaly Detection** - FFT-based vibration analysis

---

## CODE SAMPLES (STABLE SECTIONS)

### Sample 1: Main Application - Initialization (main_pyside.py)

**Lines 1-25: Copyright Header and Core Imports (STABLE)**

```python
"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Main Desktop Application Entry Point

Main PySide Application with Enhanced UI and Full Integration
Features:
- Professional dark theme with modern design
- Enhanced circular and linear gauges
- Full AI integration (UnifiedAIModule + PredictiveFailureEngine)
- Real-time vehicle monitoring
- Comprehensive failure prediction
- Secure data handling
"""

from __future__ import annotations  # PEP 563: Postponed evaluation of annotations

import sys
import os
```

**Lines 100-129: Module Import Definitions (STABLE)**

```python
    """Import all Qt-dependent modules after QApplication is created."""
    global DATA_MANAGEMENT_TAB_AVAILABLE, DEVICES_TAB_AVAILABLE
    global NOTIFICATIONS_TAB_AVAILABLE, USER_MANAGEMENT_TAB_AVAILABLE
    global MOBILE_SERVER_AVAILABLE

    # Import modules
    global ConnectionTab, ProfessionalConnectivityManager, VehicleProfileManager
    global UnifiedAIModule, ProfileManager, PDFExporter, CloudSyncManager
    global VINDecoder, PredictiveFailureEngine, DTCManager, DTCTab

    from connection_tab import ConnectionTab
    from connectivity_module import ProfessionalConnectivityManager
    from vehicle_module import VehicleProfileManager
    from unified_ai_module import UnifiedAIModule
    from profile_manager import ProfileManager
    from pdf_exporter import PDFExporter
    from cloud_sync import CloudSyncManager
    from vin_decoder import VINDecoder
    from predictive_failure_engine import PredictiveFailureEngine
    from component_prediction_models import ComponentPredictor
    from dtc_module import DTCManager
    from dtc_tab import DTCTab

    # Import LLM Assistant modules
    global get_llm_assistant, StartupScreen, ChatTab, start_llm_api_server
    from llm_assistant import get_llm_assistant
    from startup_screen import StartupScreen
    from chat_tab import ChatTab
    from llm_api_server import start_llm_api_server
```

**File Statistics:**
- Total Lines: 6,280
- Type: Python source code
- Purpose: Main application entry point and window management
- **Sections shown:** Core imports and module definitions (will not change)

---

### Sample 2: AI Intelligence Engine - Core Initialization (unified_ai_module.py)

**Lines 1-25: Copyright Header and Imports (STABLE)**

```python
"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Unified AI Module - Core Intelligence Engine

UNIFIED AI MODULE - FIXED VERSION WITH UNIQUE INSIGHTS PER VEHICLE
=========================================================================
FIXES:
1. Generates unique insights based on ACTUAL vehicle data
2. Health scores based on REAL sensor readings
3. Different analysis for each vehicle profile
4. Integration with DTC codes for accurate diagnostics
5. Real-time data analysis instead of hardcoded values
=========================================================================
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
```

**Lines 100-129: Class Initialization Data Structures (STABLE)**

```python
            'retrain_count': 0,
            'adaptive_updates': 0,
        }

        self.feedback_buffer = deque(maxlen=1000)
        self.adaptive_thresholds = {}
        self.model_performance_tracker = {}
        self.last_update_time = None

        # Environmental Context (Privacy-safe data)
        self.environmental_context = {
            'ambient_temp': 25.0,  # Default to 25°C if sensor unavailable
        }

        # Cache for vehicle-specific data
        self._vehicle_data_cache = {}

        # Initialize Enhanced Prediction Engine
        self.enhanced_engine = None
        self._init_enhanced_engine()

        print("[OK] UnifiedAIModule initialized - ENHANCED VERSION with advanced analytics")

    def _init_enhanced_engine(self):
        """Initialize the enhanced prediction engine."""
        try:
            from enhanced_prediction_engine import EnhancedPredictionEngine
            self.enhanced_engine = EnhancedPredictionEngine()
            self.enhanced_engine.set_unified_ai(self)
            print("[OK] Enhanced Prediction Engine integrated")
```

**Lines 200-229: Sensor Analysis Algorithm (STABLE)**

```python
        if sensor_name == 'coolant_temp':
            # In extreme heat (>35°C), engines naturally run hotter.
            # We relax the warning threshold slightly to prevent false alarms.
            if ambient > 35:
                heat_offset = (ambient - 35) * 0.5  # +0.5°C tolerance per degree of heat
                thresholds['optimal_max'] = thresholds.get('optimal_max', 100) + heat_offset
                thresholds['critical_high'] = thresholds.get('critical_high', 110) + heat_offset

        elif sensor_name == 'intake_temp':
            # Intake temp is physically tied to ambient temp
            thresholds['optimal_min'] = ambient
            thresholds['optimal_max'] = ambient + 30  # Expect intake to be +30 over ambient max
            thresholds['critical_high'] = ambient + 50

        return thresholds

    def _analyze_sensor_value(self, sensor_name: str, value: float) -> Dict[str, Any]:
        """Analyze a single sensor value against thresholds"""
        thresholds = self._get_dynamic_thresholds(sensor_name)

        if not thresholds:
            return {'status': 'unknown', 'score': 50, 'message': 'No thresholds defined'}

        min_val = thresholds.get('min', 0)
        max_val = thresholds.get('max', 100)
        opt_min = thresholds.get('optimal_min', min_val)
        opt_max = thresholds.get('optimal_max', max_val)
        crit_high = thresholds.get('critical_high')
        crit_low = thresholds.get('critical_low')
        unit = thresholds.get('unit', '')
```

**File Statistics:**
- Total Lines: 939
- Type: Python source code
- Purpose: Core AI intelligence and health analysis
- **Sections shown:** Initialization and core sensor analysis (will not change)

---

### Sample 3: Predictive Failure Engine - Core Architecture (predictive_failure_engine.py)

**Lines 1-25: Copyright Header and Imports (STABLE)**

```python
"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Predictive Failure Engine - Failure Forecasting System

Hybrid predictive engine for vehicle failure forecasting.
Uses rule-based logic + trend analysis to predict 3-7 day failure risks.
"""

import time
from typing import Dict, List, Tuple, Any, Optional
from collections import deque
import statistics
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from sklearn.ensemble import GradientBoostingClassifier, VotingClassifier
```

**Lines 150-179: Core Data Structures (STABLE)**

```python
        self.maintenance_frames: Dict[str, pd.DataFrame] = {}   # dataset_id -> df

        # NEW: Dataset schemas storage
        self.dataset_schemas: Dict[str, Dict[str, Any]] = {}  # dataset_id -> {label_column, feature_columns, task_type, dataset_type}
        self.dataset_analysis: Dict[str, Dict[str, Any]] = {} # dataset_id -> analysis results

        # Trained ML models and metadata
        self.models: Dict[str, Any] = {}          # e.g. {"overall_failure_7d": model, "maintenance_30d": model}
        self.model_metadata: Dict[str, Any] = {}  # e.g. {"overall_failure_7d": {"samples": ..., "accuracy": ..., "f1": ...}}

        # Learned parameters to share with unified_ai_module
        self.learned_thresholds: Dict[str, float] = {}
        self.model_feature_importances: Dict[str, Dict[str, float]] = {}

        # Hybrid AI Engine
        self.hybrid_ai = HybridAIEngine()

        # Training cancellation flag
        self._cancel_training = False

        # Attempt to load existing models from disk at startup
        self._load_existing_models()

    def _load_existing_models(self) -> None:
        """
        Load previously trained models from self.models_dir if they exist.
        This allows using ML predictions without retraining every time.
        """
        model_files = {
            "overall_failure_7d": os.path.join(self.models_dir, "overall_failure_7d.pkl"),
```

**Lines 300-329: Dataset Analysis Algorithm (STABLE)**

```python
                "unique_count": int(unique_count),
                "sample_values": sample_values
            }
            columns_info.append(col_info)

            # Check if numeric (for feature candidates)
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_columns.append(col)

            # Check if potential label column
            is_potential_label = False
            label_score = 0

            # Score based on name hints
            col_lower = col.lower()
            for hint in label_hints:
                if hint in col_lower:
                    label_score += 2

            # Score based on unique values (binary or small categorical)
            if unique_count == 2:
                label_score += 3  # Perfect binary label
            elif 2 <= unique_count <= 5:
                label_score += 2  # Small categorical
            elif unique_count <= 10:
                label_score += 1  # Medium categorical

            # Score based on data type
            if pd.api.types.is_numeric_dtype(df[col]) and unique_count <= 10:
                label_score += 1
```

**File Statistics:**
- Total Lines: 2,560
- Type: Python source code
- Purpose: Machine learning failure prediction system
- **Sections shown:** Core architecture and dataset analysis (will not change)

---

## DEPENDENCIES (requirements.txt)

```
# Core Dependencies
numpy>=1.21.0,<2.0.0
pandas>=1.5.0,<3.0.0
scipy>=1.9.0

# GUI Framework
PyQt5>=5.15.0,<6.0.0
pyqtgraph>=0.13.0

# Web Framework & API
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0

# Machine Learning
tensorflow>=2.15.0,<2.17.0
scikit-learn>=1.3.0
keras>=3.0.0

# OBD-II Communication
python-obd>=0.7.1
pyserial>=3.5

# Security & Encryption
cryptography>=41.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4

# PDF Generation
reportlab>=4.0.0
PyPDF2>=3.0.0
```

---

## PROJECT STRUCTURE

```
PREDICT Desktop/
├── main_pyside.py                 (6,280 lines) - Main application
├── unified_ai_module.py           (939 lines)   - AI engine
├── predictive_failure_engine.py   (2,560 lines) - ML predictions
├── lstm_predictor.py              - LSTM models
├── cnn_lstm_model.py             - CNN-LSTM hybrid
├── attention_lstm_model.py       - Attention mechanism
├── physics_constraints.py        - Physics validation
├── enhanced_prediction_engine.py - Prediction hub
├── db_utils.py                   - Database utilities
├── obd_connection_manager.py     - OBD communication
├── data_encryption.py            - Security
├── requirements.txt              - Dependencies
└── [140+ additional Python files]
```

---

## DEPOSIT STRATEGY

**This deposit includes STABLE code sections that will NOT change:**

### ✅ What's Included:
1. **Copyright headers** - Never change
2. **Core imports** - Rarely change (stable dependencies)
3. **Class initialization code** - Core data structures (stable)
4. **Algorithm implementations** - Established logic (stable)
5. **Configuration definitions** - Base architecture (stable)

### ✅ What's NOT Included:
1. ❌ End-of-file code - May add new features here
2. ❌ Experimental functions - May be modified
3. ❌ UI styling details - May be adjusted
4. ❌ Helper utilities - May be refactored

**Result:** This deposit represents PERMANENT sections of the codebase that establish the core functionality and will remain unchanged.

---

## INTELLECTUAL PROPERTY STATEMENT

This software is the original work of Omar Ahmad Sobeh, created in January 2026. All source code, algorithms, database schemas, UI designs, and documentation are proprietary and confidential.

The software contains trade secrets and proprietary algorithms that provide competitive advantage in the vehicle diagnostics and predictive maintenance market.

No portion of this code was copied from third-party sources. All AI/ML implementations, physics models, and diagnostic algorithms are original works.

---

## COPYRIGHT NOTICE

```
Copyright © 2026 PREDICT
All rights reserved.

PREDICT Desktop - Vehicle Intelligence Analytics Platform

This software and all associated documentation, source code, algorithms,
and materials are the exclusive property of PREDICT and Omar Ahmad Sobeh.

Unauthorized copying, modification, distribution, or use is strictly
prohibited and may result in legal action.
```

---

## DECLARATION

I, Omar Ahmad Sobeh, hereby declare that:

1. I am the sole author and creator of this software
2. This work is original and not copied from any other source
3. I own all rights to this work
4. The information provided in this deposit is true and accurate
5. This software was created in January 2026
6. The code sections shown are stable, core functionality that will not change

---

**Document Version:** 2.0 (Stable Sections Only)
**Date Prepared:** January 9, 2026
**Prepared For:** U.S. Copyright Office Registration
**Case Number:** 1-15073479562

---

**END OF DEPOSIT MATERIAL**
