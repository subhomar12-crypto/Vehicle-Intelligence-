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

# Lazy imports to avoid loading heavy dependencies at startup
def __getattr__(name):
    if name in ("UnifiedAI", "get_unified_ai"):
        from predict.core.ai.unified_ai_module import UnifiedAI, get_unified_ai
        return UnifiedAI if name == "UnifiedAI" else get_unified_ai
    if name in ("LLMAssistant", "get_llm_assistant"):
        from predict.core.ai.llm.assistant import LLMAssistant, get_llm_assistant
        return LLMAssistant if name == "LLMAssistant" else get_llm_assistant
    raise AttributeError(f"module 'predict.core.ai' has no attribute {name!r}")

__all__ = [
    # Unified interface
    "UnifiedAI",
    "get_unified_ai",

    # LLM
    "LLMAssistant",
    "get_llm_assistant",
]

