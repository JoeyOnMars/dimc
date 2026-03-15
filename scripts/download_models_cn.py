#!/usr/bin/env python3
"""
下载/修复 Dimcause 所需的 AI 模型 (专为中国大陆网络环境优化)
Uses https://hf-mirror.com to avoid GFW issues.
"""

import os
import sys

# 1. 设置 HuggingFace 镜像 (CRITICAL for China)
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("Error: huggingface_hub not installed. Please install it via pip.")
    sys.exit(1)

MODELS = [
    # Reranker (Found corrupted/incomplete in previous check)
    "BAAI/bge-reranker-v2-m3",
    # Embedding (Already verified as good, but good to ensure consistency)
    "BAAI/bge-m3",
]


def download_models():
    print(f"Using Mirror: {os.environ['HF_ENDPOINT']}")

    for model_id in MODELS:
        print(f"\n[{model_id}] Checking/Downloading...")
        try:
            local_path = snapshot_download(
                repo_id=model_id,
                resume_download=True,
                local_files_only=False,  # We WANT to go online to fix it
            )
            print(f"✅ Success: {local_path}")

            # Verify critical files exist
            files = os.listdir(local_path)
            critical_files = ["config.json", "pytorch_model.bin"]  # or model.safetensors
            found = [
                f
                for f in files
                if f in critical_files or f.endswith(".safetensors") or f.endswith(".bin")
            ]

            if len(found) < 2:
                print(f"⚠️  Warning: Model directory seems weirdly empty. Found: {files}")
            else:
                print(f"    Verified files: {len(found)} critical files present.")

        except Exception as e:
            print(f"❌ Failed: {e}")


if __name__ == "__main__":
    download_models()
