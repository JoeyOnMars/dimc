#!/usr/bin/env python3
"""
真实内存测量：使用 macOS `memory_pressure` / `ps` 测量全量内存
包括 MPS (Apple Silicon GPU) 统一内存
"""

import gc
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PID = os.getpid()


def get_real_memory_mb():
    """用 ps 获取 RSS (Resident Set Size)"""
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(PID)], capture_output=True, text=True)
    rss_kb = int(result.stdout.strip())
    return rss_kb / 1024


def get_footprint_mb():
    """用 macOS footprint 获取真实全量内存 (含 GPU/IOKit)"""
    try:
        result = subprocess.run(
            ["footprint", "-p", str(PID), "--skip-aggregation"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # 解析 footprint 输出寻找 total
        for line in result.stdout.split("\n"):
            if "total:" in line.lower() or "ALL" in line:
                return line.strip()
        return result.stdout[:500]
    except Exception as e:
        return f"footprint 不可用: {e}"


def get_vm_tracker():
    """用 vmmap 获取详细内存映射摘要"""
    try:
        result = subprocess.run(
            ["vmmap", "--summary", str(PID)], capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.split("\n")
        # 找 TOTAL 和 IOKit 行
        relevant = []
        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["total", "iokit", "neural", "gpu", "metal", "cg image"]):
                relevant.append(line.strip())
        return "\n".join(relevant) if relevant else "无相关行"
    except Exception as e:
        return f"vmmap 不可用: {e}"


def measure(label):
    rss = get_real_memory_mb()
    print(f"\n{'─' * 50}")
    print(f"[{label}]")
    print(f"  ps RSS: {rss:.1f} MB")
    print("  vmmap summary (含 GPU/IOKit):")
    vm = get_vm_tracker()
    for line in vm.split("\n"):
        print(f"    {line}")
    print(f"{'─' * 50}")
    return rss


def main():
    print("=" * 60)
    print(f"PID: {PID}")
    print("真实内存测量 (macOS 系统工具)")
    print("=" * 60)

    # Baseline
    measure("0. Baseline (空进程)")

    # Phase 1: Load Embedding
    print("\n>>> 加载 Embedding 模型 (BGE-M3)...")
    from dimcause.core.chunking import Chunk
    from dimcause.storage.vector_store import VectorStore

    vs = VectorStore()
    test_chunks = [
        Chunk(event_id="test-001", seq=0, pos=0, text="重构了 CLI 模块", token_count=10),
    ]
    embeddings = vs.embed_chunks(test_chunks)
    print(f"  Embedding 完成, 维度: {embeddings[0].shape}")
    measure("1. Embedding 已加载 (模型在内存中)")

    # Phase 2: 尝试释放
    print("\n>>> 尝试释放 Embedding 模型...")
    if hasattr(vs, "_st_model") and vs._st_model is not None:
        # 移到 CPU 再删除 (有时能帮助释放 MPS 内存)
        try:
            vs._st_model = vs._st_model.to("cpu")
        except Exception:
            pass
        del vs._st_model
        vs._st_model = None
    gc.collect()
    try:
        import torch

        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
            torch.mps.synchronize()
    except Exception:
        pass
    time.sleep(1)  # 给系统时间回收
    measure("2. Embedding 释放后")

    # Phase 3: Load Reranker
    print("\n>>> 加载 Reranker 模型 (BGE-Reranker-V2-M3)...")
    from dimcause.search.reranker import get_reranker

    reranker = get_reranker()
    if reranker._model:
        print("  Reranker 加载成功")
    measure("3. Reranker 已加载")

    # Phase 4: 两个同时加载 (危险测试)
    print("\n>>> 重新加载 Embedding (两个模型将同时存在!)...")
    from sentence_transformers import SentenceTransformer

    snapshot = os.path.expanduser(
        "~/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
    )
    embed_model = SentenceTransformer(snapshot)
    _ = embed_model.encode(["测试"], convert_to_numpy=True)  # 确保真正加载到 GPU
    measure("4. 两个模型同时加载 (峰值)")

    print(f"\n{'=' * 60}")
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
