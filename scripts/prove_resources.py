#!/usr/bin/env python3
"""
验证脚本：证明 VectorStore 使用的是本地模型和正确的数据库路径。
"""

import logging
import os
import sys

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加 src 到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from dimcause.core.chunking import Chunk  # noqa: E402
from dimcause.storage.vector_store import VectorStore  # noqa: E402


def prove_resources():
    print(f"\n{'=' * 50}")
    print("RESOURCE PROOF CHECK")
    print(f"{'=' * 50}")

    # 1. 初始化 VectorStore (使用默认配置)
    print("\n[1] Initializing VectorStore (Default Config)...")
    vs = VectorStore()

    print(f"    - Database Path: {vs.db_path}")
    if "index.db" in str(vs.db_path) and "test" not in str(vs.db_path):
        print("    ✅ CONFIRMED: Using Production DB Path")
    else:
        print("    ⚠️ WARNING: Using Non-Standard DB Path")

    # 2. 验证 Embedding 模型加载
    print("\n[2] Loading Embedding Model (Triggering Lazy Load)...")
    # 创建个 dummy chunk 触发 embed_chunks
    dummy_chunk = Chunk(
        event_id="proof_check", seq=0, pos=0, text="Proof of concept", token_count=3
    )

    # 捕获 stdout/stderr 或者直接检查内部属性
    try:
        vs.embed_chunks([dummy_chunk])

        model = vs._st_model
        if model:
            print(f"    - Model Loaded: {type(model).__name__}")
            # 尝试获取模型路径
            if hasattr(model, "tokenizer") and hasattr(model.tokenizer, "name_or_path"):
                print(f"    - Tokenizer Path: {model.tokenizer.name_or_path}")
                if "/Users/mini/.cache/huggingface" in model.tokenizer.name_or_path:
                    print("    ✅ CONFIRMED: Using Local HuggingFace Cache")
                else:
                    print(f"    ℹ️ Info: Model path is {model.tokenizer.name_or_path}")
            else:
                print(f"    - Model object check: {model}")
        else:
            print("    ❌ FAILED: Model not loaded")

    except Exception as e:
        print(f"    ❌ FAILED: Error during embedding: {e}")

    print("\n[3] Loading Reranker Model...")
    try:
        from dimcause.search.reranker import get_reranker

        reranker = get_reranker()
        if reranker._model:
            print(f"    - Reranker Loaded: {type(reranker._model).__name__}")
            # CrossEncoder 通常也有同样的属性
            if hasattr(reranker._model, "tokenizer") and hasattr(
                reranker._model.tokenizer, "name_or_path"
            ):
                print(f"    - Tokenizer Path: {reranker._model.tokenizer.name_or_path}")
                if "/Users/mini/.cache/huggingface" in reranker._model.tokenizer.name_or_path:
                    print("    ✅ CONFIRMED: Using Local HuggingFace Cache")
            else:
                print("    ℹ️ Info: Reranker path check inconclusive")
        else:
            print("    ❌ FAILED: Reranker not loaded (maybe disabled?)")
    except Exception as e:
        print(f"    ❌ FAILED: Error loading reranker: {e}")

    print(f"\n{'=' * 50}")
    print("END PROOF")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    prove_resources()
