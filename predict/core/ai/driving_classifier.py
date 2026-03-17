"""Driving context classifier — heuristic-based driving pattern detection."""

import numpy as np
from typing import List, Dict, Any


class DrivingContextClassifier:
    """Classify driving context from a telemetry window."""

    def classify(self, telemetry_window: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a window of readings and return driving context.

        Returns:
            {
                "context": "city" | "highway" | "aggressive" | "mixed" | "idle",
                "speed_stats": {"mean": float, "max": float, "std": float},
                "rpm_stats": {"mean": float, "max": float, "std": float},
                "stop_count": int,        # number of speed=0 events
                "hard_accel_count": int,   # RPM jumps > 1500 in 2s
                "hard_brake_count": int,   # speed drops > 20 km/h in 2s
                "confidence": float,       # 0-1
            }
        """
        # Extract speed and RPM arrays
        speeds = [r.get("speed", 0) or 0 for r in telemetry_window]
        rpms = [r.get("rpm", 0) or 0 for r in telemetry_window]

        # Speed distribution analysis
        speed_mean = np.mean(speeds) if speeds else 0
        speed_max = max(speeds) if speeds else 0
        speed_std = np.std(speeds) if speeds else 0

        # RPM distribution analysis
        rpm_mean = np.mean(rpms) if rpms else 0
        rpm_max = max(rpms) if rpms else 0
        rpm_std = np.std(rpms) if rpms else 0

        # Stop frequency
        stop_count = sum(1 for i in range(1, len(speeds))
                        if speeds[i] == 0 and speeds[i-1] > 0)

        # Hard acceleration/braking
        hard_accel = 0
        hard_brake = 0
        for i in range(2, len(speeds)):
            speed_delta = speeds[i] - speeds[i-2]
            rpm_delta = rpms[i] - rpms[i-2]
            if rpm_delta > 1500:
                hard_accel += 1
            if speed_delta < -20:
                hard_brake += 1

        # Classify
        if speed_mean < 5 and rpm_mean < 1200:
            context = "idle"
        elif hard_accel > 3 or hard_brake > 3 or rpm_max > 4500:
            context = "aggressive"
        elif speed_mean > 60 and stop_count < 2:
            context = "highway"
        elif stop_count > 5 or speed_mean < 40:
            context = "city"
        else:
            context = "mixed"

        return {
            "context": context,
            "speed_stats": {"mean": float(speed_mean), "max": float(speed_max), "std": float(speed_std)},
            "rpm_stats": {"mean": float(rpm_mean), "max": float(rpm_max), "std": float(rpm_std)},
            "stop_count": stop_count,
            "hard_accel_count": hard_accel,
            "hard_brake_count": hard_brake,
            "confidence": 0.85,  # heuristic confidence
        }
