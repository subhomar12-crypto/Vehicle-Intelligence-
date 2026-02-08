"""
AI/ML Pipeline for PREDICT.

Provides vehicle failure prediction, health scoring, and diagnostic assistance.

Usage:
    from predict.core.ai import get_unified_ai, get_llm_assistant
    
    # Health analysis
    ai = get_unified_ai()
    result = await ai.analyze_vehicle_health(vehicle_id, obd_data)
    
    # LLM assistance
    assistant = get_llm_assistant()
    response = assistant.explain_dtc("P0301", "Cylinder 1 Misfire Detected")
"""

from predict.core.ai.model_loader import ModelLoader, get_model_loader
from predict.core.ai.lstm_predictor import LSTMPredictor
from predict.core.ai.ensemble_voter import EnsembleVoter, ModelPrediction
from predict.core.ai.explainability import ExplainabilityEngine, FeatureImportance
from predict.core.ai.unified_ai_module import UnifiedAI, get_unified_ai

__all__ = [
    # Model loading
    "ModelLoader",
    "get_model_loader",
    
    # Predictors
    "LSTMPredictor",
    "EnsembleVoter",
    "ModelPrediction",
    
    # Explanations
    "ExplainabilityEngine",
    "FeatureImportance",
    
    # Unified interface
    "UnifiedAI",
    "get_unified_ai",
]

# Optional LLM import (may fail if llama_cpp not installed)
try:
    from predict.core.ai.llm.assistant import LLMAssistant, get_llm_assistant
    __all__.extend(["LLMAssistant", "get_llm_assistant"])
except ImportError:
    pass
