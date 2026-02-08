"""
LLM Assistant for vehicle diagnostics and recommendations.

Uses local GGUF models via llama-cpp-python for privacy and offline operation.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from predict.core.ai.model_loader import get_model_loader
from predict.core.config import get_config

logger = logging.getLogger(__name__)


class LLMAssistant:
    """
    Local LLM assistant for vehicle-related queries.
    
    Provides:
    - Diagnostic explanations
    - Maintenance advice
    - Driving tips
    - General automotive Q&A
    """
    
    def __init__(self, model_filename: Optional[str] = None):
        self.config = get_config()
        self.model_path: Optional[Path] = None
        self.llm = None
        
        # Load model
        self._load_model(model_filename or self._get_default_model())
    
    def _get_default_model(self) -> str:
        """Get default model filename from config."""
        return getattr(self.config, 'LLM_MODEL_PATH', 'llama-2-7b-chat.Q4_K_M.gguf')
    
    def _load_model(self, model_filename: str) -> None:
        """Load GGUF model."""
        loader = get_model_loader()
        self.model_path = loader.get_llm_model_path(model_filename)
        
        if self.model_path is None:
            logger.warning(f"LLM model not found: {model_filename}")
            return
        
        try:
            from llama_cpp import Llama
            
            # Model parameters
            n_ctx = getattr(self.config, 'LLM_CONTEXT_SIZE', 4096)
            n_gpu_layers = getattr(self.config, 'LLM_GPU_LAYERS', 0)
            
            logger.info(f"Loading LLM from {self.model_path}")
            
            self.llm = Llama(
                model_path=str(self.model_path),
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=False,
            )
            
            logger.info("LLM loaded successfully")
        
        except ImportError:
            logger.warning("llama_cpp not installed, LLM unavailable")
        
        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
    
    def is_available(self) -> bool:
        """Check if LLM is loaded and available."""
        return self.llm is not None
    
    def ask(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Ask the assistant a question.
        
        Args:
            question: User question
            context: Optional vehicle context (OBD data, etc.)
            max_tokens: Maximum response length
            temperature: Sampling temperature
        
        Returns:
            Response with text and metadata
        """
        if not self.is_available():
            return {
                "response": self._fallback_response(question),
                "source": "fallback",
                "confidence": 0.0,
            }
        
        # Build prompt
        prompt = self._build_prompt(question, context)
        
        try:
            # Generate response
            output = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["</s>", "Human:", "User:"],
            )
            
            response_text = output['choices'][0]['text'].strip()
            
            return {
                "response": response_text,
                "source": "llm",
                "model": self.model_path.name if self.model_path else None,
                "tokens_used": output.get('usage', {}).get('total_tokens'),
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "response": self._fallback_response(question),
                "source": "fallback",
                "error": str(e),
            }
    
    def explain_dtc(self, dtc_code: str, description: str) -> Dict[str, Any]:
        """
        Explain a diagnostic trouble code in plain language.
        
        Args:
            dtc_code: DTC code (e.g., "P0301")
            description: Technical description
        
        Returns:
            Explanation with severity and advice
        """
        question = f"What does DTC code {dtc_code} ({description}) mean for my vehicle?"
        
        context = {
            "dtc_code": dtc_code,
            "dtc_description": description,
        }
        
        return self.ask(
            question=question,
            context=context,
            max_tokens=400,
            temperature=0.5,
        )
    
    def get_maintenance_advice(
        self,
        vehicle_info: Dict[str, Any],
        issues: List[str],
    ) -> Dict[str, Any]:
        """
        Get maintenance advice based on vehicle issues.
        
        Args:
            vehicle_info: Vehicle make, model, year, mileage
            issues: List of detected issues
        
        Returns:
            Maintenance recommendations
        """
        question = (
            f"My {vehicle_info.get('year')} {vehicle_info.get('make')} "
            f"{vehicle_info.get('model')} with {vehicle_info.get('mileage')}km "
            f"has these issues: {', '.join(issues)}. "
            f"What maintenance should I do?"
        )
        
        return self.ask(
            question=question,
            context=vehicle_info,
            max_tokens=600,
            temperature=0.6,
        )
    
    def _build_prompt(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build a structured prompt for the LLM."""
        system_prompt = """You are PREDICT AI, an automotive diagnostic assistant. 
Provide helpful, accurate advice about vehicle maintenance and diagnostics. 
Be concise but thorough. Always prioritize safety - recommend professional inspection for serious issues.
"""
        
        prompt_parts = [f"System: {system_prompt}"]
        
        # Add context if available
        if context:
            context_str = self._format_context(context)
            if context_str:
                prompt_parts.append(f"Context: {context_str}")
        
        prompt_parts.append(f"Human: {question}")
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dict into string."""
        parts = []
        
        if 'vehicle_id' in context:
            parts.append(f"Vehicle ID: {context['vehicle_id']}")
        
        if 'obd_data' in context:
            parts.append(f"Recent OBD readings available")
        
        if 'dtc_code' in context:
            parts.append(f"DTC Code: {context['dtc_code']}")
        
        if 'health_score' in context:
            parts.append(f"Health Score: {context['health_score']}")
        
        return ", ".join(parts)
    
    def _fallback_response(self, question: str) -> str:
        """Provide fallback response when LLM unavailable."""
        return (
            "I'm sorry, but the AI assistant is currently unavailable. "
            "Please consult your vehicle's manual or a qualified mechanic "
            "for assistance with your question."
        )


# Singleton instance
_llm_assistant: Optional[LLMAssistant] = None


def get_llm_assistant() -> LLMAssistant:
    """Get singleton LLMAssistant instance."""
    global _llm_assistant
    if _llm_assistant is None:
        _llm_assistant = LLMAssistant()
    return _llm_assistant
