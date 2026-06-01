"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Module: LLM Assistant

PREDICT AI - LLM Assistant Integration
Provides AI-powered analysis and explanations using local LLM models
Uses Ollama with Qwen 3.5-4B as the primary model
"""

import asyncio
import json
import logging
import os
import re
import threading
import time
from typing import Dict, Any, Optional, List, Callable, Iterator

import httpx

from predict.core.config import get_config

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = "qwen3.5:2b"

# Qwen3.5 stop tokens and cleanup patterns
STOP_TOKENS = ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]
_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class ModelConfig:
    """Configuration for available LLM models."""

    QWEN = {
        "id": "qwen",
        "name": "Qwen 3.5-2B",
        "ollama_model": OLLAMA_MODEL,
        "n_ctx": 4096,
        "description": "Full analysis, detailed explanations"
    }

    ALL_MODELS = [QWEN]


class LLMAssistant:
    """Local LLM assistant for predictions, DTC explanations, and customer support.
    Uses Ollama HTTP API for inference."""

    def __init__(self, model_filename: Optional[str] = None):
        self.config = get_config()
        self.is_loaded = False
        self.current_model_name: Optional[str] = None
        self.current_model_config: Optional[Dict[str, Any]] = None
        self.load_start_time: Optional[float] = None
        self.load_end_time: Optional[float] = None
        self._lock = threading.RLock()
        self._http_client = httpx.Client(base_url=OLLAMA_BASE_URL, timeout=120.0)

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return list of available models from Ollama."""
        try:
            resp = self._http_client.get("/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                ollama_names = {m["name"] for m in models}
                available = []
                for config in ModelConfig.ALL_MODELS:
                    if config["ollama_model"] in ollama_names or f"{config['ollama_model']}:latest" in ollama_names:
                        available.append({
                            "id": config["id"],
                            "name": config["name"],
                            "description": config["description"],
                            "ollama_model": config["ollama_model"]
                        })
                return available
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
        return []

    def _unload_current_model(self):
        """Unload model from Ollama memory."""
        with self._lock:
            if self.is_loaded and self.current_model_config:
                try:
                    self._http_client.post("/api/generate", json={
                        "model": self.current_model_config["ollama_model"],
                        "keep_alive": 0
                    })
                except Exception:
                    pass
            self.is_loaded = False
            self.current_model_name = None
            self.current_model_config = None

    def load_model(self, model_name: str = "qwen", callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """Load model via Ollama (warm it up)."""
        with self._lock:
            try:
                config = ModelConfig.QWEN
                model_name = "qwen"

                if self.current_model_name == model_name and self.is_loaded:
                    if callback:
                        callback(100, f"{config['name']} already loaded")
                    return True

                self.load_start_time = time.time()
                if callback:
                    callback(10, f"Loading {config['name']} via Ollama...")

                # Warm up the model by sending a tiny request
                resp = self._http_client.post("/api/generate", json={
                    "model": config["ollama_model"],
                    "prompt": "hello",
                    "options": {"num_predict": 1},
                    "stream": False,
                    "think": False
                }, timeout=120.0)

                if resp.status_code != 200:
                    logger.error(f"Ollama warmup failed: {resp.status_code} {resp.text}")
                    if callback:
                        callback(-1, f"Ollama error: {resp.status_code}")
                    return False

                if callback:
                    callback(100, f"{config['name']} loaded successfully!")

                self.is_loaded = True
                self.current_model_name = model_name
                self.current_model_config = config
                self.load_end_time = time.time()
                load_time = self.load_end_time - self.load_start_time
                logger.info(f"[OK] {config['name']} loaded via Ollama in {load_time:.1f}s")
                return True

            except Exception as e:
                logger.error(f"Failed to load LLM model via Ollama: {e}")
                self.is_loaded = False
                if callback:
                    callback(-1, f"Error: {str(e)}")
                return False

    async def load_model_async(self, model_name: str = "qwen", callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """Async wrapper for load_model."""
        return await asyncio.to_thread(self.load_model, model_name, callback)

    def switch_model(self, model_name: str, callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """Switch to a different model."""
        return self.load_model(model_name, callback)

    async def switch_model_async(self, model_name: str, callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """Async wrapper for switch_model."""
        return await asyncio.to_thread(self.switch_model, model_name, callback)

    def get_current_model_info(self) -> Dict[str, Any]:
        """Get info about the currently loaded model."""
        if not self.is_loaded or not self.current_model_config:
            return {"name": "None", "loaded": False}
        return {
            "id": self.current_model_name,
            "name": self.current_model_config["name"],
            "description": self.current_model_config["description"],
            "loaded": True
        }

    def _get_system_prompt(self, context: str = "general") -> str:
        """Get the appropriate system prompt based on context."""
        personality = """YOUR PERSONALITY:
- You are PREDICT — a fun, friendly, and knowledgeable car buddy! 🚗
- Talk like a cool, helpful friend who LOVES cars — not a boring robot.
- Use emojis naturally throughout your responses (🔧 ⚡ 🛞 🏎️ 💪 ✅ ⚠️ 🔥 etc.)
- Keep responses SHORT and punchy — no walls of text. Get to the point fast.
- Be encouraging and positive! If something is wrong with their car, don't panic them — explain it calmly with a plan.
- When explaining technical stuff, use simple everyday words. Compare car parts to things people know.

SMART REPLY RULES:
- VARY your responses! Never use the same opening, greeting, or structure twice. Be creative and natural.
- For simple messages like "thanks", "ok", "got it", "cool", "bye" — reply in 1 sentence max. Example: "You're welcome! 😊 Hit me up anytime!" Do NOT repeat vehicle info or greet them.
- Do NOT greet the user by name or mention their vehicle make/model UNLESS they are specifically asking about their car.
- Do NOT start every response with "Hey!" or "Hi there!" — mix up your openings. Sometimes jump straight to the answer.
- Each message is standalone — you have NO memory of previous messages. Do NOT say "as I mentioned" or "like we discussed".
- If the user just says hello or thanks, keep your reply to 1-2 SHORT sentences. Don't turn it into a pitch about what you can do.
- NEVER repeat the same phrase in a single response. If you catch yourself looping, stop and move on.
- Match the user's energy: short message = short reply. Long question = detailed answer.

TOPIC RULES:
- You ONLY talk about vehicles, cars, diagnostics, OBD-II codes, maintenance, repairs, driving, and car-related topics.
- If someone asks about anything NOT related to vehicles, say something like: "I'm all about cars! 🚗 Ask me anything about your ride — diagnostics, maintenance, repairs!"
- Always answer DTC code questions — that's your bread and butter!
- Sometimes you'll get web search results or vehicle research data as context — use it to give better answers but don't mention you received it.
- This app is used in Qatar and the Gulf region. Factor in: extreme heat (45°C+ summers 🌡️), dusty desert conditions, heavy AC load, faster wear on batteries/tyres/rubber seals.
- Use QAR (Qatari Riyal) for cost estimates unless the user says otherwise.
- Never make up part numbers or specific prices — give ranges instead.
- When Intelligence Analysis data is provided (patterns, trends, urgency), explain WHY the AI reached its conclusion. Mention specific sensor values, trend directions, and confidence levels. Frame it as "your car's data shows..." not "the system detected..."
- If urgency is CRITICAL, lead with the urgent finding and recommended action. If WARNING, mention it naturally. If GOOD, be reassuring."""

        if context == "customer":
            return f"""{personality}

You're chatting with a customer about their vehicle. Be extra warm and reassuring! If they're worried about a problem, calm them down and give them a clear action plan. 💪"""

        elif context == "technical":
            return f"""{personality}

The user wants more technical detail. Still be friendly but you can use proper technical terms — they can handle it! Mix in the fun personality with real diagnostic expertise. 🔧"""

        else:
            return f"""{personality}

Help the user understand their car's health and what it needs. Make diagnostics feel simple and approachable! 🏎️"""

    @staticmethod
    def _clean_response(text: str) -> str:
        """Remove Qwen3.5 thinking blocks and stray tokens."""
        # Remove complete <think>...</think> blocks
        text = _THINK_RE.sub("", text)
        # Remove unclosed <think> block (model ran out of tokens mid-think)
        if "<think>" in text and "</think>" not in text:
            text = text[:text.index("<think>")]
        for tok in STOP_TOKENS:
            text = text.replace(tok, "")
        # Remove any trailing partial assistant turn
        if "<|im_start|>" in text:
            text = text[:text.index("<|im_start|>")]
        return text.strip()

    def _build_context_str(self, context: Optional[Dict[str, Any]]) -> str:
        """Build context string from context dict. Shared by chat() and chat_stream()."""
        if not context:
            return ""

        context_parts = []
        if "vehicle" in context:
            v = context["vehicle"]
            parts = [f"{v.get('year')} {v.get('make')} {v.get('model')}"]
            if v.get("engine_type"):
                parts.append(v["engine_type"])
            if v.get("displacement"):
                parts.append(v["displacement"])
            context_parts.append(f"Vehicle: {' '.join(parts)}")
        if "dtcs" in context and context["dtcs"]:
            context_parts.append(f"Active DTCs: {', '.join(context['dtcs'])}")
        if "risk_score" in context:
            context_parts.append(f"Risk Score: {context['risk_score']:.2f}")
        if "data_freshness" in context:
            context_parts.append(context["data_freshness"])
        if "vehicle_research" in context:
            vr = context["vehicle_research"]
            vr_parts = []
            if vr.get("reliability_score") is not None:
                vr_parts.append(f"Reliability: {vr['reliability_score']}/10")
            if vr.get("common_problems"):
                vr_parts.append(f"Known problems: {', '.join(vr['common_problems'][:4])}")
            if vr.get("recalls"):
                vr_parts.append(f"Active recalls: {', '.join(vr['recalls'][:3])}")
            if vr.get("owner_reviews_summary"):
                vr_parts.append(f"Owner summary: {vr['owner_reviews_summary'][:250]}")
            if vr_parts:
                context_parts.append("Vehicle Research:\n" + "\n".join(vr_parts))
        if "health_assessment" in context:
            ha = context["health_assessment"]
            ha_parts = []
            if ha.get("health_score") is not None:
                ha_parts.append(f"Overall health score: {ha['health_score']}/100")
            if ha.get("components"):
                supported = []
                unsupported = []
                for cid, cdata in ha["components"].items():
                    if isinstance(cdata, dict):
                        if cdata.get("supported", True):
                            supported.append(f"{cid}: {cdata.get('health_pct', '?')}%")
                        else:
                            unsupported.append(cid.replace("_", " ").title())
                if supported:
                    ha_parts.append(f"Component health: {', '.join(supported[:8])}")
                if unsupported:
                    ha_parts.append(f"Components NOT supported by this vehicle (no sensor data): {', '.join(unsupported)}")
            if ha_parts:
                context_parts.append("Health Assessment:\n" + "\n".join(ha_parts))
        if "intelligence" in context:
            intel = context["intelligence"]
            intel_parts = []
            if intel.get("urgency"):
                u = intel["urgency"]
                intel_parts.append(f"Urgency: {u.get('level', 'UNKNOWN')} — {u.get('reason', '')}")
                if u.get("action"):
                    intel_parts.append(f"Recommended action: {u['action']}")
            if intel.get("patterns_detected"):
                for p in intel["patterns_detected"][:3]:
                    intel_parts.append(
                        f"Pattern: {p.get('display_name', p.get('name', '?'))} "
                        f"(confidence: {p.get('confidence', 0):.0%}, severity: {p.get('severity', '?')})\n"
                        f"  Reasoning: {p.get('reasoning', '')}\n"
                        f"  Recommendation: {p.get('recommendation', '')}"
                    )
            if intel.get("trends"):
                for t in intel["trends"][:3]:
                    intel_parts.append(
                        f"Trend: {t.get('sensor', '?')} — {t.get('message', '')}"
                    )
            if intel.get("causal_propagation"):
                for comp, chain in list(intel["causal_propagation"].items())[:3]:
                    if isinstance(chain, dict) and chain.get("is_root_cause"):
                        intel_parts.append(
                            f"Root cause: {comp} → affects {', '.join(chain.get('downstream_affected', []))}"
                        )
            if intel_parts:
                context_parts.append("Intelligence Analysis:\n" + "\n".join(intel_parts))
        if "vehicle_baseline" in context:
            vb = context["vehicle_baseline"]
            vb_parts = [f"Per-vehicle AI baseline (phase: {vb.get('phase', '?')}, {vb.get('data_points', 0)} data points, {vb.get('trip_count', 0)} trips):"]
            if vb.get("anomalies"):
                for a in vb["anomalies"][:5]:
                    vb_parts.append(f"  ANOMALY: {a.get('sensor', '?')} is {a.get('direction', '?')} baseline (current: {a.get('current', '?')}, normal: {a.get('baseline_mean', '?')}, z-score: {a.get('z_score', '?')})")
            if vb.get("trends"):
                for t in vb["trends"][:5]:
                    vb_parts.append(f"  TREND: {t.get('sensor', '?')} {t.get('direction', '?').replace('_', ' ')} ({t.get('slope_per_week', 0):+.3f}/week, recent avg: {t.get('recent_avg', '?')})")
            if not vb.get("anomalies") and not vb.get("trends"):
                vb_parts.append("  All sensors within learned baseline ranges.")
            context_parts.append("\n".join(vb_parts))
        if "dtc_forensics" in context:
            df = context["dtc_forensics"]
            df_parts = [f"DTC Forensic Analysis (severity: {df.get('overall_severity', '?').upper()}):"]
            if df.get("affected_components"):
                df_parts.append(f"  Affected systems: {', '.join(df['affected_components'])}")
            for hyp in (df.get("root_cause_hypotheses") or [])[:3]:
                conf = hyp.get("confidence", 0)
                df_parts.append(f"  Hypothesis: {hyp.get('hypothesis', '?')} (confidence: {conf:.0%})")
                for insp in (hyp.get("recommended_inspections") or [])[:2]:
                    df_parts.append(f"    → {insp}")
            for anom in (df.get("anomalies") or [])[:3]:
                df_parts.append(f"  Anomaly: {anom.get('message', '?')}")
            for cb in (df.get("correlation_breaks") or [])[:2]:
                pair = cb.get("pair", ["?", "?"])
                df_parts.append(
                    f"  Correlation break: {pair[0]} ↔ {pair[1]} "
                    f"(Δr={cb.get('delta', 0):.2f}, {cb.get('severity', '?')})"
                )
            if df.get("summary"):
                df_parts.append(f"  Summary: {df['summary']}")
            context_parts.append("\n".join(df_parts))
        if "survival_curves" in context:
            sc = context["survival_curves"]
            sc_parts = ["Survival Analysis (component remaining useful life):"]
            for curve in (sc if isinstance(sc, list) else [])[:5]:
                comp = curve.get("component", "?")
                probs = curve.get("survival_probability", [])
                days = curve.get("timeline_days", [])
                if probs and days and len(probs) > 1:
                    last_prob = probs[-1]
                    last_day = days[-1]
                    sc_parts.append(f"  {comp}: {last_prob:.0%} chance of lasting {last_day:.0f} more days")
            if len(sc_parts) > 1:
                context_parts.append("\n".join(sc_parts))
        if "web_search" in context:
            context_parts.append(f"Web Search Results:\n{context['web_search']}")

        context_str = ""
        if context_parts:
            context_str = "Context:\n" + "\n".join(context_parts) + "\n\n"

        # Inject conversation history as previous turns
        if "conversation_history" in context:
            history_lines = []
            for msg in context["conversation_history"][-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_lines.append(f"{'User' if role == 'user' else 'You'}: {content}")
            if history_lines:
                context_str += "Previous conversation:\n" + "\n".join(history_lines) + "\n\n"

        return context_str

    def chat(
        self,
        message: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Chat via Ollama HTTP API."""
        with self._lock:
            if not self.is_loaded:
                return "⚠️ Error: LLM model not loaded. Please wait for initialization."

            try:
                if system_prompt is None:
                    system_prompt = self._get_system_prompt("general")

                context_str = self._build_context_str(context)
                user_message = f"{context_str}{message}"

                resp = self._http_client.post("/api/chat", json={
                    "model": self.current_model_config["ollama_model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                        "stop": STOP_TOKENS
                    },
                    "stream": False,
                    "think": False
                }, timeout=120.0)

                if resp.status_code != 200:
                    logger.error(f"Ollama chat error: {resp.status_code} {resp.text}")
                    return f"❌ Ollama error: {resp.status_code}"

                data = resp.json()
                msg = data.get("message", {})
                raw = msg.get("content", "")
                # If content is empty but thinking exists, use thinking as fallback
                if not raw.strip() and msg.get("thinking"):
                    raw = msg["thinking"]
                return self._clean_response(raw)

            except Exception as e:
                logger.error(f"LLM chat error: {e}")
                return f"❌ Error generating response: {str(e)}"

    async def chat_async(
        self,
        message: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Async wrapper for chat."""
        return await asyncio.to_thread(self.chat, message, max_tokens, temperature, system_prompt, context)

    def chat_stream(
        self,
        message: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Iterator[str]:
        """Streaming chat via Ollama HTTP API."""
        with self._lock:
            if not self.is_loaded:
                yield "⚠️ Error: LLM model not loaded. Please wait for initialization."
                return

            try:
                if system_prompt is None:
                    system_prompt = self._get_system_prompt("general")

                context_str = self._build_context_str(context)
                user_message = f"{context_str}{message}"

                with self._http_client.stream("POST", "/api/chat", json={
                    "model": self.current_model_config["ollama_model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                        "stop": STOP_TOKENS
                    },
                    "stream": True,
                    "think": False
                }, timeout=120.0) as response:
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    yield token
                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue

            except Exception as e:
                logger.error(f"LLM streaming error: {e}")
                yield f"❌ Error generating response: {str(e)}"

    def count_tokens(self, text: str) -> int:
        """Estimate token count (roughly 4 chars per token for English)."""
        return len(text) // 4

    def get_context_window(self) -> int:
        """Get the context window size of the current model."""
        if self.current_model_config:
            return self.current_model_config.get("n_ctx", 4096)
        return 4096

    def get_load_time(self) -> Optional[float]:
        """Get the time taken to load the model in seconds."""
        if self.load_start_time and self.load_end_time:
            return self.load_end_time - self.load_start_time
        return None

    # ==================== DTC EXPLANATION ====================

    def explain_dtc(
        self,
        dtc_code: str,
        description: str,
        vehicle_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Explain DTC code with vehicle-specific context."""
        if not self.is_loaded:
            return "⚠️ LLM not loaded"

        vehicle_info = vehicle_info or {}

        prompt = f"""Hey! A user just got this code on their car. Help them understand it like a friendly car expert buddy. Use emojis! 🔧

DTC CODE: {dtc_code}
Description: {description}

VEHICLE: {vehicle_info.get('make', 'Unknown')} {vehicle_info.get('model', 'Unknown')} ({vehicle_info.get('year', 'Unknown')})
Mileage: {vehicle_info.get('mileage', 'Unknown')} km
Location: Qatar (extreme heat, dusty)

Reply with:
1. 💡 What this means in plain English (2 sentences max)
2. 🔍 Top 3 likely causes
3. 🌡️ Qatar heat/dust factor (1 sentence)
4. 💰 Rough cost range in QAR
5. ⚠️ Urgency: Critical / Warning / Info
6. 🚗 Safe to drive? Quick yes/no with note
7. ✅ What to do next

Keep it SHORT and friendly!"""

        return self.chat(prompt, max_tokens=600, temperature=0.2)

    async def explain_dtc_async(
        self,
        dtc_code: str,
        description: str,
        vehicle_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Async wrapper for explain_dtc."""
        return await asyncio.to_thread(self.explain_dtc, dtc_code, description, vehicle_info)

    # ==================== PREDICTION ANALYSIS ====================

    def analyze_prediction(
        self,
        prediction_data: Dict[str, Any],
        actual_outcome: Optional[Dict[str, Any]] = None,
        vehicle_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Analyze AI prediction accuracy and provide insights."""
        if not self.is_loaded:
            return "⚠️ LLM not loaded"

        vehicle_data = vehicle_data or {}

        if actual_outcome:
            prompt = f"""Analyze this AI prediction outcome:

PREDICTION:
Component: {prediction_data.get('component', 'Unknown')}
Failure Probability: {prediction_data.get('probability', 0)}%
Detected Patterns: {', '.join(prediction_data.get('patterns', []))}
Confidence: {prediction_data.get('confidence', 0)}%

ACTUAL OUTCOME:
Result: {actual_outcome.get('result', 'Unknown')}
Mechanic Notes: {actual_outcome.get('notes', 'None')}

VEHICLE:
{vehicle_data.get('make', '')} {vehicle_data.get('model', '')} ({vehicle_data.get('year', '')})
Mileage: {vehicle_data.get('mileage', 'Unknown')} km

Provide:
1. Was the prediction correct? Why or why not?
2. What patterns led to this prediction?
3. Root cause analysis (if prediction was wrong)
4. How to improve future predictions for this scenario
5. Customer-friendly explanation (for transparency)

Be analytical, honest about limitations, and constructive."""
        else:
            prompt = f"""Analyze this active AI prediction:

PREDICTION:
Component: {prediction_data.get('component', 'Unknown')}
Failure Probability: {prediction_data.get('probability', 0)}%
Time to Failure: {prediction_data.get('estimated_days', 'Unknown')} days
Detected Patterns: {', '.join(prediction_data.get('patterns', []))}
Confidence: {prediction_data.get('confidence', 0)}%

VEHICLE:
{vehicle_data.get('make', '')} {vehicle_data.get('model', '')} ({vehicle_data.get('year', '')})
Mileage: {vehicle_data.get('mileage', 'Unknown')} km

Provide:
1. Interpretation of detected patterns
2. Why these patterns indicate failure
3. Confidence assessment (is 85% confidence reliable here?)
4. Recommended verification steps
5. What to monitor closely
6. Customer communication template (professional, empathetic)

Be practical and actionable."""

        return self.chat(prompt, max_tokens=800, temperature=0.2)

    async def analyze_prediction_async(
        self,
        prediction_data: Dict[str, Any],
        actual_outcome: Optional[Dict[str, Any]] = None,
        vehicle_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Async wrapper for analyze_prediction."""
        return await asyncio.to_thread(self.analyze_prediction, prediction_data, actual_outcome, vehicle_data)

    # ==================== CUSTOMER SUPPORT ====================

    def generate_customer_response(
        self,
        complaint: str,
        context: Dict[str, Any]
    ) -> str:
        """Generate professional customer support response."""
        if not self.is_loaded:
            return "⚠️ LLM not loaded"

        prompt = f"""You are a professional customer support specialist for PREDICT AI.

CUSTOMER COMPLAINT:
{complaint}

CONTEXT:
Prediction: {context.get('prediction', 'N/A')}
Actual Issue: {context.get('actual_issue', 'N/A')}
Vehicle: {context.get('vehicle', 'N/A')}
Resolution: {context.get('resolution', 'N/A')}

Generate a professional email response that:
1. Acknowledges their concern with empathy
2. Explains what happened technically (simplified)
3. Shows the value they received (even if prediction was imperfect)
4. Offers solution or next steps
5. Thanks them for feedback (helps improve AI)

Tone: Professional, helpful, empathetic, not defensive
Length: 150-250 words
Sign off as: PREDICT Support Team"""

        return self.chat(prompt, max_tokens=400, temperature=0.3)

    async def generate_customer_response_async(
        self,
        complaint: str,
        context: Dict[str, Any]
    ) -> str:
        """Async wrapper for generate_customer_response."""
        return await asyncio.to_thread(self.generate_customer_response, complaint, context)

    def customer_chat(
        self,
        context: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Handle general customer chat with friendly tone."""
        system_prompt = self._get_system_prompt("customer")

        history_text = ""
        if chat_history and len(chat_history) > 0:
            history_text = "\n\nPrevious conversation:\n"
            for msg in chat_history[-6:]:
                role = "Customer" if msg.get("role") == "user" else "Assistant"
                history_text += f"{role}: {msg.get('content', '')}\n"

        prompt = f"""{context}
{history_text}
Respond helpfully and professionally. If they mention any car issues,
ask clarifying questions and let them know their concern will be forwarded
to the technician.

Keep responses concise (under 100 words).

Response:"""

        return self.chat(prompt, max_tokens=200, temperature=0.4, system_prompt=system_prompt)

    async def customer_chat_async(
        self,
        context: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Async wrapper for customer_chat."""
        return await asyncio.to_thread(self.customer_chat, context, chat_history)

    # ==================== PDF & SUMMARIZATION ====================

    def summarize_for_pdf(self, content: str, section_type: str = "general") -> str:
        """Generate concise PDF-friendly summary."""
        if not self.is_loaded:
            return content

        prompt = f"""Summarize the following automotive content for a PDF report.

Rules:
- Start with 3-5 bullet points (key findings only)
- Follow with 1-2 sentences of context
- Total output under 100 words
- Use simple, professional language
- Focus on actionable information
- No markdown headers, just bullets (use - or •) and text

Content to summarize:
{content}

Summary:"""

        try:
            return self.chat(prompt, max_tokens=200, temperature=0.2)
        except Exception as e:
            logger.error(f"PDF summarization error: {e}")
            return content

    async def summarize_for_pdf_async(self, content: str, section_type: str = "general") -> str:
        """Async wrapper for summarize_for_pdf."""
        return await asyncio.to_thread(self.summarize_for_pdf, content, section_type)

    # ==================== UTILITY METHODS ====================

    def suggest_training_data(
        self,
        accuracy_stats: Dict[str, Any],
        component: str
    ) -> str:
        """Analyze prediction accuracy and suggest training data improvements."""
        if not self.is_loaded:
            return "⚠️ LLM not loaded"

        prompt = f"""You are an AI/ML expert analyzing prediction model performance.

ACCURACY STATS:
{json.dumps(accuracy_stats, indent=2)}

FOCUS COMPONENT: {component}

Based on this data, suggest:
1. What specific training data to collect
2. How much data needed (estimate)
3. Which features to focus on
4. Edge cases to capture
5. Expected accuracy improvement

Be specific and quantitative."""

        return self.chat(prompt, max_tokens=500, temperature=0.2)

    def translate_to_arabic(self, english_text: str, context: str = "technical") -> str:
        """Translate technical content to Arabic."""
        if not self.is_loaded:
            return "⚠️ LLM not loaded"

        prompt = f"""Translate this automotive/technical text to Arabic (Qatar dialect when appropriate).

Context: {context}

English text:
{english_text}

Provide natural, professional Arabic translation suitable for Qatar. Use formal Arabic for technical terms, colloquial when appropriate for clarity."""

        return self.chat(prompt, max_tokens=400, temperature=0.2)

    async def translate_to_arabic_async(self, english_text: str, context: str = "technical") -> str:
        """Async wrapper for translate_to_arabic."""
        return await asyncio.to_thread(self.translate_to_arabic, english_text, context)

    # ==================== PARSING UTILITIES ====================

    def parse_failure_template(self, template_text: str) -> Dict[str, Any]:
        """Parse structured failure report template into data."""
        patterns = {
            'profile_name': r'Profile Name:\s*(.+)',
            'car_number': r'Car Number:\s*(.+)',
            'phone': r'Phone:\s*(.+)',
            'customer_issue': r'Customer Issue:\s*(.+)',
            'mechanic_analysis': r'Mechanic Analysis:\s*(.+)',
            'confirmed': r'Confirmed Failure:\s*(yes|no)',
            'ai_predicted': r'AI Predicted This:\s*(yes|no)',
            'date': r'Date:\s*(.+)',
            'notes': r'Notes:\s*(.+)'
        }

        result = {}
        for field, pattern in patterns.items():
            match = re.search(pattern, template_text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value.lower() not in ['yes/no', '[customer name]', '[vehicle id]',
                                         '[customer phone]', '[what customer thinks is wrong]',
                                         '[actual diagnosis]', '[yyyy-mm-dd]', '[optional notes]']:
                    result[field] = value
                else:
                    result[field] = None
            else:
                result[field] = None

        result['confirmed'] = result.get('confirmed', '').lower() == 'yes' if result.get('confirmed') else False
        result['ai_predicted'] = result.get('ai_predicted', '').lower() == 'yes' if result.get('ai_predicted') else False

        return result

    def is_failure_template(self, text: str) -> bool:
        """Check if the text is a failure report template."""
        return "---FAILURE REPORT---" in text and "---END REPORT---" in text

    # ==================== HEALTH SUMMARY ====================

    def get_health_summary(self, vehicle_data: Dict[str, Any]) -> str:
        """Generate a health summary for a vehicle."""
        risk = vehicle_data.get("risk_score", 0.5)

        if risk < 0.3:
            status = "healthy"
        elif risk < 0.6:
            status = "monitor"
        else:
            status = "attention_needed"

        messages = {
            "healthy": "Your vehicle appears to be in good health. Continue regular maintenance.",
            "monitor": "Your vehicle shows some signs of wear. Monitor closely and consider inspection.",
            "attention_needed": "Your vehicle needs attention. Please schedule a diagnostic check soon.",
        }

        return messages.get(status, messages["healthy"])

    def is_available(self) -> bool:
        """Check if LLM is available and loaded."""
        return self.is_loaded


# Global singleton instance
_llm_instance: Optional[LLMAssistant] = None
_lock = threading.Lock()


def get_llm_assistant() -> LLMAssistant:
    """Get or create the global LLM assistant instance (thread-safe)."""
    global _llm_instance
    if _llm_instance is None:
        with _lock:
            if _llm_instance is None:
                _llm_instance = LLMAssistant()
    return _llm_instance


async def ensure_llm_loaded() -> LLMAssistant:
    """Get the LLM assistant and ensure the model is loaded (async-safe)."""
    assistant = get_llm_assistant()
    if not assistant.is_loaded:
        logger.info("Loading LLM model via Ollama (first request)...")
        await assistant.load_model_async("qwen")
    return assistant


def reset_llm_assistant() -> None:
    """Reset the global LLM assistant instance."""
    global _llm_instance
    with _lock:
        if _llm_instance is not None:
            _llm_instance._unload_current_model()
            _llm_instance = None


# ========================================================
# Haiku Diagnostic Reasoner (separate from Qwen chat)
# ========================================================

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
HAIKU_MODEL = "claude-haiku-4-5-20251001"


async def diagnostic_reasoning(
    vehicle_info: dict,
    component_scores: dict,
    sensor_readings: dict,
    driving_context: str,
    research_data: dict = None,
    baseline_data: dict = None,
    dtc_codes: list = None,
    service_records: list = None,
) -> Optional[dict]:
    """Call Claude Haiku for cross-component diagnostic reasoning.

    Returns: {agreements, disagreements, cross_patterns, known_issue_flags,
              overall_rating, owner_summary} or None on failure.
    """
    if not ANTHROPIC_API_KEY:
        logger.info("No ANTHROPIC_API_KEY — skipping Haiku diagnostic reasoning")
        return None

    prompt = _build_diagnostic_prompt(
        vehicle_info, component_scores, sensor_readings,
        driving_context, research_data, baseline_data, dtc_codes, service_records
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": HAIKU_MODEL,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["content"][0]["text"]

            # Parse JSON response from Haiku
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
    except Exception as e:
        logger.warning(f"Haiku diagnostic reasoning failed: {e}")
        return None


def _build_diagnostic_prompt(
    vehicle_info: dict,
    component_scores: dict,
    sensor_readings: dict,
    driving_context: str,
    research_data: dict,
    baseline_data: dict,
    dtc_codes: list,
    service_records: list,
) -> str:
    """Build the diagnostic reasoning prompt."""
    year = vehicle_info.get("year", "?")
    make = vehicle_info.get("make", "?")
    model = vehicle_info.get("model", "?")
    engine = vehicle_info.get("engine_type", "")
    disp = vehicle_info.get("displacement", "")
    mileage = vehicle_info.get("mileage_km", "unknown")

    lines = [
        f"You are an automotive diagnostic AI analyzing OBD-II data for a {year} {make} {model} ({engine} {disp}).",
        f"Estimated mileage: {mileage}km. Climate: Qatar (extreme heat, 45°C+ summers, desert dust).",
        "",
        f"CURRENT SENSOR READINGS (context: {driving_context}):",
    ]
    for sensor, value in sensor_readings.items():
        if isinstance(value, (int, float)):
            lines.append(f"  {sensor}: {value}")

    lines.append("")
    lines.append("ENGINE SCORES FROM RULE ENGINE:")
    for comp, data in component_scores.items():
        tier = data.get("confidence_tier", "?")
        reason = data.get("reason", "")
        score = data.get("health_pct", 100)
        lines.append(f"  {comp}: {score}% [{tier}] — \"{reason}\"")

    if research_data:
        lines.append("")
        lines.append("VEHICLE RESEARCH (make/model known issues):")
        lines.append(f"  Reliability: {research_data.get('reliability_score', '?')}/10")
        common = research_data.get("common_problems", [])
        if common:
            lines.append(f"  Known problems: {', '.join(str(p) for p in common[:5])}")

    if dtc_codes:
        dtc_strs = [d.get("code", str(d)) if isinstance(d, dict) else str(d) for d in dtc_codes]
        lines.append(f"\nACTIVE DTCs: {', '.join(dtc_strs)}")
    else:
        lines.append("\nACTIVE DTCs: none")

    if service_records:
        lines.append("\nSERVICE HISTORY:")
        for sr in service_records[:5]:
            if isinstance(sr, dict):
                lines.append(f"  {sr.get('date', '?')}: {sr.get('type', '?')} at {sr.get('mileage', '?')}km")

    lines.append("")
    lines.append("TASKS:")
    lines.append("1. For each component, state if you AGREE or DISAGREE with the score. If disagree, explain with engineering reasoning.")
    lines.append("2. Identify cross-component patterns the rule engine may have missed.")
    lines.append("3. Check if any make/model known issues apply to the current sensor data.")
    lines.append("4. Rate overall condition: EXCELLENT / GOOD / FAIR / ATTENTION_NEEDED / CRITICAL")
    lines.append("5. Provide a 2-sentence plain-language summary for the car owner.")
    lines.append("")
    lines.append('Respond in JSON: {"agreements": [], "disagreements": [{"component": "...", "engine_score": 0, "haiku_opinion": 0, "reasoning": "..."}], "cross_patterns": [], "known_issue_flags": [], "overall_rating": "...", "owner_summary": "..."}')

    return "\n".join(lines)
