"""
LLM model configurations.

The primary LLM is served via Ollama (see assistant.py).
This file provides configuration metadata for model management utilities.
"""

from dataclasses import dataclass


@dataclass
class LLMModelConfig:
    """Configuration for an LLM model."""
    name: str
    ollama_model: str
    context_length: int
    temperature: float
    max_tokens: int = 500


AVAILABLE_MODELS = {
    "qwen3.5-2b": LLMModelConfig(
        name="qwen3.5-2b",
        ollama_model="qwen3.5:2b",
        context_length=4096,
        temperature=0.3,
    ),
    "qwen3.5-4b": LLMModelConfig(
        name="qwen3.5-4b",
        ollama_model="qwen3.5:4b",
        context_length=4096,
        temperature=0.3,
    ),
}


def get_default_model() -> str:
    return "qwen3.5-2b"


def get_model_config(name: str) -> LLMModelConfig:
    if name not in AVAILABLE_MODELS:
        available = ", ".join(AVAILABLE_MODELS.keys())
        raise KeyError(f"Model '{name}' not found. Available: {available}")
    return AVAILABLE_MODELS[name]


def list_available_models() -> list:
    return list(AVAILABLE_MODELS.keys())


def get_model_info(name: str) -> dict:
    cfg = get_model_config(name)
    return {
        'name': cfg.name,
        'ollama_model': cfg.ollama_model,
        'context_length': cfg.context_length,
        'temperature': cfg.temperature,
        'max_tokens': cfg.max_tokens,
    }
