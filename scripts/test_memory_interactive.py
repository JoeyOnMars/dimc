#!/usr/bin/env python3
"""
交互式内存测试：四阶段，每阶段暂停等待用户检查 Activity Monitor
"""

import gc
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PID = os.getpid()
print(f"PID: {PID}  ← 在活动监视器中搜索这个进程号")
print("进程名称: Python")
print()

# ===================== Phase 1 =====================
input("按 Enter 开始加载 Embedding 模型 (BGE-M3)...")
print(">>> 正在加载 Embedding...")
from sentence_transformers import SentenceTransformer  # noqa: E402

snapshot = os.path.expanduser(
    "~/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/"
    "5617a9f61b028005a4858fdac845db406aefb181"
)
embed_model = SentenceTransformer(snapshot)
# 执行一次推理，确保权重真正进入 MPS
_ = embed_model.encode(["确保模型完全加载到 GPU"], convert_to_numpy=True)
print()
print("=" * 50)
print("✅ 阶段 1：Embedding 已加载")
print("   → 去活动监视器看内存")
print("=" * 50)

# ===================== Phase 2 =====================
input("\n按 Enter 加载 Reranker (此时两个模型将同时在内存中)...")
print(">>> 正在加载 Reranker...")
from sentence_transformers import CrossEncoder  # noqa: E402

reranker_path = os.path.expanduser(
    "~/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/snapshots/"
    "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
)
reranker_model = CrossEncoder(reranker_path, max_length=512, local_files_only=True)
# 执行一次推理
_ = reranker_model.predict([["测试查询", "测试文档"]])
print()
print("=" * 50)
print("✅ 阶段 2：Embedding + Reranker 同时在内存中")
print("   → 去活动监视器看内存 (应该是峰值)")
print("=" * 50)

# ===================== Phase 3 =====================
input("\n按 Enter 释放 Reranker...")
print(">>> 正在释放 Reranker...")
try:
    import torch

    # 把模型移回 CPU 再删除
    reranker_model.model = reranker_model.model.to("cpu")
except Exception:
    pass
del reranker_model
gc.collect()
try:
    import torch

    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
        torch.mps.synchronize()
except Exception:
    pass
time.sleep(2)
print()
print("=" * 50)
print("✅ 阶段 3：Reranker 已释放，仅 Embedding 在内存中")
print("   → 去活动监视器看内存 (应该下降)")
print("=" * 50)

# ===================== Phase 4 =====================
input("\n按 Enter 释放 Embedding...")
print(">>> 正在释放 Embedding...")
try:
    embed_model = embed_model.to("cpu")
except Exception:
    pass
del embed_model
gc.collect()
try:
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
        torch.mps.synchronize()
except Exception:
    pass
time.sleep(2)
print()
print("=" * 50)
print("✅ 阶段 4：全部释放")
print("   → 去活动监视器看内存 (应该回到 baseline)")
print("=" * 50)

input("\n按 Enter 退出...")
print("结束。")
