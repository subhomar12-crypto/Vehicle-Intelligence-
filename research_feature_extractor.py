"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Research Feature Extractor - Converts LLM research to numerical features
for AI prediction integration.

This module bridges the gap between qualitative research data and
quantitative features used by AI prediction models.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ResearchFeatures:
    """
    Numerical features extracted from research for AI modules.

    These features are used by:
    - enhanced_prediction_engine.py: Adjusts failure probabilities
    - lstm_predictor.py: Additional input features
    - predictive_failure_engine.py: Component-specific risk factors
    - rul_estimation.py: Remaining useful life adjustments
    """

    # Risk multipliers - BOUNDS ENFORCED to prevent LLM hallucination impact
    # known_issue_multiplier: 0.8-1.5 (1.0 = normal, >1.0 = more risky)
    # reliability_factor: 0.8-1.2 (1.0 = normal, >1.0 = less reliable)
    known_issue_multiplier: float = 1.0
    reliability_factor: float = 1.0

    # Part-specific risk boosts (0.0-0.5 probability increase - capped to prevent overconfidence)
    failure_probability_boost: Dict[str, float] = field(default_factory=dict)

    # Bounds constants for validation
    MULTIPLIER_MIN: float = field(default=0.8, repr=False)
    MULTIPLIER_MAX: float = field(default=1.5, repr=False)
    RELIABILITY_MIN: float = field(default=0.8, repr=False)
    RELIABILITY_MAX: float = field(default=1.2, repr=False)
    BOOST_MAX: float = field(default=0.5, repr=False)  # Max 50% boost per component

    # Cost estimates in QAR
    avg_part_costs: Dict[str, int] = field(default_factory=dict)

    # Common issues
    common_failure_parts: List[str] = field(default_factory=list)

    # Severity weights for DTC interpretation
    dtc_severity_adjustments: Dict[str, float] = field(default_factory=dict)

    # Fleet comparison data
    fleet_percentiles: Dict[str, float] = field(default_factory=dict)

    # Recall risk
    has_active_recalls: bool = False
    recall_severity: float = 0.0  # 0-1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def clamp_multiplier(value: Any, default: float = 1.0) -> float:
        """Clamp known_issue_multiplier to safe bounds (0.8-1.5)."""
        try:
            val = float(value)
            if val < 0.8 or val > 1.5:
                logger.warning(f"LLM multiplier {val} out of bounds, clamping to [0.8, 1.5]")
            return max(0.8, min(1.5, val))
        except (TypeError, ValueError):
            logger.warning(f"Invalid multiplier value: {value}, using default {default}")
            return default

    @staticmethod
    def clamp_reliability(value: Any, default: float = 1.0) -> float:
        """Clamp reliability_factor to safe bounds (0.8-1.2)."""
        try:
            val = float(value)
            if val < 0.8 or val > 1.2:
                logger.warning(f"LLM reliability factor {val} out of bounds, clamping to [0.8, 1.2]")
            return max(0.8, min(1.2, val))
        except (TypeError, ValueError):
            logger.warning(f"Invalid reliability value: {value}, using default {default}")
            return default

    @staticmethod
    def clamp_boost(value: Any, default: float = 0.0) -> float:
        """Clamp probability boost to safe bounds (0.0-0.5)."""
        try:
            val = float(value)
            if val < 0.0 or val > 0.5:
                logger.warning(f"LLM boost {val} out of bounds, clamping to [0.0, 0.5]")
            return max(0.0, min(0.5, val))
        except (TypeError, ValueError):
            logger.warning(f"Invalid boost value: {value}, using default {default}")
            return default

    @staticmethod
    def validate_boost_dict(boost_dict: Any) -> Dict[str, float]:
        """Validate and clamp all values in a failure_probability_boost dict."""
        if not isinstance(boost_dict, dict):
            return {}
        validated = {}
        for key, value in boost_dict.items():
            validated[str(key)] = ResearchFeatures.clamp_boost(value)
        return validated

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchFeatures':
        """Create ResearchFeatures from dict with bounds validation."""
        return cls(
            known_issue_multiplier=cls.clamp_multiplier(data.get('known_issue_multiplier', 1.0)),
            reliability_factor=cls.clamp_reliability(data.get('reliability_factor', 1.0)),
            failure_probability_boost=cls.validate_boost_dict(data.get('failure_probability_boost', {})),
            avg_part_costs=data.get('avg_part_costs', {}),
            common_failure_parts=data.get('common_failure_parts', []),
            dtc_severity_adjustments=data.get('dtc_severity_adjustments', {}),
            fleet_percentiles=data.get('fleet_percentiles', {}),
            has_active_recalls=data.get('has_active_recalls', False),
            recall_severity=max(0.0, min(1.0, float(data.get('recall_severity', 0.0))))
        )


