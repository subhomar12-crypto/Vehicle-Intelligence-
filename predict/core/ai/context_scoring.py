"""
Context-Aware Scoring Engine (Layer A)

Adjusts health thresholds based on real-time driving conditions.
Prevents false alarms when a sensor reading is elevated but normal
given the ambient environment.

Example: Coolant at 102°C is fine in Qatar summer + slow traffic,
         but concerning on a cool highway day.
"""
from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ContextAwareScorer:
    """
    Scores sensor readings relative to expected values given driving context.

    Context keys used:
        ambient_temp  (float) — °C, defaults to 35 (Qatar summer)
        speed         (float) — km/h
        engine_load   (float) — 0-100%
        rpm           (float) — engine RPM
        idle          (bool)  — True if idling
    """

    # Default Qatar climate assumption
    DEFAULT_AMBIENT = 35.0

    def score_sensor(
        self,
        sensor: str,
        value: float,
        context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """
        Score a sensor reading in context.

        Returns:
            (health_score 0-100, explanation_str)
        """
        if sensor == "coolant_temp":
            return self._score_coolant(value, context)
        elif sensor == "battery_voltage":
            return self._score_battery(value, context)
        elif sensor == "oil_temp":
            return self._score_oil_temp(value, context)
        elif sensor == "engine_load":
            return self._score_engine_load(value, context)
        elif sensor == "intake_temp":
            return self._score_intake_temp(value, context)
        elif sensor == "boost_pressure":
            return self._score_boost_pressure(value, context)
        else:
            return (None, f"No context scoring for {sensor}")

    # ------------------------------------------------------------------
    # Per-sensor context scorers
    # ------------------------------------------------------------------

    def _score_coolant(self, temp: float, ctx: Dict) -> Tuple[float, str]:
        """Coolant temperature scoring adjusted for ambient temp, speed, and load."""
        ambient = ctx.get("ambient_temp", self.DEFAULT_AMBIENT)
        speed = ctx.get("speed", 0.0)
        load = ctx.get("engine_load", 50.0)

        # Expected coolant temp formula:
        # - Base: 85°C ideal
        # - Hot ambient raises expected by ~0.4°C per °C above 25
        # - Low speed (traffic) raises expected (less airflow) by up to 5°C
        # - High load raises expected by ~0.05°C per % load
        expected = (
            85.0
            + max(0.0, (ambient - 25.0)) * 0.4
            + max(0.0, (1.0 - speed / 100.0)) * 5.0
            + load * 0.05
        )

        deviation = temp - expected

        if deviation > 20:
            return (10.0, f"Coolant {temp:.0f}°C is {deviation:.0f}°C above expected {expected:.0f}°C — CRITICAL overheating")
        elif deviation > 12:
            return (35.0, f"Coolant {temp:.0f}°C is {deviation:.0f}°C above expected {expected:.0f}°C — overheating")
        elif deviation > 6:
            return (65.0, f"Coolant {temp:.0f}°C is elevated for conditions (expected ~{expected:.0f}°C)")
        elif deviation < -15:
            return (80.0, f"Coolant {temp:.0f}°C — still warming up")
        elif deviation < -5:
            return (90.0, f"Coolant {temp:.0f}°C — slightly below operating temp")
        else:
            return (97.0, f"Coolant {temp:.0f}°C — normal for conditions (expected {expected:.0f}°C)")

    def _score_battery(self, voltage: float, ctx: Dict) -> Tuple[float, str]:
        """Battery voltage scoring adjusted for engine state and temperature."""
        rpm = ctx.get("rpm", 1000.0)
        ambient = ctx.get("ambient_temp", self.DEFAULT_AMBIENT)
        engine_running = rpm > 500

        if not engine_running:
            # Key-on engine-off: 12.4-12.8V is healthy, ≤11.5V is critical
            if voltage <= 11.5:
                return (10.0, f"Battery {voltage:.2f}V — critically discharged")
            elif voltage < 12.0:
                return (40.0, f"Battery {voltage:.2f}V — low charge")
            elif voltage < 12.4:
                return (70.0, f"Battery {voltage:.2f}V — partially discharged")
            else:
                return (95.0, f"Battery {voltage:.2f}V — fully charged")
        else:
            # Engine running: alternator should maintain 13.5-14.8V
            # Cold weather reduces charge acceptance
            temp_factor = max(0.0, (ambient - 20.0)) * 0.05  # hot reduces voltage slightly
            expected_min = 13.5 - temp_factor
            expected_max = 14.8

            if voltage < 12.0:
                return (5.0, f"Battery {voltage:.2f}V — alternator not charging (critical)")
            elif voltage < expected_min:
                return (45.0, f"Battery {voltage:.2f}V — below charging range (expected {expected_min:.1f}V+)")
            elif voltage > expected_max + 0.5:
                return (60.0, f"Battery {voltage:.2f}V — overcharging (expected ≤{expected_max}V)")
            elif voltage > expected_max:
                return (85.0, f"Battery {voltage:.2f}V — slightly high but within range")
            else:
                return (98.0, f"Battery {voltage:.2f}V — normal charging voltage")

    def _score_oil_temp(self, temp: float, ctx: Dict) -> Tuple[float, str]:
        """Oil temperature scoring — optimal depends on ambient and load."""
        ambient = ctx.get("ambient_temp", self.DEFAULT_AMBIENT)
        load = ctx.get("engine_load", 50.0)

        # Optimal oil temp: 90-115°C. Hot ambient pushes baseline up.
        optimal_min = 90.0 + max(0.0, (ambient - 25.0)) * 0.2
        optimal_max = 115.0 + max(0.0, (ambient - 25.0)) * 0.3

        if temp > 135.0:
            return (5.0, f"Oil {temp:.0f}°C — CRITICAL: oil degrading rapidly")
        elif temp > 125.0:
            return (25.0, f"Oil {temp:.0f}°C — dangerously hot")
        elif temp > optimal_max:
            return (60.0, f"Oil {temp:.0f}°C — above optimal range ({optimal_max:.0f}°C)")
        elif temp < 60.0:
            return (70.0, f"Oil {temp:.0f}°C — cold, engine not at operating temp")
        elif temp < optimal_min:
            return (85.0, f"Oil {temp:.0f}°C — warming up")
        else:
            return (96.0, f"Oil {temp:.0f}°C — optimal range")

    def _score_engine_load(self, load: float, ctx: Dict) -> Tuple[float, str]:
        """Engine load scoring — sustained high load is stressful in heat."""
        ambient = ctx.get("ambient_temp", self.DEFAULT_AMBIENT)
        speed = ctx.get("speed", 50.0)

        # High load on highway is normal; high load at low speed (traffic) is concerning
        # Hot ambient amplifies thermal stress
        thermal_multiplier = 1.0 + max(0.0, (ambient - 35.0)) * 0.02

        effective_load = load * thermal_multiplier

        if effective_load > 95:
            return (15.0, f"Engine load {load:.0f}% (thermal-adjusted: {effective_load:.0f}%) — extreme stress")
        elif effective_load > 85 and speed < 40:
            return (40.0, f"Engine load {load:.0f}% at low speed — excessive thermal stress in heat")
        elif effective_load > 80:
            return (65.0, f"Engine load {load:.0f}% — high but manageable")
        elif load > 60:
            return (85.0, f"Engine load {load:.0f}% — normal working load")
        else:
            return (97.0, f"Engine load {load:.0f}% — light operation")

    def _score_intake_temp(self, temp: float, ctx: Dict) -> Tuple[float, str]:
        """Intake air temperature — expected to track ambient closely."""
        ambient = ctx.get("ambient_temp", self.DEFAULT_AMBIENT)

        # Intake temp should be close to ambient (or slightly higher from heat soak)
        expected = ambient + 5.0  # 5°C above ambient is normal heat soak
        deviation = temp - expected

        if deviation > 20:
            return (30.0, f"Intake {temp:.0f}°C is {deviation:.0f}°C above ambient — heat soak issue")
        elif deviation > 10:
            return (65.0, f"Intake {temp:.0f}°C — elevated vs ambient {ambient:.0f}°C")
        elif temp > 70:
            return (40.0, f"Intake {temp:.0f}°C — critically hot air (power loss, knock risk)")
        else:
            return (95.0, f"Intake {temp:.0f}°C — normal relative to {ambient:.0f}°C ambient")

    def _score_boost_pressure(self, pressure: float, ctx: Dict) -> Tuple[float, str]:
        """Boost pressure scoring for turbocharged vehicles."""
        engine_load = ctx.get("engine_load", 50.0)

        # Expected boost is proportional to load for turbo engines
        # At idle/light load, near 0 boost is normal
        # Under full load, up to 200-250kPa is typical
        if engine_load < 20 and pressure > 50:
            return (50.0, f"Boost {pressure:.0f}kPa — unusually high at low load (possible leak/wastegate issue)")
        elif pressure > 280:
            return (20.0, f"Boost {pressure:.0f}kPa — dangerously high (turbo/engine risk)")
        elif pressure > 220:
            return (60.0, f"Boost {pressure:.0f}kPa — above typical maximum")
        else:
            return (95.0, f"Boost {pressure:.0f}kPa — normal for current conditions")

    # ------------------------------------------------------------------
    # Batch scoring
    # ------------------------------------------------------------------

    def score_all(
        self,
        telemetry: Dict[str, float],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Score all available sensors in the telemetry dict.

        Args:
            telemetry: Sensor readings {sensor_name: value}
            context:   Driving context (ambient_temp, speed, engine_load, rpm)
                       Falls back to telemetry values if not provided separately.

        Returns:
            {sensor_name: {"score": float, "explanation": str}}
        """
        if context is None:
            context = {}

        # Merge telemetry into context for self-referential scoring
        merged_ctx = {
            "ambient_temp": telemetry.get("ambient_temp", self.DEFAULT_AMBIENT),
            "speed": telemetry.get("speed", 0.0),
            "engine_load": telemetry.get("engine_load", 50.0),
            "rpm": telemetry.get("rpm", 0.0),
        }
        merged_ctx.update(context)  # explicit context overrides telemetry

        results = {}
        scoreable = {"coolant_temp", "battery_voltage", "oil_temp",
                     "engine_load", "intake_temp", "boost_pressure"}

        for sensor, value in telemetry.items():
            if sensor not in scoreable or value is None:
                continue
            score, explanation = self.score_sensor(sensor, value, merged_ctx)
            if score is not None:
                results[sensor] = {"score": score, "explanation": explanation}

        return results
