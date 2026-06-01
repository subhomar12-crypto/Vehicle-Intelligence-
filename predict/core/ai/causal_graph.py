"""
Causal Graph for root cause analysis.

Uses a directed acyclic graph (DAG) of vehicle system relationships
to identify root causes from symptoms.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class CausalGraph:
    """
    Root cause analysis using causal relationships.
    
    Models vehicle system dependencies as a directed graph where:
    - Nodes are components/conditions
    - Edges represent cause -> effect relationships
    """
    
    def __init__(self):
        # Build the complete causal graph
        self.graph = self._build_graph()
        self.reverse_graph = self._build_reverse_graph()
        logger.info("CausalGraph initialized with %d nodes", len(self.graph))
    
    def _build_graph(self) -> Dict[str, List[str]]:
        """Build the causal graph (cause -> effects)."""
        return {
            # Electrical system
            'alternator_failing': [
                'low_battery_voltage',
                'engine_load_increase',
                'battery_warning_light',
                'dimming_headlights',
            ],
            'battery_aging': [
                'low_battery_voltage',
                'slow_cranking',
                'frequent_jump_starts',
            ],
            'bad_battery_connection': [
                'low_battery_voltage',
                'intermittent_electrical_issues',
            ],
            
            # Cooling system
            'thermostat_stuck': [
                'high_coolant_temp',
                'engine_overheating',
                'poor_heater_performance',
            ],
            'failing_water_pump': [
                'high_coolant_temp',
                'coolant_leak',
                'grinding_noise',
            ],
            'low_coolant': [
                'high_coolant_temp',
                'engine_overheating',
            ],
            'radiator_clogged': [
                'high_coolant_temp',
                'inefficient_cooling',
            ],
            'cooling_fan_failure': [
                'high_coolant_temp_at_idle',
                'overheating_in_traffic',
            ],
            
            # Intake/Vacuum
            'vacuum_leak': [
                'lean_fuel_trim',
                'rough_idle',
                'misfire',
                'high_rpm_at_idle',
            ],
            'intake_manifold_gasket_leak': [
                'lean_fuel_trim',
                'rough_idle',
            ],
            'pcv_valve_failure': [
                'rough_idle',
                'oil_consumption',
            ],
            
            # Ignition
            'worn_spark_plugs': [
                'misfire',
                'reduced_power',
                'fuel_efficiency_drop',
                'rough_idle',
            ],
            'failing_ignition_coil': [
                'misfire',
                'reduced_power',
                'engine_stalling',
            ],
            'bad_spark_plug_wires': [
                'misfire',
                'rough_idle',
            ],
            
            # Fuel system
            'clogged_fuel_filter': [
                'low_fuel_pressure',
                'engine_hesitation',
                'reduced_power',
            ],
            'failing_fuel_pump': [
                'low_fuel_pressure',
                'engine_hesitation',
                'hard_starting',
                'engine_stalling',
            ],
            'dirty_fuel_injectors': [
                'lean_fuel_trim',
                'misfire',
                'rough_idle',
            ],
            'fuel_injector_failure': [
                'rich_fuel_trim',
                'misfire',
                'fuel_smell',
            ],
            
            # Exhaust/Emissions
            'failing_catalytic_converter': [
                'reduced_power',
                'rotten_egg_smell',
                'high_emissions',
                'p0420_code',
            ],
            'bad_oxygen_sensor': [
                'rich_fuel_trim',
                'poor_fuel_economy',
                'high_emissions',
            ],
            'exhaust_leak': [
                'loud_exhaust',
                'oxygen_sensor_inaccurate_reading',
            ],
            
            # Engine mechanical
            'worn_timing_belt': [
                'engine_noise',
                'reduced_power',
                'timing_drift',
                'valve_damage_risk',
            ],
            'low_oil_pressure': [
                'engine_noise',
                'bearing_wear',
                'engine_damage_risk',
            ],
            'worn_piston_rings': [
                'oil_consumption',
                'low_compression',
                'blue_exhaust_smoke',
            ],
            
            # Transmission
            'low_transmission_fluid': [
                'harsh_shifting',
                'transmission_slippage',
                'overheating_transmission',
            ],
            'worn_transmission': [
                'transmission_slippage',
                'delayed_engagement',
                'unusual_noise',
            ],
            'torque_converter_failure': [
                'shudder_at_speed',
                'overheating_transmission',
            ],
            
            # Brakes
            'worn_brake_pads': [
                'brake_noise',
                'increased_stopping_distance',
                'brake_vibration',
            ],
            'brake_fluid_leak': [
                'soft_brake_pedal',
                'decreased_braking_power',
            ],
            'warped_brake_rotors': [
                'brake_vibration',
                'pulsating_brake_pedal',
            ],
            
            # Sensors
            'maf_sensor_dirty': [
                'inaccurate_air_flow_reading',
                'poor_fuel_economy',
                'rough_idle',
            ],
            'coolant_temp_sensor_failure': [
                'inaccurate_temp_reading',
                'poor_fuel_economy',
            ],
            'throttle_position_sensor_failure': [
                'hesitation',
                'erratic_idle',
            ],
        }
    
    def _build_reverse_graph(self) -> Dict[str, List[str]]:
        """Build reverse graph (effect -> causes)."""
        reverse = defaultdict(list)
        for cause, effects in self.graph.items():
            for effect in effects:
                reverse[effect].append(cause)
        return dict(reverse)
    
    def find_root_cause(self, symptoms: List[str]) -> List[Dict[str, Any]]:
        """
        Find most likely root causes given observed symptoms.
        
        Args:
            symptoms: List of observed symptoms
        
        Returns:
            Ranked list of probable root causes with scores
        """
        if not symptoms:
            return []
        
        # Normalize symptoms
        symptoms = set(s.lower().replace(' ', '_') for s in symptoms)
        
        # Score each potential root cause
        candidates = {}
        
        for cause, expected_effects in self.graph.items():
            expected_set = set(e.lower().replace(' ', '_') for e in expected_effects)
            
            # Count matching symptoms
            matches = len(symptoms & expected_set)
            total_expected = len(expected_set)
            
            if matches > 0:
                # Precision: what fraction of expected symptoms are observed
                precision = matches / total_expected if total_expected > 0 else 0
                
                # Recall: what fraction of observed symptoms are explained
                recall = matches / len(symptoms) if symptoms else 0
                
                # F1 score
                f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
                
                candidates[cause] = {
                    'cause': cause,
                    'confidence': f1,
                    'matches': matches,
                    'total_expected': total_expected,
                    'matched_symptoms': list(symptoms & expected_set),
                    'unmatched_symptoms': list(symptoms - expected_set),
                    'missing_expected': list(expected_set - symptoms),
                }
        
        # Sort by confidence
        ranked = sorted(candidates.values(), key=lambda x: x['confidence'], reverse=True)
        
        return ranked[:10]  # Top 10
    
    def get_related_symptoms(self, root_cause: str) -> List[str]:
        """
        Get all expected symptoms for a root cause.
        
        Args:
            root_cause: The root cause to look up
        
        Returns:
            List of expected symptoms
        """
        cause_normalized = root_cause.lower().replace(' ', '_')
        
        # Direct match
        for key in self.graph:
            if key.lower().replace(' ', '_') == cause_normalized:
                return self.graph[key]
        
        return []
    
    def explain_chain(self, root_cause: str) -> str:
        """
        Generate human-readable cause-effect chain.
        
        Args:
            root_cause: Root cause to explain
        
        Returns:
            Human-readable chain string
        """
        effects = self.get_related_symptoms(root_cause)
        
        if not effects:
            return f"No known effects for {root_cause}."
        
        # Format as chain
        cause_formatted = root_cause.replace('_', ' ').title()
        effects_formatted = [e.replace('_', ' ') for e in effects]
        
        if len(effects_formatted) == 1:
            return f"{cause_formatted} → {effects_formatted[0]}"
        elif len(effects_formatted) == 2:
            return f"{cause_formatted} → {effects_formatted[0]} and {effects_formatted[1]}"
        else:
            chain = f"{cause_formatted} → "
            chain += ", ".join(effects_formatted[:-1])
            chain += f", and {effects_formatted[-1]}"
            return chain
    
    def get_all_causes(self) -> List[str]:
        """Get list of all known root causes."""
        return sorted(self.graph.keys())
    
    def get_all_symptoms(self) -> List[str]:
        """Get list of all known symptoms."""
        symptoms = set()
        for effects in self.graph.values():
            symptoms.update(effects)
        return sorted(symptoms)
    
    def find_path(self, start: str, end: str) -> Optional[List[str]]:
        """
        Find causal path from start to end using BFS.
        
        Args:
            start: Starting node (cause)
            end: Target node (symptom)
        
        Returns:
            Path as list of nodes, or None if no path
        """
        if start not in self.graph:
            return None
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            if current.lower().replace(' ', '_') == end.lower().replace(' ', '_'):
                return path
            
            for effect in self.graph.get(current, []):
                if effect not in visited:
                    visited.add(effect)
                    queue.append((effect, path + [effect]))
        
        return None
    
    def get_causes_for_symptom(self, symptom: str) -> List[str]:
        """
        Get all possible causes for a symptom.
        
        Args:
            symptom: The observed symptom
        
        Returns:
            List of potential causes
        """
        symptom_normalized = symptom.lower().replace(' ', '_')
        
        causes = []
        for effect, potential_causes in self.reverse_graph.items():
            if effect.lower().replace(' ', '_') == symptom_normalized:
                causes.extend(potential_causes)
        
        return causes
    
    def analyze_symptom_combination(self, symptoms: List[str]) -> Dict[str, Any]:
        """
        Comprehensive analysis of symptom combination.
        
        Args:
            symptoms: List of observed symptoms
        
        Returns:
            Analysis dict with root causes, chains, and recommendations
        """
        root_causes = self.find_root_cause(symptoms)
        
        # Find common causes across symptoms
        all_causes = set()
        symptom_to_causes = {}
        
        for symptom in symptoms:
            causes = self.get_causes_for_symptom(symptom)
            symptom_to_causes[symptom] = causes
            all_causes.update(causes)
        
        # Find causes that explain multiple symptoms
        multi_symptom_causes = []
        for cause in all_causes:
            explained = sum(1 for s in symptoms if cause in symptom_to_causes.get(s, []))
            if explained > 1:
                multi_symptom_causes.append({
                    'cause': cause,
                    'explained_symptoms': explained,
                    'total_symptoms': len(symptoms),
                })
        
        multi_symptom_causes.sort(key=lambda x: x['explained_symptoms'], reverse=True)
        
        return {
            'observed_symptoms': symptoms,
            'ranked_root_causes': root_causes[:5],
            'multi_symptom_causes': multi_symptom_causes[:5],
            'total_causes_considered': len(all_causes),
        }
