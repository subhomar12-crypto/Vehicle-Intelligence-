"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Simple
"""

from llama_cpp import Llama
import sys
from pathlib import Path

# Determine model path
try:
    # Add parent directory to path for config import
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    CONFIG = get_config()
    MODEL_PATH = str(CONFIG.ROOT_DIR / "models" / "Qwen2.5-7B-Instruct-Q5_K_M.gguf")
except ImportError:
    CONFIG = None
    MODEL_PATH = str(Path(__file__).parent / "Qwen2.5-7B-Instruct-Q5_K_M.gguf")

print("Loading model...")
print(f"Model path: {MODEL_PATH}")

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,  # Smaller context
    n_threads=4,  # Fewer threads
    verbose=True  # Show what's happening
)

print("\n✓ Model loaded! Testing...")

response = llm(
    "Say hello",
    max_tokens=50
)

print("\nResponse:", response['choices'][0]['text'])
