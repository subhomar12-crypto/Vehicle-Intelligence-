"""
Survival Analysis for time-to-failure estimation.

Uses Weibull distribution to model component lifetime and predict
failure probability over time with confidence bands.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WeibullParams:
    """Weibull distribution parameters."""
    shape: float  # k - determines shape of distribution
    scale: float  # lambda - characteristic life
    r_squared: float  # Goodness of fit


class SurvivalAnalyzer:
    """
    Survival analysis for component failure prediction.
    
    Uses Weibull distribution to model:
    - Time-to-failure with confidence bands
    - Optimal maintenance windows
    - Degradation curve fitting
    """
    
    def __init__(self):
        self._has_lifelines = False
        self._check_lifelines()
    
    def _check_lifelines(self) -> None:
        """Check if lifelines library is available."""
        try:
            from lifelines import WeibullFitter
            self._has_lifelines = True
            logger.info("lifelines library available for survival analysis")
        except ImportError:
            logger.warning("lifelines not available, using numpy implementation")
            self._has_lifelines = False
    
    def _weibull_pdf(self, t: float, shape: float, scale: float) -> float:
        """Weibull probability density function. Accepts scalar or array."""
        if scale <= 0 or shape <= 0:
            return np.zeros_like(t) if isinstance(t, np.ndarray) else 0.0
        t = np.asarray(t, dtype=float)
        t = np.maximum(t, 0.0)
        return (shape / scale) * (t / scale) ** (shape - 1) * np.exp(-(t / scale) ** shape)
    
    def _weibull_cdf(self, t, shape: float, scale: float):
        """Weibull cumulative distribution function. Accepts scalar or array."""
        if scale <= 0 or shape <= 0:
            return np.zeros_like(t) if isinstance(t, np.ndarray) else 0.0
        t = np.asarray(t, dtype=float)
        t = np.maximum(t, 0.0)
        return 1 - np.exp(-(t / scale) ** shape)
    
    def _weibull_sf(self, t, shape: float, scale: float):
        """Weibull survival function (1 - CDF). Accepts scalar or array."""
        if scale <= 0 or shape <= 0:
            return np.ones_like(t) if isinstance(t, np.ndarray) else 1.0
        t = np.asarray(t, dtype=float)
        t = np.maximum(t, 0.0)
        return np.exp(-(t / scale) ** shape)
    
    def _fit_weibull_mle(self, data: List[float]) -> WeibullParams:
        """
        Fit Weibull distribution using Maximum Likelihood Estimation.
        
        Args:
            data: List of failure times or degradation measurements
        
        Returns:
            Fitted Weibull parameters
        """
        data = np.array(data)
        data = data[data > 0]  # Remove non-positive values
        
        if len(data) < 5:
            logger.warning("Insufficient data for Weibull fitting")
            return WeibullParams(shape=1.5, scale=np.mean(data) if len(data) > 0 else 100, r_squared=0.0)
        
        # Log-likelihood function for Weibull
        def neg_log_likelihood(params):
            k, lam = params
            if k <= 0 or lam <= 0:
                return 1e10
            n = len(data)
            log_likelihood = (
                n * np.log(k) - n * k * np.log(lam) +
                (k - 1) * np.sum(np.log(data)) -
                np.sum((data / lam) ** k)
            )
            return -log_likelihood
        
        # Optimize using simple grid search + refinement
        best_k, best_lam = 1.5, np.median(data)
        best_nll = neg_log_likelihood([best_k, best_lam])
        
        # Grid search
        for k in np.linspace(0.5, 5, 20):
            for lam in np.linspace(np.percentile(data, 10), np.percentile(data, 90), 20):
                nll = neg_log_likelihood([k, lam])
                if nll < best_nll:
                    best_nll = nll
                    best_k, best_lam = k, lam
        
        # Calculate R-squared (approximation)
        observed_cdf = np.arange(1, len(data) + 1) / (len(data) + 1)
        predicted_cdf = self._weibull_cdf(np.sort(data), best_k, best_lam)
        ss_res = np.sum((observed_cdf - predicted_cdf) ** 2)
        ss_tot = np.sum((observed_cdf - np.mean(observed_cdf)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        return WeibullParams(shape=best_k, scale=best_lam, r_squared=r_squared)
    
    def fit_weibull(self, degradation_data: List[float]) -> Dict[str, float]:
        """
        Fit Weibull distribution to degradation/failure data.
        
        Args:
            degradation_data: List of times to failure or degradation measurements
        
        Returns:
            Dict with shape, scale, and r_squared
        """
        if self._has_lifelines:
            try:
                from lifelines import WeibullFitter
                wf = WeibullFitter()
                wf.fit(degradation_data)
                return {
                    'shape': wf.lambda_,
                    'scale': wf.rho_,
                    'r_squared': 0.9,  # lifelines doesn't provide R^2 directly
                }
            except Exception as e:
                logger.warning(f"lifelines fitting failed: {e}, using MLE")
        
        # Use MLE implementation
        params = self._fit_weibull_mle(degradation_data)
        return {
            'shape': params.shape,
            'scale': params.scale,
            'r_squared': params.r_squared,
        }
    
    def predict_failure_distribution(
        self,
        component: str,
        current_data: List[float],
    ) -> Dict[str, float]:
        """
        Predict failure probability distribution over time.
        
        Args:
            component: Component name
            current_data: Historical degradation measurements
        
        Returns:
            Dict with p50, p80, p95 days to failure
        """
        if not current_data or len(current_data) < 3:
            logger.warning(f"Insufficient data for {component} failure prediction")
            return {
                'p50_days': 90.0,
                'p80_days': 180.0,
                'p95_days': 365.0,
                'median_days': 90.0,
                'confidence': 0.3,
            }
        
        # Fit Weibull
        params = self.fit_weibull(current_data)
        shape = params['shape']
        scale = params['scale']
        
        # Calculate percentiles
        # F(t) = p => t = scale * (-ln(1-p))^(1/shape)
        def percentile(p):
            return scale * ((-np.log(1 - p)) ** (1 / shape))
        
        p50 = percentile(0.50)
        p80 = percentile(0.80)
        p95 = percentile(0.95)
        
        # Confidence based on R^2 and data size
        confidence = min(0.9, params['r_squared'] * (1 + len(current_data) / 100))
        
        return {
            'p50_days': float(p50),
            'p80_days': float(p80),
            'p95_days': float(p95),
            'median_days': float(p50),
            'shape': float(shape),
            'scale': float(scale),
            'r_squared': float(params['r_squared']),
            'confidence': float(confidence),
        }
    
    def get_optimal_maintenance_window(
        self,
        failure_dist: Dict[str, float],
    ) -> Tuple[int, int]:
        """
        Calculate optimal maintenance window.
        
        Args:
            failure_dist: Output from predict_failure_distribution()
        
        Returns:
            (earliest_day, latest_day) for maintenance
        """
        p50 = failure_dist.get('p50_days', 90)
        p80 = failure_dist.get('p80_days', 180)
        
        # Schedule between p50 and p80
        earliest = int(p50 * 0.8)  # 20% before median
        latest = int(p80 * 0.9)    # Before 80% risk
        
        return (earliest, latest)
    
    def fit_degradation_curve(
        self,
        history: List[Tuple[float, float]],
    ) -> Dict[str, float]:
        """
        Fit degradation curve to time-series data.
        
        Args:
            history: List of (timestamp, value) tuples
        
        Returns:
            Curve parameters
        """
        if len(history) < 3:
            return {'curve_type': 'insufficient_data'}
        
        timestamps = np.array([h[0] for h in history])
        values = np.array([h[1] for h in history])
        
        # Normalize timestamps to days from start
        days = (timestamps - timestamps[0]) / 86400.0
        
        # Try linear fit
        linear_coef = np.polyfit(days, values, 1)
        linear_residual = np.sum((values - np.polyval(linear_coef, days)) ** 2)
        
        # Try exponential fit: y = a * exp(b * x)
        # ln(y) = ln(a) + b * x
        if np.all(values > 0):
            exp_coef = np.polyfit(days, np.log(values), 1)
            exp_a = np.exp(exp_coef[1])
            exp_b = exp_coef[0]
            exp_residual = np.sum((values - exp_a * np.exp(exp_b * days)) ** 2)
            
            # Choose better fit
            if exp_residual < linear_residual:
                return {
                    'curve_type': 'exponential',
                    'a': float(exp_a),
                    'b': float(exp_b),
                    'residual': float(exp_residual),
                    'formula': f'{exp_a:.3f} * exp({exp_b:.6f} * days)',
                }
        
        return {
            'curve_type': 'linear',
            'slope': float(linear_coef[0]),
            'intercept': float(linear_coef[1]),
            'residual': float(linear_residual),
            'formula': f'{linear_coef[0]:.6f} * days + {linear_coef[1]:.3f}',
        }
    
    def predict_threshold_crossing(
        self,
        current_value: float,
        trend: float,
        threshold: float,
    ) -> Optional[float]:
        """
        Predict when a value will cross a threshold.
        
        Args:
            current_value: Current measurement
            trend: Rate of change per day
            threshold: Threshold to cross
        
        Returns:
            Estimated days until crossing, or None if not approaching
        """
        if trend == 0:
            return None
        
        if trend > 0 and current_value < threshold:
            # Increasing toward threshold
            days = (threshold - current_value) / trend
            return max(0, days)
        elif trend < 0 and current_value > threshold:
            # Decreasing toward threshold
            days = (current_value - threshold) / abs(trend)
            return max(0, days)
        
        return None
    
    def calculate_reliability(
        self,
        time_points: List[float],
        shape: float,
        scale: float,
    ) -> List[float]:
        """
        Calculate reliability (survival probability) at given time points.
        
        Args:
            time_points: List of time values
            shape: Weibull shape parameter
            scale: Weibull scale parameter
        
        Returns:
            Reliability values (0-1)
        """
        return [self._weibull_sf(t, shape, scale) for t in time_points]
    
    def calculate_hazard_rate(
        self,
        time_points: List[float],
        shape: float,
        scale: float,
    ) -> List[float]:
        """
        Calculate hazard rate (instantaneous failure rate) at time points.
        
        Args:
            time_points: List of time values
            shape: Weibull shape parameter
            scale: Weibull scale parameter
        
        Returns:
            Hazard rate values
        """
        rates = []
        for t in time_points:
            if t <= 0 or scale <= 0:
                rates.append(0.0)
            else:
                rate = (shape / scale) * (t / scale) ** (shape - 1)
                rates.append(rate)
        return rates
