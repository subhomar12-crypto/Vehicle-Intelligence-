"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Phi Explainer
"""

"""
Small test script to verify that phi_explainer.py and Ollama + Phi are working.

Run from Command Prompt while in this folder:

    python test_phi_explainer.py

You should see a human-readable explanation printed.
"""

from phi_explainer import get_phi_explanation


def main():
    # Minimal fake summary just to test
    health_summary = {
        "vehicle": {
            "make": "Nissan",
            "model": "Altima",
            "year": 2017,
            "license_plate": "TEST123"
        },
        "overall_health_score": 72,
        "subsystems": {
            "engine": {
                "score": 68,
                "issues": [
                    "High engine load at highway speeds",
                    "Frequent RPM above 4000"
                ]
            },
            "cooling": {
                "score": 60,
                "issues": [
                    "Coolant temperature reached 112°C on climbs",
                    "Coolant often > 100°C in city traffic"
                ]
            }
        },
        "dtc_codes": ["P0300", "P0420"],
        "recent_anomalies": [
            "Battery voltage dropped to 11.7V during crank",
            "Coolant temperature outside optimal range for 15 minutes"
        ],
        "region": "Qatar / hot climate"
    }

    explanation = get_phi_explanation(health_summary)
    print("\n=== PHI EXPLANATION ===\n")
    print(explanation)


if __name__ == "__main__":
    main()
