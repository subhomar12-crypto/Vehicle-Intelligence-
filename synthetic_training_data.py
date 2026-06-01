"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Synthetic Training Data

Synthetic Training Data Generator for LSTM Model Bootstrap
===========================================================
Generates realistic labeled training sequences based on known automotive failure patterns.

Failure Patterns Implemented:
- Battery failures: voltage drop patterns over 30-60 days
- Alternator failures: charging voltage instability
- Thermostat failures: coolant temp oscillation patterns
- Fuel system issues: fuel trim drift patterns

Physics-Based Models:
- Weibull distribution for time-to-failure
- Arrhenius equation for temperature-dependent degradation
- Exponential decay for capacity loss
"""

import numpy as np
from scipy import stats
from scipy.signal import savgol_filter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import json
import sqlite3
import os
import logging
import random
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# PHYSICS-BASED DEGRADATION MODELS
# =============================================================================

class PhysicsBasedDegradation:
    """
    Physics-based degradation models for realistic failure simulation.
    Uses established engineering models for component wear and failure.
    """

    @staticmethod
    def weibull_failure_probability(t: float, shape: float, scale: float) -> float:
        """
        Weibull distribution for time-to-failure probability.

        Args:
            t: Time (normalized 0-1 representing component life)
            shape: Shape parameter (β) - determines failure rate behavior
                   β < 1: decreasing failure rate (infant mortality)
                   β = 1: constant failure rate (random failures)
                   β > 1: increasing failure rate (wear-out failures)
            scale: Scale parameter (η) - characteristic life

        Returns:
            Cumulative failure probability
        """
        if t <= 0:
            return 0.0
        return 1 - np.exp(-((t / scale) ** shape))

    @staticmethod
    def arrhenius_degradation(temp_celsius: float, activation_energy: float = 0.7,
                               reference_temp: float = 25.0) -> float:
        """
        Arrhenius equation for temperature-dependent degradation rate.
        Higher temperatures accelerate chemical degradation.

        Args:
            temp_celsius: Operating temperature in Celsius
            activation_energy: Activation energy in eV (typical: 0.5-1.0 for electronics)
            reference_temp: Reference temperature in Celsius

        Returns:
            Acceleration factor relative to reference temperature
        """
        k_boltzmann = 8.617e-5  # eV/K
        temp_k = temp_celsius + 273.15
        ref_k = reference_temp + 273.15

        acceleration = np.exp((activation_energy / k_boltzmann) * (1/ref_k - 1/temp_k))
        return acceleration

    @staticmethod
    def exponential_capacity_loss(t: float, initial_capacity: float,
                                   decay_rate: float) -> float:
        """
        Exponential decay model for capacity loss (e.g., battery capacity).

        Args:
            t: Time (normalized 0-1)
            initial_capacity: Starting capacity value
            decay_rate: Rate of exponential decay

        Returns:
            Remaining capacity
        """
        return initial_capacity * np.exp(-decay_rate * t)

    @staticmethod
    def cyclic_fatigue(cycles: int, fatigue_limit: int,
                       stress_amplitude: float) -> float:
        """
        S-N curve based fatigue damage accumulation.

        Args:
            cycles: Number of stress cycles
            fatigue_limit: Maximum cycles to failure at given stress
            stress_amplitude: Normalized stress level (0-1)

        Returns:
            Damage accumulation (0-1, where 1 = failure)
        """
        # Modified Basquin equation
        damage = (cycles / fatigue_limit) * (stress_amplitude ** 3)
        return min(damage, 1.0)


# =============================================================================
# FAILURE PATTERN GENERATORS
# =============================================================================

@dataclass
class SyntheticSequence:
    """Represents a synthetic training sequence."""
    timestamps: List[datetime]
    sensor_data: Dict[str, List[float]]
    failure_type: str
    failure_occurred: bool
    days_to_failure: Optional[int]
    pattern_metadata: Dict[str, Any] = field(default_factory=dict)
    vehicle_id: str = ""
    sequence_id: str = ""


class BatteryFailureGenerator:
    """
    Generates realistic battery failure patterns.

    Battery failure characteristics:
    - Gradual voltage drop from 12.6V (healthy) to <12V (failing)
    - Increased internal resistance over time
    - Cold cranking performance degradation
    - Temperature sensitivity increases with age
    """

    # Physical constants for lead-acid battery
    HEALTHY_VOLTAGE = 12.6  # Fully charged resting voltage
    CRITICAL_VOLTAGE = 11.8  # Below this, starting problems
    DEAD_VOLTAGE = 10.5  # Battery considered dead

    NORMAL_VOLTAGE_RANGE = (12.4, 12.8)  # Normal operating range
    CRANKING_DROP = (0.5, 1.5)  # Voltage drop during cranking (healthy)

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.RandomState(seed)
        self.physics = PhysicsBasedDegradation()

    def generate_healthy_sequence(self, days: int = 60,
                                   readings_per_day: int = 10) -> SyntheticSequence:
        """Generate a healthy battery sequence (no failure)."""
        timestamps = []
        voltages = []

        base_voltage = self.rng.uniform(12.5, 12.7)
        start_time = datetime.now() - timedelta(days=days)

        for day in range(days):
            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                # Normal daily variation
                hour_variation = 0.1 * np.sin(2 * np.pi * reading / readings_per_day)
                noise = self.rng.normal(0, 0.02)

                voltage = base_voltage + hour_variation + noise
                voltage = np.clip(voltage, 12.3, 12.9)
                voltages.append(voltage)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={'battery_voltage': voltages},
            failure_type='none',
            failure_occurred=False,
            days_to_failure=None,
            pattern_metadata={'pattern': 'healthy', 'degradation_rate': 0},
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"healthy-{self.rng.random()}".encode()).hexdigest()[:8]
        )

    def generate_failure_sequence(self, days_to_failure: int = 45,
                                   readings_per_day: int = 10,
                                   degradation_type: str = 'gradual') -> SyntheticSequence:
        """
        Generate a battery failure sequence.

        Args:
            days_to_failure: Days until battery fails
            readings_per_day: Sensor readings per day
            degradation_type: 'gradual', 'sudden', or 'cyclic'
        """
        total_days = days_to_failure + 5  # Include some post-failure readings
        timestamps = []
        voltages = []

        start_voltage = self.rng.uniform(12.5, 12.7)
        start_time = datetime.now() - timedelta(days=total_days)

        # Weibull shape for battery failure (wear-out pattern)
        weibull_shape = 2.5  # Increasing failure rate
        weibull_scale = 0.8

        for day in range(total_days):
            progress = day / days_to_failure  # 0 to 1+

            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                # Calculate degradation based on physics
                if degradation_type == 'gradual':
                    # Exponential capacity loss
                    capacity_factor = self.physics.exponential_capacity_loss(
                        min(progress, 1.2), 1.0, decay_rate=1.5
                    )
                    degraded_voltage = start_voltage * capacity_factor

                elif degradation_type == 'sudden':
                    # Sudden failure near end
                    if progress < 0.8:
                        degraded_voltage = start_voltage - progress * 0.3
                    else:
                        drop_factor = (progress - 0.8) / 0.2
                        degraded_voltage = (start_voltage - 0.3) - drop_factor * 2.0

                elif degradation_type == 'cyclic':
                    # Intermittent problems before failure
                    base_degradation = progress * 0.8
                    if progress > 0.5 and self.rng.random() < 0.3:
                        # Random voltage drops
                        base_degradation += self.rng.uniform(0.5, 1.5)
                    degraded_voltage = start_voltage - base_degradation

                else:
                    degraded_voltage = start_voltage

                # Add realistic noise (increases with degradation)
                noise_amplitude = 0.02 + 0.1 * min(progress, 1.0)
                noise = self.rng.normal(0, noise_amplitude)

                # Daily temperature effect (colder = lower voltage)
                temp_effect = 0.05 * np.sin(2 * np.pi * reading / readings_per_day)

                voltage = degraded_voltage + noise + temp_effect
                voltage = np.clip(voltage, self.DEAD_VOLTAGE, 13.0)
                voltages.append(voltage)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={'battery_voltage': voltages},
            failure_type='battery_failure',
            failure_occurred=True,
            days_to_failure=days_to_failure,
            pattern_metadata={
                'pattern': degradation_type,
                'start_voltage': start_voltage,
                'weibull_shape': weibull_shape
            },
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"battery-{self.rng.random()}".encode()).hexdigest()[:8]
        )


class AlternatorFailureGenerator:
    """
    Generates realistic alternator failure patterns.

    Alternator failure characteristics:
    - Charging voltage instability (should be 13.5-14.5V)
    - Erratic voltage swings before failure
    - Diode failures cause AC ripple
    - Bearing wear causes intermittent charging
    """

    NORMAL_CHARGING = (13.8, 14.4)  # Normal charging voltage range
    LOW_CHARGING = 13.2  # Undercharging threshold
    HIGH_CHARGING = 15.0  # Overcharging threshold

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.RandomState(seed)
        self.physics = PhysicsBasedDegradation()

    def generate_healthy_sequence(self, days: int = 60,
                                   readings_per_day: int = 10) -> SyntheticSequence:
        """Generate healthy alternator sequence."""
        timestamps = []
        voltages = []

        base_charging = self.rng.uniform(13.9, 14.2)
        start_time = datetime.now() - timedelta(days=days)

        for day in range(days):
            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                # RPM-dependent variation (simulated)
                rpm_factor = 0.2 * np.sin(2 * np.pi * reading / readings_per_day)
                load_factor = self.rng.uniform(-0.1, 0.1)
                noise = self.rng.normal(0, 0.03)

                voltage = base_charging + rpm_factor + load_factor + noise
                voltage = np.clip(voltage, 13.6, 14.6)
                voltages.append(voltage)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={'charging_voltage': voltages},
            failure_type='none',
            failure_occurred=False,
            days_to_failure=None,
            pattern_metadata={'pattern': 'healthy'},
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"alt-healthy-{self.rng.random()}".encode()).hexdigest()[:8]
        )

    def generate_failure_sequence(self, days_to_failure: int = 30,
                                   readings_per_day: int = 10,
                                   failure_mode: str = 'voltage_regulator') -> SyntheticSequence:
        """
        Generate alternator failure sequence.

        Args:
            days_to_failure: Days until alternator fails
            failure_mode: 'voltage_regulator', 'diode', 'bearing', or 'brush'
        """
        total_days = days_to_failure + 3
        timestamps = []
        voltages = []

        start_time = datetime.now() - timedelta(days=total_days)
        base_charging = self.rng.uniform(13.9, 14.2)

        for day in range(total_days):
            progress = day / days_to_failure

            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                if failure_mode == 'voltage_regulator':
                    # Voltage regulator failure: erratic high/low voltages
                    if progress < 0.5:
                        instability = 0.3 * progress
                    else:
                        instability = 0.3 + 1.5 * (progress - 0.5)

                    swing = self.rng.normal(0, instability)
                    voltage = base_charging + swing

                    # Occasional spikes
                    if progress > 0.6 and self.rng.random() < 0.15:
                        voltage += self.rng.choice([-2, 2]) * self.rng.random()

                elif failure_mode == 'diode':
                    # Diode failure: reduced charging + AC ripple
                    capacity_loss = self.physics.exponential_capacity_loss(
                        min(progress, 1.1), 1.0, decay_rate=0.8
                    )
                    base = base_charging * capacity_loss

                    # AC ripple increases with failure
                    ripple = 0.5 * progress * np.sin(reading * 6)  # High frequency ripple
                    noise = self.rng.normal(0, 0.05)
                    voltage = base + ripple + noise

                elif failure_mode == 'bearing':
                    # Bearing failure: intermittent charging drops
                    voltage = base_charging

                    # Random complete charging drops (bearing seizing)
                    drop_probability = 0.1 + 0.4 * progress
                    if self.rng.random() < drop_probability:
                        drop_duration = self.rng.randint(1, 4)
                        voltage = self.rng.uniform(12.0, 12.8)  # Battery voltage only

                    voltage += self.rng.normal(0, 0.1)

                elif failure_mode == 'brush':
                    # Brush wear: gradually decreasing charging
                    wear_factor = 1.0 - 0.3 * min(progress, 1.2)
                    voltage = base_charging * wear_factor

                    # Intermittent contact as brushes wear
                    if progress > 0.7 and self.rng.random() < 0.2:
                        voltage *= self.rng.uniform(0.7, 0.9)

                    voltage += self.rng.normal(0, 0.04)

                else:
                    voltage = base_charging

                voltage = np.clip(voltage, 10.5, 16.0)
                voltages.append(voltage)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={'charging_voltage': voltages},
            failure_type='alternator_failure',
            failure_occurred=True,
            days_to_failure=days_to_failure,
            pattern_metadata={
                'pattern': failure_mode,
                'base_charging': base_charging
            },
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"alt-{failure_mode}-{self.rng.random()}".encode()).hexdigest()[:8]
        )


class ThermostatFailureGenerator:
    """
    Generates realistic thermostat failure patterns.

    Thermostat failure characteristics:
    - Stuck open: engine runs too cold (160-175°F instead of 195-220°F)
    - Stuck closed: engine overheats rapidly
    - Intermittent: oscillating temperatures
    - Partial opening: slow warmup, unstable temps
    """

    NORMAL_OPERATING_TEMP = (195, 220)  # °F
    COLD_ENGINE_TEMP = 70  # °F (ambient)
    OVERHEAT_THRESHOLD = 250  # °F

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.RandomState(seed)
        self.physics = PhysicsBasedDegradation()

    def generate_healthy_sequence(self, days: int = 60,
                                   readings_per_day: int = 10) -> SyntheticSequence:
        """Generate healthy thermostat sequence."""
        timestamps = []
        temps = []

        target_temp = self.rng.uniform(200, 210)
        start_time = datetime.now() - timedelta(days=days)

        for day in range(days):
            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                # Normal operating variation
                load_variation = self.rng.uniform(-5, 8)  # Higher temps under load
                ambient_effect = 3 * np.sin(2 * np.pi * day / 30)  # Seasonal
                noise = self.rng.normal(0, 2)

                temp = target_temp + load_variation + ambient_effect + noise
                temp = np.clip(temp, 190, 225)
                temps.append(temp)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={'coolant_temp': temps},
            failure_type='none',
            failure_occurred=False,
            days_to_failure=None,
            pattern_metadata={'pattern': 'healthy', 'target_temp': target_temp},
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"thermo-healthy-{self.rng.random()}".encode()).hexdigest()[:8]
        )

    def generate_failure_sequence(self, days_to_failure: int = 21,
                                   readings_per_day: int = 10,
                                   failure_mode: str = 'stuck_open') -> SyntheticSequence:
        """
        Generate thermostat failure sequence.

        Args:
            days_to_failure: Days until thermostat fails
            failure_mode: 'stuck_open', 'stuck_closed', 'intermittent', or 'partial'
        """
        total_days = days_to_failure + 5
        timestamps = []
        temps = []

        start_time = datetime.now() - timedelta(days=total_days)
        normal_temp = self.rng.uniform(200, 210)

        for day in range(total_days):
            progress = day / days_to_failure

            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                if failure_mode == 'stuck_open':
                    # Thermostat stuck open: engine runs cold
                    # Gradual transition from normal to too-cold
                    if progress < 0.3:
                        temp = normal_temp + self.rng.normal(0, 3)
                    else:
                        cold_target = 160 + (normal_temp - 160) * max(0, 1 - progress)
                        temp = cold_target + self.rng.normal(0, 5)

                        # Engine never quite reaches normal temp
                        if progress > 0.8:
                            temp = min(temp, 175)

                elif failure_mode == 'stuck_closed':
                    # Thermostat stuck closed: overheating
                    if progress < 0.5:
                        # Gradual increase in peak temps
                        overheat_tendency = progress * 20
                        temp = normal_temp + overheat_tendency + self.rng.normal(0, 3)
                    else:
                        # Full overheat condition
                        temp = 230 + (progress - 0.5) * 40
                        temp += self.rng.normal(0, 5)
                        temp = min(temp, 270)  # Cap before engine damage

                elif failure_mode == 'intermittent':
                    # Intermittent failure: oscillating temperatures
                    base_temp = normal_temp

                    # Increasing oscillation amplitude over time
                    oscillation_amp = 10 + 30 * progress
                    oscillation = oscillation_amp * np.sin(reading * 0.5 + day * 0.3)

                    # Random sticking events
                    if progress > 0.4 and self.rng.random() < 0.25:
                        if self.rng.random() < 0.5:
                            oscillation += 30  # Stuck closed moment
                        else:
                            oscillation -= 30  # Stuck open moment

                    temp = base_temp + oscillation + self.rng.normal(0, 4)

                elif failure_mode == 'partial':
                    # Partial opening: slow warmup, never quite right
                    # Simulate slow warmup on each "drive cycle"
                    cycle_position = reading / readings_per_day

                    # Healthy warmup reaches target quickly
                    healthy_warmup = normal_temp * (1 - 0.5 * np.exp(-5 * cycle_position))

                    # Failing warmup is slower and lower
                    failure_factor = 0.85 - 0.15 * progress
                    slow_warmup = healthy_warmup * failure_factor

                    temp = slow_warmup + self.rng.normal(0, 3)

                else:
                    temp = normal_temp

                temp = np.clip(temp, 50, 280)
                temps.append(temp)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={'coolant_temp': temps},
            failure_type='thermostat_failure',
            failure_occurred=True,
            days_to_failure=days_to_failure,
            pattern_metadata={
                'pattern': failure_mode,
                'normal_temp': normal_temp
            },
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"thermo-{failure_mode}-{self.rng.random()}".encode()).hexdigest()[:8]
        )


class FuelSystemFailureGenerator:
    """
    Generates realistic fuel system failure patterns.

    Fuel system characteristics:
    - Long Term Fuel Trim (LTFT): learned compensation for fuel delivery
    - Normal LTFT: ±5% (some allow ±10%)
    - Failing: gradual drift beyond ±10-15%
    - Causes: O2 sensor degradation, fuel injector clogging, vacuum leaks
    """

    NORMAL_LTFT_RANGE = (-5, 5)  # Percent
    WARNING_THRESHOLD = 10  # Percent
    CRITICAL_THRESHOLD = 20  # Percent (likely CEL)

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.RandomState(seed)
        self.physics = PhysicsBasedDegradation()

    def generate_healthy_sequence(self, days: int = 60,
                                   readings_per_day: int = 10) -> SyntheticSequence:
        """Generate healthy fuel system sequence."""
        timestamps = []
        ltft_values = []
        stft_values = []

        base_ltft = self.rng.uniform(-2, 2)
        start_time = datetime.now() - timedelta(days=days)

        for day in range(days):
            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                # LTFT is fairly stable (learned value)
                ltft = base_ltft + self.rng.normal(0, 0.5)
                ltft = np.clip(ltft, -5, 5)
                ltft_values.append(ltft)

                # STFT varies more (real-time correction)
                stft = self.rng.normal(0, 3)
                stft = np.clip(stft, -10, 10)
                stft_values.append(stft)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={
                'long_term_fuel_trim_bank1': ltft_values,
                'short_term_fuel_trim_bank1': stft_values
            },
            failure_type='none',
            failure_occurred=False,
            days_to_failure=None,
            pattern_metadata={'pattern': 'healthy', 'base_ltft': base_ltft},
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"fuel-healthy-{self.rng.random()}".encode()).hexdigest()[:8]
        )

    def generate_failure_sequence(self, days_to_failure: int = 45,
                                   readings_per_day: int = 10,
                                   failure_mode: str = 'lean_drift') -> SyntheticSequence:
        """
        Generate fuel system failure sequence.

        Args:
            days_to_failure: Days until fuel trim exceeds limits
            failure_mode: 'lean_drift', 'rich_drift', 'oscillating', or 'intermittent'
        """
        total_days = days_to_failure + 5
        timestamps = []
        ltft_values = []
        stft_values = []

        start_time = datetime.now() - timedelta(days=total_days)
        base_ltft = self.rng.uniform(-1, 1)

        for day in range(total_days):
            progress = day / days_to_failure

            for reading in range(readings_per_day):
                t = start_time + timedelta(days=day, hours=reading * 2.4)
                timestamps.append(t)

                if failure_mode == 'lean_drift':
                    # Gradual lean drift (positive LTFT)
                    # Common cause: vacuum leak, weak fuel pump, clogged injectors
                    drift = 15 * self.physics.weibull_failure_probability(
                        progress, shape=2.0, scale=0.6
                    )
                    ltft = base_ltft + drift + self.rng.normal(0, 0.8)

                    # STFT compensates opposite direction initially
                    stft = -drift * 0.3 + self.rng.normal(0, 2)

                elif failure_mode == 'rich_drift':
                    # Gradual rich drift (negative LTFT)
                    # Common cause: leaking injector, stuck-open EVAP purge
                    drift = -18 * self.physics.exponential_capacity_loss(
                        progress, 1.0, decay_rate=1.2
                    )
                    drift = -(1.0 - abs(drift)) * 18  # Convert to negative drift
                    ltft = base_ltft + drift + self.rng.normal(0, 0.8)

                    stft = -drift * 0.2 + self.rng.normal(0, 2)

                elif failure_mode == 'oscillating':
                    # Oscillating fuel trim (sensor issues)
                    # Common cause: failing O2 sensor
                    oscillation_amplitude = 5 + 10 * progress
                    frequency = 0.5 + 0.3 * progress  # Increasing frequency

                    oscillation = oscillation_amplitude * np.sin(
                        reading * frequency + day * 0.2
                    )
                    ltft = base_ltft + oscillation + self.rng.normal(0, 1)

                    # STFT becomes erratic too
                    stft = 8 * np.sin(reading * frequency * 2) + self.rng.normal(0, 3)

                elif failure_mode == 'intermittent':
                    # Intermittent spikes (electrical issues)
                    ltft = base_ltft + self.rng.normal(0, 0.5)
                    stft = self.rng.normal(0, 2)

                    # Random intermittent spikes that get worse
                    spike_prob = 0.05 + 0.25 * progress
                    if self.rng.random() < spike_prob:
                        spike = self.rng.choice([-15, 15]) + self.rng.normal(0, 5)
                        ltft += spike
                        stft += spike * 0.5

                else:
                    ltft = base_ltft
                    stft = 0

                ltft = np.clip(ltft, -30, 30)
                stft = np.clip(stft, -25, 25)

                ltft_values.append(ltft)
                stft_values.append(stft)

        return SyntheticSequence(
            timestamps=timestamps,
            sensor_data={
                'long_term_fuel_trim_bank1': ltft_values,
                'short_term_fuel_trim_bank1': stft_values
            },
            failure_type='fuel_system_failure',
            failure_occurred=True,
            days_to_failure=days_to_failure,
            pattern_metadata={
                'pattern': failure_mode,
                'base_ltft': base_ltft
            },
            vehicle_id=f"SYN-{self.rng.randint(1000, 9999)}",
            sequence_id=hashlib.md5(f"fuel-{failure_mode}-{self.rng.random()}".encode()).hexdigest()[:8]
        )


# =============================================================================
# FLEET-WIDE PATTERN SHARING
# =============================================================================

class FleetPatternDatabase:
    """
    Fleet-wide pattern sharing database.
    Enables learning from failures across the entire fleet.
    """

    def __init__(self, db_path: str = "fleet_patterns.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the fleet pattern database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Failure patterns table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS failure_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    failure_type TEXT NOT NULL,
                    pattern_signature TEXT NOT NULL,
                    sensor_correlations TEXT,
                    days_before_failure INTEGER,
                    confidence_score REAL,
                    occurrence_count INTEGER DEFAULT 1,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    vehicle_types TEXT,
                    metadata TEXT
                )
            ''')

            # Fleet vehicles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fleet_vehicles (
                    vehicle_id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    vehicle_type TEXT,
                    make TEXT,
                    model TEXT,
                    year INTEGER,
                    mileage INTEGER,
                    last_updated TIMESTAMP
                )
            ''')

            # Pattern occurrences table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pattern_occurrences (
                    occurrence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT,
                    vehicle_id TEXT,
                    detected_at TIMESTAMP,
                    actual_failure_date TIMESTAMP,
                    prediction_accuracy REAL,
                    FOREIGN KEY (pattern_id) REFERENCES failure_patterns(pattern_id),
                    FOREIGN KEY (vehicle_id) REFERENCES fleet_vehicles(vehicle_id)
                )
            ''')

            # Aggregated insights table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fleet_insights (
                    insight_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    insight_type TEXT,
                    affected_vehicle_types TEXT,
                    pattern_ids TEXT,
                    recommendation TEXT,
                    severity TEXT,
                    created_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')

            conn.commit()

    def register_pattern(self, sequence: SyntheticSequence,
                         pattern_signature: Dict[str, Any]) -> str:
        """Register a new failure pattern discovered from a sequence."""
        pattern_id = hashlib.md5(
            json.dumps(pattern_signature, sort_keys=True).encode()
        ).hexdigest()[:16]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if pattern exists
            cursor.execute(
                'SELECT occurrence_count FROM failure_patterns WHERE pattern_id = ?',
                (pattern_id,)
            )
            existing = cursor.fetchone()

            now = datetime.now().isoformat()

            if existing:
                # Update existing pattern
                cursor.execute('''
                    UPDATE failure_patterns
                    SET occurrence_count = occurrence_count + 1,
                        last_seen = ?,
                        confidence_score = MIN(confidence_score + 0.05, 1.0)
                    WHERE pattern_id = ?
                ''', (now, pattern_id))
            else:
                # Insert new pattern
                cursor.execute('''
                    INSERT INTO failure_patterns
                    (pattern_id, failure_type, pattern_signature, days_before_failure,
                     confidence_score, first_seen, last_seen, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pattern_id,
                    sequence.failure_type,
                    json.dumps(pattern_signature),
                    sequence.days_to_failure,
                    0.7,  # Initial confidence
                    now,
                    now,
                    json.dumps(sequence.pattern_metadata)
                ))

            conn.commit()

        return pattern_id

    def find_similar_patterns(self, sensor_data: Dict[str, List[float]],
                               limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar patterns in the fleet database."""
        # Calculate pattern signature from current data
        signature = self._calculate_signature(sensor_data)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT pattern_id, failure_type, pattern_signature,
                       days_before_failure, confidence_score, occurrence_count
                FROM failure_patterns
                ORDER BY confidence_score DESC, occurrence_count DESC
                LIMIT ?
            ''', (limit * 3,))  # Get more for filtering

            results = []
            for row in cursor.fetchall():
                stored_signature = json.loads(row[2])
                similarity = self._compare_signatures(signature, stored_signature)

                if similarity > 0.6:  # Minimum similarity threshold
                    results.append({
                        'pattern_id': row[0],
                        'failure_type': row[1],
                        'days_before_failure': row[3],
                        'confidence': row[4],
                        'occurrence_count': row[5],
                        'similarity': similarity
                    })

            # Sort by combined score
            results.sort(key=lambda x: x['similarity'] * x['confidence'], reverse=True)
            return results[:limit]

    def _calculate_signature(self, sensor_data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Calculate a pattern signature from sensor data."""
        signature = {}

        for sensor, values in sensor_data.items():
            if len(values) < 10:
                continue

            arr = np.array(values)

            # Statistical features
            signature[f'{sensor}_mean'] = float(np.mean(arr))
            signature[f'{sensor}_std'] = float(np.std(arr))
            signature[f'{sensor}_trend'] = float(np.polyfit(range(len(arr)), arr, 1)[0])

            # Detect volatility
            diff = np.diff(arr)
            signature[f'{sensor}_volatility'] = float(np.std(diff))

            # Detect oscillation
            fft = np.fft.fft(arr - np.mean(arr))
            signature[f'{sensor}_dominant_freq'] = float(np.argmax(np.abs(fft[1:len(fft)//2])))

        return signature

    def _compare_signatures(self, sig1: Dict[str, Any],
                            sig2: Dict[str, Any]) -> float:
        """Compare two pattern signatures for similarity."""
        common_keys = set(sig1.keys()) & set(sig2.keys())

        if not common_keys:
            return 0.0

        similarities = []
        for key in common_keys:
            v1, v2 = sig1[key], sig2[key]

            if v1 == 0 and v2 == 0:
                similarities.append(1.0)
            elif v1 == 0 or v2 == 0:
                similarities.append(0.0)
            else:
                # Relative similarity
                ratio = min(v1, v2) / max(abs(v1), abs(v2))
                similarities.append(max(0, ratio))

        return float(np.mean(similarities))

    def get_fleet_insights(self, vehicle_type: Optional[str] = None) -> List[Dict]:
        """Get aggregated insights for the fleet."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get most common failure patterns
            cursor.execute('''
                SELECT failure_type, COUNT(*) as count,
                       AVG(days_before_failure) as avg_days,
                       AVG(confidence_score) as avg_confidence
                FROM failure_patterns
                GROUP BY failure_type
                ORDER BY count DESC
            ''')

            insights = []
            for row in cursor.fetchall():
                insights.append({
                    'failure_type': row[0],
                    'total_patterns': row[1],
                    'avg_days_warning': row[2],
                    'avg_confidence': row[3]
                })

            return insights


# =============================================================================
# SYNTHETIC DATA TRAINING MANAGER
# =============================================================================

class SyntheticTrainingDataManager:
    """
    Manages synthetic training data generation and LSTM bootstrap training.
    """

    def __init__(self, output_dir: str = "synthetic_training_data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Initialize generators
        self.battery_gen = BatteryFailureGenerator()
        self.alternator_gen = AlternatorFailureGenerator()
        self.thermostat_gen = ThermostatFailureGenerator()
        self.fuel_gen = FuelSystemFailureGenerator()

        # Fleet pattern database
        self.fleet_db = FleetPatternDatabase(
            os.path.join(output_dir, "fleet_patterns.db")
        )

        # Physics model
        self.physics = PhysicsBasedDegradation()

        self.generated_sequences: List[SyntheticSequence] = []

    def generate_training_dataset(self,
                                    samples_per_failure: int = 50,
                                    healthy_samples: int = 100) -> Dict[str, Any]:
        """
        Generate a complete training dataset with all failure types.

        Args:
            samples_per_failure: Number of failure sequences per type
            healthy_samples: Number of healthy sequences

        Returns:
            Dictionary with training statistics
        """
        logger.info("Generating synthetic training dataset...")

        all_sequences = []
        stats = {
            'total_sequences': 0,
            'failure_sequences': 0,
            'healthy_sequences': 0,
            'by_type': {}
        }

        # Generate battery failures
        logger.info("Generating battery failure patterns...")
        for i in range(samples_per_failure):
            days = np.random.randint(30, 60)
            degradation = np.random.choice(['gradual', 'sudden', 'cyclic'])
            seq = self.battery_gen.generate_failure_sequence(
                days_to_failure=days, degradation_type=degradation
            )
            all_sequences.append(seq)
            self.fleet_db.register_pattern(seq, {'type': 'battery', 'mode': degradation})

        for i in range(healthy_samples // 4):
            seq = self.battery_gen.generate_healthy_sequence()
            all_sequences.append(seq)

        stats['by_type']['battery'] = samples_per_failure

        # Generate alternator failures
        logger.info("Generating alternator failure patterns...")
        for i in range(samples_per_failure):
            days = np.random.randint(20, 45)
            mode = np.random.choice(['voltage_regulator', 'diode', 'bearing', 'brush'])
            seq = self.alternator_gen.generate_failure_sequence(
                days_to_failure=days, failure_mode=mode
            )
            all_sequences.append(seq)
            self.fleet_db.register_pattern(seq, {'type': 'alternator', 'mode': mode})

        for i in range(healthy_samples // 4):
            seq = self.alternator_gen.generate_healthy_sequence()
            all_sequences.append(seq)

        stats['by_type']['alternator'] = samples_per_failure

        # Generate thermostat failures
        logger.info("Generating thermostat failure patterns...")
        for i in range(samples_per_failure):
            days = np.random.randint(14, 35)
            mode = np.random.choice(['stuck_open', 'stuck_closed', 'intermittent', 'partial'])
            seq = self.thermostat_gen.generate_failure_sequence(
                days_to_failure=days, failure_mode=mode
            )
            all_sequences.append(seq)
            self.fleet_db.register_pattern(seq, {'type': 'thermostat', 'mode': mode})

        for i in range(healthy_samples // 4):
            seq = self.thermostat_gen.generate_healthy_sequence()
            all_sequences.append(seq)

        stats['by_type']['thermostat'] = samples_per_failure

        # Generate fuel system failures
        logger.info("Generating fuel system failure patterns...")
        for i in range(samples_per_failure):
            days = np.random.randint(30, 60)
            mode = np.random.choice(['lean_drift', 'rich_drift', 'oscillating', 'intermittent'])
            seq = self.fuel_gen.generate_failure_sequence(
                days_to_failure=days, failure_mode=mode
            )
            all_sequences.append(seq)
            self.fleet_db.register_pattern(seq, {'type': 'fuel_system', 'mode': mode})

        for i in range(healthy_samples // 4):
            seq = self.fuel_gen.generate_healthy_sequence()
            all_sequences.append(seq)

        stats['by_type']['fuel_system'] = samples_per_failure

        self.generated_sequences = all_sequences

        stats['total_sequences'] = len(all_sequences)
        stats['failure_sequences'] = samples_per_failure * 4
        stats['healthy_sequences'] = healthy_samples

        logger.info(f"Generated {stats['total_sequences']} total sequences")
        return stats

    def prepare_lstm_training_data(self, sequence_length: int = 30) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Prepare training data for LSTM model.

        Args:
            sequence_length: Number of timesteps per sequence

        Returns:
            Tuple of (X_train, y_dict) where y_dict contains multiple targets
        """
        if not self.generated_sequences:
            self.generate_training_dataset()

        # Define all sensors we're tracking
        all_sensors = [
            'battery_voltage', 'charging_voltage', 'coolant_temp',
            'long_term_fuel_trim_bank1', 'short_term_fuel_trim_bank1'
        ]

        # Failure type mapping
        failure_types = {
            'none': 0,
            'battery_failure': 1,
            'alternator_failure': 2,
            'thermostat_failure': 3,
            'fuel_system_failure': 4
        }

        X_sequences = []
        y_failure_prob = []
        y_failure_type = []
        y_days_to_failure = []

        for seq in self.generated_sequences:
            # Build feature matrix for this sequence
            n_samples = len(seq.timestamps)

            if n_samples < sequence_length:
                continue

            # Create feature array
            features = np.zeros((n_samples, len(all_sensors)))

            for i, sensor in enumerate(all_sensors):
                if sensor in seq.sensor_data:
                    values = seq.sensor_data[sensor]
                    features[:len(values), i] = values
                else:
                    # Fill with typical values for missing sensors
                    if sensor == 'battery_voltage':
                        features[:, i] = 12.6
                    elif sensor == 'charging_voltage':
                        features[:, i] = 14.0
                    elif sensor == 'coolant_temp':
                        features[:, i] = 200
                    else:
                        features[:, i] = 0

            # Create sliding windows
            for start in range(0, n_samples - sequence_length, sequence_length // 2):
                end = start + sequence_length
                X_sequences.append(features[start:end])

                y_failure_prob.append(1.0 if seq.failure_occurred else 0.0)
                y_failure_type.append(failure_types.get(seq.failure_type, 0))

                # Days to failure (negative for healthy)
                if seq.days_to_failure:
                    # Estimate days remaining at this point in sequence
                    progress = end / n_samples
                    days_remaining = max(0, seq.days_to_failure * (1 - progress))
                    y_days_to_failure.append(days_remaining)
                else:
                    y_days_to_failure.append(-1)  # No failure expected

        X = np.array(X_sequences)

        # Normalize X
        for i in range(X.shape[2]):
            mean = np.mean(X[:, :, i])
            std = np.std(X[:, :, i])
            if std > 0:
                X[:, :, i] = (X[:, :, i] - mean) / std

        y = {
            'failure_probability': np.array(y_failure_prob),
            'failure_type': np.array(y_failure_type),
            'days_to_failure': np.array(y_days_to_failure)
        }

        logger.info(f"Prepared {len(X)} training sequences of shape {X.shape}")
        return X, y

    def save_training_data(self, filename: str = "synthetic_training_data.npz"):
        """Save prepared training data to file."""
        X, y = self.prepare_lstm_training_data()

        filepath = os.path.join(self.output_dir, filename)
        np.savez(
            filepath,
            X=X,
            y_failure_prob=y['failure_probability'],
            y_failure_type=y['failure_type'],
            y_days_to_failure=y['days_to_failure']
        )

        logger.info(f"Saved training data to {filepath}")
        return filepath

    def export_sequences_json(self, filename: str = "sequences.json"):
        """Export generated sequences to JSON for inspection."""
        export_data = []

        for seq in self.generated_sequences:
            export_data.append({
                'sequence_id': seq.sequence_id,
                'vehicle_id': seq.vehicle_id,
                'failure_type': seq.failure_type,
                'failure_occurred': seq.failure_occurred,
                'days_to_failure': seq.days_to_failure,
                'pattern_metadata': seq.pattern_metadata,
                'sensor_data': {k: v[:10] for k, v in seq.sensor_data.items()},  # First 10 samples
                'total_samples': len(seq.timestamps)
            })

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Exported {len(export_data)} sequences to {filepath}")
        return filepath


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def generate_and_train(samples_per_failure: int = 50,
                        healthy_samples: int = 100) -> Dict[str, Any]:
    """
    Main entry point: Generate synthetic data and prepare for LSTM training.

    Args:
        samples_per_failure: Number of failure sequences per failure type
        healthy_samples: Number of healthy (no failure) sequences

    Returns:
        Dictionary with generation statistics and file paths
    """
    manager = SyntheticTrainingDataManager()

    # Generate training dataset
    stats = manager.generate_training_dataset(
        samples_per_failure=samples_per_failure,
        healthy_samples=healthy_samples
    )

    # Save training data
    npz_path = manager.save_training_data()

    # Export sequences for inspection
    json_path = manager.export_sequences_json()

    # Get fleet insights
    fleet_insights = manager.fleet_db.get_fleet_insights()

    return {
        'statistics': stats,
        'training_data_path': npz_path,
        'sequences_json_path': json_path,
        'fleet_insights': fleet_insights,
        'total_patterns_registered': len(manager.generated_sequences)
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("SYNTHETIC TRAINING DATA GENERATOR")
    print("=" * 60)

    result = generate_and_train(samples_per_failure=50, healthy_samples=100)

    print("\nGeneration Statistics:")
    print(f"  Total sequences: {result['statistics']['total_sequences']}")
    print(f"  Failure sequences: {result['statistics']['failure_sequences']}")
    print(f"  Healthy sequences: {result['statistics']['healthy_sequences']}")

    print("\nBy failure type:")
    for ftype, count in result['statistics']['by_type'].items():
        print(f"  {ftype}: {count}")

    print(f"\nTraining data saved to: {result['training_data_path']}")
    print(f"Sequences JSON saved to: {result['sequences_json_path']}")

    print("\nFleet Insights:")
    for insight in result['fleet_insights']:
        print(f"  {insight['failure_type']}: {insight['total_patterns']} patterns, "
              f"avg {insight['avg_days_warning']:.1f} days warning")
