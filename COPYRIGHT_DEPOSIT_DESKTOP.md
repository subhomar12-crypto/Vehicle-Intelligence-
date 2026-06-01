# COPYRIGHT DEPOSIT MATERIAL
## PREDICT Desktop - Vehicle Intelligence Analytics Platform

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

## CODE SAMPLES

### Sample 1: Main Application Entry Point (main_pyside.py)

**First 25 Lines:**

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

**Last 25 Lines:**

```python
    # Apply professional theme
    ProfessionalTheme.apply_theme(app)

    # Initialize LLM assistant (lazy loading - will load on first use)
    logger.info("Initializing LLM assistant (lazy loading)...")
    llm_assistant = get_llm_assistant()
    # Model will load when first used in chat tab to improve startup performance
    logger.info("LLM assistant initialized, creating main window...")

    # Now create main window
    try:
        window = MainWindow()
        logger.info("Main window created successfully")
        window.show()
    except Exception as e:
        logger.critical(f"Failed to create main window: {e}")
        QMessageBox.critical(None, "Startup Error", f"Failed to start application:\n{e}")
        sys.exit(1)

    # Run application
    exit_code = app.exec()
    logger.info(f"Application exited with code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
```

**File Statistics:**
- Total Lines: 6,280
- Type: Python source code
- Purpose: Main application entry point and window management

---

### Sample 2: AI Intelligence Engine (unified_ai_module.py)

**First 25 Lines:**

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

**Last 25 Lines:**

```python

        analysis = {
            'total_codes': len(dtc_codes),
            'active_codes': len(active_codes),
            'high_severity_count': len(high_severity),
            'codes_by_system': {},
            'recommendations': []
        }

        # Group by system
        for dtc in active_codes:
            system = dtc.get('system', 'Unknown')
            if system not in analysis['codes_by_system']:
                analysis['codes_by_system'][system] = []
            analysis['codes_by_system'][system'].append(dtc['code'])

        # Generate recommendations
        if high_severity:
            analysis['recommendations'].append("URGENT: High severity codes detected. Seek immediate inspection.")

        for system, codes in analysis['codes_by_system'].items():
            if len(codes) >= 2:
                analysis['recommendations'].append(f"Multiple {system} issues detected. Comprehensive {system} inspection recommended.")

        analysis['status'] = 'critical' if high_severity else 'warning' if active_codes else 'healthy'
```

**File Statistics:**
- Total Lines: 939
- Type: Python source code
- Purpose: Core AI intelligence and health analysis

---

### Sample 3: Predictive Failure Engine (predictive_failure_engine.py)

**First 25 Lines:**

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

**Last 25 Lines:**

```python

            if isinstance(new_data, list):
                new_df = pd.DataFrame(new_data)
            else:
                new_df = pd.DataFrame([new_data]) if isinstance(new_data, dict) else new_data.copy()

            if new_df is None or new_df.empty:
                return False

            if target_column not in new_df.columns:
                new_df[target_column] = self._create_synthetic_target(new_df)

            if self.training_history:
                existing_data = self.training_history[-1].get('training_data')
                if isinstance(existing_data, pd.DataFrame):
                    combined = pd.concat([existing_data, new_df], ignore_index=True)
                else:
                    combined = new_df
            else:
                combined = new_df

            result = self.train_advanced_ensemble(combined, target_column=target_column)
            return bool(result.get('success'))

        except Exception as e:
            print(f"Error updating models with new data: {e}")
```

**File Statistics:**
- Total Lines: 2,560
- Type: Python source code
- Purpose: Machine learning failure prediction system

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

---

**Document Version:** 1.0
**Date Prepared:** January 9, 2026
**Prepared For:** U.S. Copyright Office Registration
**Case Number:** 1-15073479562

---

**END OF DEPOSIT MATERIAL**
