"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Download Model
"""

from huggingface_hub import hf_hub_download
import os
import sys
from pathlib import Path

# Determine models directory
try:
    # Add parent directory to path for config import
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config
    CONFIG = get_config()
    MODELS_DIR = str(CONFIG.ROOT_DIR / "models")
except ImportError:
    CONFIG = None
    MODELS_DIR = str(Path(__file__).parent)

print("=" * 60)
print("Downloading Qwen 2.5 7B Model")
print("Size: ~5GB | Time: 10-30 minutes")
print("=" * 60)
print()

os.makedirs(MODELS_DIR, exist_ok=True)

try:
    print("Starting download...")
    print(f"Target directory: {MODELS_DIR}")

    model_path = hf_hub_download(
        repo_id="bartowski/Qwen2.5-7B-Instruct-GGUF",
        filename="Qwen2.5-7B-Instruct-Q5_K_M.gguf",
        local_dir=MODELS_DIR
    )

    print()
    print("=" * 60)
    print("✅ SUCCESS! Qwen 2.5 7B downloaded!")
    print(f"Location: {model_path}")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Error: {e}")
