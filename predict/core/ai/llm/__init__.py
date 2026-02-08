"""
LLM (Large Language Model) integration.

Local inference using llama-cpp-python for privacy and offline operation.
"""

try:
    from predict.core.ai.llm.assistant import LLMAssistant, get_llm_assistant
    
    __all__ = ["LLMAssistant", "get_llm_assistant"]
except ImportError:
    # llama_cpp not installed
    __all__ = []