class ResearchFeatureExtractor:
    """
    Extracts numerical features from vehicle research for AI integration.

    This class transforms qualitative research data (common problems,
    owner reviews, recalls) into quantitative features that can be
    used by machine learning models.
    """

    # Standard component name mappings
    COMPONENT_ALIASES = {
        'alternator': ['alternator', 'charging system', 'generator', 'charging'],
        'battery': ['battery', '12v battery', 'starter battery', 'car battery'],
        'starter': ['starter', 'starter motor', 'starting system', 'cranking'],
        'fuel_pump': ['fuel pump', 'fuel delivery', 'fuel system pump'],
        'fuel_filter': ['fuel filter'],
        'spark_plug': ['spark plugs', 'spark plug', 'ignition', 'spark'],
        'ignition_coil': ['ignition coil', 'coil pack', 'coil'],
        'oxygen_sensor': ['o2 sensor', 'oxygen sensor', 'lambda sensor', 'o2'],
        'catalytic_converter': ['catalytic converter', 'cat', 'exhaust catalyst', 'catalytic'],
        'maf_sensor': ['maf', 'mass air flow', 'air flow sensor', 'maf sensor'],
        'map_sensor': ['map sensor', 'manifold pressure'],
        'thermostat': ['thermostat', 'cooling thermostat'],
        'water_pump': ['water pump', 'coolant pump'],
        'radiator': ['radiator', 'cooling radiator'],
        'coolant_system': ['coolant', 'cooling system', 'antifreeze'],
        'transmission': ['transmission', 'gearbox', 'cvt', 'automatic transmission', 'manual transmission'],
        'clutch': ['clutch', 'clutch plate', 'clutch disc'],
        'brake_pads': ['brake pads', 'brake pad', 'front brakes', 'rear brakes'],
        'brake_rotors': ['brake rotors', 'brake discs', 'rotors'],
        'brake_calipers': ['brake caliper', 'caliper', 'brake calipers'],
        'suspension': ['suspension', 'struts', 'shocks', 'shock absorbers'],
        'cv_joint': ['cv joint', 'cv axle', 'constant velocity'],
        'tie_rod': ['tie rod', 'tie rod end', 'steering linkage'],
        'wheel_bearing': ['wheel bearing', 'hub bearing'],
        'timing_belt': ['timing belt', 'timing chain', 'cam belt'],
        'serpentine_belt': ['serpentine belt', 'drive belt', 'accessory belt'],
        'ac_compressor': ['ac compressor', 'air conditioning', 'a/c compressor'],
        'power_steering': ['power steering', 'steering pump', 'ps pump'],
        'egr_valve': ['egr valve', 'egr', 'exhaust gas recirculation'],
        'pcv_valve': ['pcv valve', 'pcv', 'positive crankcase'],
        'head_gasket': ['head gasket', 'cylinder head gasket'],
        'oil_pump': ['oil pump', 'oil pressure'],
        'turbo': ['turbocharger', 'turbo', 'turbo charger'],
    }

    # DTC prefix to component category mapping
    DTC_CATEGORIES = {
        'P00': 'fuel_air_metering',
        'P01': 'fuel_air_metering',
        'P02': 'fuel_air_metering',
        'P03': 'ignition',
        'P04': 'emissions',
        'P05': 'speed_idle',
        'P06': 'computer',
        'P07': 'transmission',
        'P0A': 'hybrid',
        'P0B': 'hybrid',
        'P0C': 'hybrid',
    }

    # Severity weights for problem types
    SEVERITY_WEIGHTS = {
        'high': 0.25,
        'medium': 0.12,
        'low': 0.05
    }

    # Frequency weights
    FREQUENCY_WEIGHTS = {
        'common': 1.0,
        'occasional': 0.6,
        'rare': 0.3
    }

    def extract_features(self, research_data: Dict[str, Any]) -> ResearchFeatures:
        """
        Extract numerical features from research data.

        Args:
            research_data: Raw research data from VehicleResearchEngine

        Returns:
            ResearchFeatures ready for AI integration
        """
        features = ResearchFeatures()

        # Check if ai_features already computed
        if 'ai_features' in research_data:
            ai_features = research_data['ai_features']
            # CRITICAL: Apply bounds validation to prevent LLM hallucinations
            features.known_issue_multiplier = ResearchFeatures.clamp_multiplier(
                ai_features.get('known_issue_multiplier', 1.0)
            )
            features.reliability_factor = ResearchFeatures.clamp_reliability(
                ai_features.get('reliability_factor', 1.0)
            )
            # Normalize component names AND clamp boost values
            raw_boosts = self._normalize_components(
                ai_features.get('failure_probability_boost', {})
            )
            features.failure_probability_boost = ResearchFeatures.validate_boost_dict(raw_boosts)
            features.avg_part_costs = self._normalize_components(
                ai_features.get('avg_part_costs', {})
            )
            features.common_failure_parts = ai_features.get('common_failure_parts', [])
            features.dtc_severity_adjustments = ai_features.get('dtc_severity_adjustments', {})
        else:
            # Extract from raw research data
            features = self._extract_from_raw(research_data)

        # Process recalls
        recalls = research_data.get('recalls', [])
        if recalls:
            features.has_active_recalls = True
            features.recall_severity = min(1.0, len(recalls) * 0.2)

        return features

    def _extract_from_raw(self, research_data: Dict[str, Any]) -> ResearchFeatures:
        """Extract features from raw research data structure"""
        features = ResearchFeatures()

        # Extract from common problems
        problems = research_data.get('common_problems', [])
        if problems:
            features.known_issue_multiplier = self._calculate_issue_multiplier(problems)
            features.dtc_severity_adjustments = self._generate_dtc_adjustments(problems)

        # Extract from failure-prone parts
        parts = research_data.get('failure_prone_parts', [])
        for part in parts:
            if isinstance(part, dict):
                part_name = self._normalize_part_name(part.get('part', ''))
                if part_name:
                    features.common_failure_parts.append(part_name)

                    # Get failure rate - clamp to prevent LLM hallucination impact
                    failure_rate = part.get('failure_rate', 0.1)
                    if isinstance(failure_rate, str):
                        try:
                            failure_rate = float(failure_rate)
                        except ValueError:
                            failure_rate = 0.1
                    # Clamp boost to safe bounds (0.0-0.5)
                    features.failure_probability_boost[part_name] = ResearchFeatures.clamp_boost(failure_rate)

                    # Get cost
                    cost = part.get('avg_cost_qar', 200)
                    if isinstance(cost, str):
                        try:
                            cost = int(cost.replace(',', ''))
                        except ValueError:
                            cost = 200
                    features.avg_part_costs[part_name] = int(cost)

        # Extract reliability factor
        reliability_score = research_data.get('reliability_score', 5.0)
        if isinstance(reliability_score, str):
            try:
                reliability_score = float(reliability_score)
            except ValueError:
                reliability_score = 5.0
        features.reliability_factor = max(0.8, min(1.2, 2 - (reliability_score / 10)))

        return features

    def _calculate_issue_multiplier(self, problems: List[Dict]) -> float:
        """Calculate overall issue multiplier from problems list.

        Returns value clamped to [0.8, 1.5] to prevent hallucination impact.
        """
        multiplier = 1.0

        for problem in problems:
            if isinstance(problem, dict):
                severity = problem.get('severity', 'low')
                frequency = problem.get('frequency', 'occasional')

                severity_weight = self.SEVERITY_WEIGHTS.get(severity, 0.05)
                frequency_weight = self.FREQUENCY_WEIGHTS.get(frequency, 0.6)

                multiplier += severity_weight * frequency_weight

        # Use centralized clamping for consistency
        return ResearchFeatures.clamp_multiplier(multiplier)

    def _generate_dtc_adjustments(self, problems: List[Dict]) -> Dict[str, float]:
        """Generate DTC severity adjustments based on known issues"""
        adjustments = {}

        # Keywords that map to DTC categories
        keyword_to_dtc = {
            'engine': ['P00', 'P01', 'P02'],
            'transmission': ['P07'],
            'fuel': ['P02'],
            'emission': ['P04'],
            'ignition': ['P03'],
            'evap': ['P04'],
            'catalyst': ['P04'],
            'idle': ['P05'],
            'speed': ['P05'],
            'misfire': ['P03'],
            'oxygen': ['P01', 'P02'],
            'air': ['P01', 'P02'],
        }

        severity_mult = {'high': 1.3, 'medium': 1.15, 'low': 1.05}

        for problem in problems:
            if isinstance(problem, dict):
                problem_text = str(problem.get('problem', '')).lower()
                severity = problem.get('severity', 'low')
                mult = severity_mult.get(severity, 1.05)

                for keyword, dtc_prefixes in keyword_to_dtc.items():
                    if keyword in problem_text:
                        for prefix in dtc_prefixes:
                            # Use max if already exists
                            current = adjustments.get(prefix, 1.0)
                            adjustments[prefix] = max(current, mult)

        return adjustments

    def _normalize_components(self, component_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize component names to standard identifiers"""
        normalized = {}

        for raw_name, value in component_dict.items():
            normalized_name = self._normalize_part_name(raw_name)
            if normalized_name:
                normalized[normalized_name] = value

        return normalized

    def _normalize_part_name(self, raw_name: str) -> str:
        """Normalize a part name to standard identifier"""
        if not raw_name:
            return ""

        raw_lower = raw_name.lower().strip()

        # Check against aliases
        for standard_name, aliases in self.COMPONENT_ALIASES.items():
            if any(alias in raw_lower for alias in aliases):
                return standard_name

        # If no match, create a normalized version
        normalized = raw_lower.replace(' ', '_').replace('-', '_')
        normalized = re.sub(r'[^a-z0-9_]', '', normalized)
        return normalized if normalized else ""

    def apply_to_prediction(
        self,
        base_prediction: Dict[str, Any],
        features: ResearchFeatures
    ) -> Dict[str, Any]:
        """
        Apply research features to adjust a prediction.

        Args:
            base_prediction: Original prediction from AI model
            features: Research features to apply

        Returns:
            Adjusted prediction with research-based modifications
        """
        adjusted = base_prediction.copy()

        # Apply overall health adjustment
        if 'overall_health' in adjusted:
            # Lower reliability = lower health
            health_adjustment = 2 - features.reliability_factor  # 0.8-1.2
            adjusted['overall_health'] = int(
                adjusted['overall_health'] * health_adjustment
            )
            adjusted['overall_health'] = max(0, min(100, adjusted['overall_health']))

        # Apply component-specific adjustments
        if 'component_risks' in adjusted:
            for component, risk in adjusted['component_risks'].items():
                normalized = self._normalize_part_name(component)
                if normalized in features.failure_probability_boost:
                    boost = features.failure_probability_boost[normalized]
                    # Increase risk by boost factor
                    new_risk = min(1.0, risk * (1 + boost))
                    adjusted['component_risks'][component] = new_risk

        # Apply known issue multiplier to failure probabilities
        if 'failure_probability' in adjusted:
            adjusted['failure_probability'] = min(
                1.0,
                adjusted['failure_probability'] * features.known_issue_multiplier
            )

        # Add research metadata
        adjusted['research_applied'] = True
        adjusted['research_multiplier'] = features.known_issue_multiplier
        adjusted['known_issues_count'] = len(features.common_failure_parts)

        # Add cost estimates if available
        if features.avg_part_costs:
            adjusted['estimated_repair_costs'] = features.avg_part_costs

        # Add recall warning
        if features.has_active_recalls:
            adjusted['recall_warning'] = True
            adjusted['recall_severity'] = features.recall_severity

        return adjusted

    def get_component_risk_summary(self, features: ResearchFeatures) -> List[Dict[str, Any]]:
        """
        Get a summary of component risks for display.

        Returns sorted list of components with their risk levels and costs.
        """
        summary = []

        for part in features.common_failure_parts:
            risk = features.failure_probability_boost.get(part, 0.1)
            cost = features.avg_part_costs.get(part, 0)

            # Determine risk level
            if risk >= 0.3:
                risk_level = 'high'
            elif risk >= 0.15:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            summary.append({
                'component': part,
                'risk_probability': risk,
                'risk_level': risk_level,
                'estimated_cost_qar': cost,
                'display_name': part.replace('_', ' ').title()
            })

        # Sort by risk level (high first)
        risk_order = {'high': 0, 'medium': 1, 'low': 2}
        summary.sort(key=lambda x: (risk_order.get(x['risk_level'], 3), -x['risk_probability']))

        return summary


# Singleton instance
_extractor: Optional[ResearchFeatureExtractor] = None


def get_feature_extractor() -> ResearchFeatureExtractor:
    """Get global feature extractor instance"""
    global _extractor
    if _extractor is None:
        _extractor = ResearchFeatureExtractor()
    return _extractor


def extract_features_from_research(research_data: Dict[str, Any]) -> ResearchFeatures:
    """
    Convenience function to extract features from research data.

    Args:
        research_data: Research data dictionary

    Returns:
        ResearchFeatures object
    """
    extractor = get_feature_extractor()
    return extractor.extract_features(research_data)
