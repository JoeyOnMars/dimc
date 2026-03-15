#!/usr/bin/env python3
"""
端到端测试：Embedding -> Search -> Reranker 全流程
重点关注：
1. 模型是否成功加载（本地）
2. 内存使用情况
3. 两个模型之间的内存释放策略
"""

import gc
import os
import resource  # macOS/Linux only
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def get_memory_mb():
    """获取当前进程的 RSS 内存使用量 (MB)"""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS: ru_maxrss is in bytes
    return usage.ru_maxrss / (1024 * 1024)


def get_current_rss_mb():
    """获取当前 RSS (非高峰值)"""
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback: 使用 resource 模块 (只能获取 peak)
        return get_memory_mb()


def main():
    print("=" * 60)
    print("DIMCAUSE 端到端模型测试 (Embedding + Reranker)")
    print("=" * 60)

    mem_baseline = get_current_rss_mb()
    print(f"\n[0] Baseline Memory: {mem_baseline:.1f} MB")

    # ============================================================
    # Phase 1: Embedding (VectorStore)
    # ============================================================
    print(f"\n{'─' * 40}")
    print("[Phase 1] Embedding 模型加载与测试")
    print(f"{'─' * 40}")

    from dimcause.core.chunking import Chunk
    from dimcause.storage.vector_store import VectorStore

    vs = VectorStore()
    print(f"    DB Path: {vs.db_path}")

    # 创建测试 Chunks
    test_chunks = [
        Chunk(
            event_id="test-001",
            seq=0,
            pos=0,
            text="重构了 CLI 模块，将命令行参数解析从 argparse 迁移到 click 框架",
            token_count=30,
        ),
        Chunk(
            event_id="test-001",
            seq=1,
            pos=1,
            text="修复了 Git importer 中的 UTF-8 解码错误，添加了 errors='replace' 参数",
            token_count=35,
        ),
        Chunk(
            event_id="test-002",
            seq=0,
            pos=0,
            text="实现了基于 NetworkX 的因果图存储，支持 BFS 遍历查询邻居节点",
            token_count=30,
        ),
    ]

    print(f"    Embedding {len(test_chunks)} chunks...")
    try:
        embeddings = vs.embed_chunks(test_chunks)
        print("    ✅ Embedding 成功！")
        print(f"    - 向量数量: {len(embeddings)}")
        print(
            f"    - 向量维度: {embeddings[0].shape if hasattr(embeddings[0], 'shape') else len(embeddings[0])}"
        )
    except Exception as e:
        print(f"    ❌ Embedding 失败: {e}")
        import traceback

        traceback.print_exc()
        return

    mem_after_embed = get_current_rss_mb()
    print(
        f"    Memory after Embedding: {mem_after_embed:.1f} MB (+{mem_after_embed - mem_baseline:.1f} MB)"
    )

    # ============================================================
    # Phase 1.5: 释放 Embedding 模型
    # ============================================================
    print(f"\n{'─' * 40}")
    print("[Phase 1.5] 释放 Embedding 模型以节省内存")
    print(f"{'─' * 40}")

    if hasattr(vs, "_st_model") and vs._st_model is not None:
        print("    释放 SentenceTransformer 模型...")
        del vs._st_model
        vs._st_model = None
        gc.collect()

        # 如果 MPS (Apple Silicon) 或 CUDA，尝试清理 GPU 缓存
        try:
            import torch

            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
                print("    MPS cache cleared.")
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        mem_after_release = get_current_rss_mb()
        print(
            f"    Memory after release: {mem_after_release:.1f} MB (freed ~{mem_after_embed - mem_after_release:.1f} MB)"
        )
    else:
        print("    ⚠️ No model to release (was it loaded?)")
        mem_after_release = mem_after_embed

    # ============================================================
    # Phase 2: Reranker
    # ============================================================
    print(f"\n{'─' * 40}")
    print("[Phase 2] Reranker 模型加载与测试")
    print(f"{'─' * 40}")

    from datetime import datetime

    from dimcause.core.models import Event, EventType
    from dimcause.search.reranker import get_reranker

    reranker = get_reranker()

    if not reranker._model:
        print("    ❌ Reranker 模型未加载！测试中止。")
        return

    mem_after_reranker = get_current_rss_mb()
    print(
        f"    Memory after Reranker load: {mem_after_reranker:.1f} MB (+{mem_after_reranker - mem_after_release:.1f} MB)"
    )

    # 创建测试 Events (使用正确的字段名)
    test_events = [
        Event(
            id="evt-001",
            timestamp=datetime.now(),
            type=EventType.CODE_CHANGE,
            summary="重构 CLI 模块迁移到 click",
            content="将 CLI 从 argparse 迁移到 click 框架，改善了命令行参数处理和帮助信息生成。",
        ),
        Event(
            id="evt-002",
            timestamp=datetime.now(),
            type=EventType.CODE_CHANGE,
            summary="修复 Git importer UTF-8 错误",
            content="在 Git importer 的文件读取中添加了 errors='replace'，解决了二进制文件导致的 UnicodeDecodeError。",
        ),
        Event(
            id="evt-003",
            timestamp=datetime.now(),
            type=EventType.DECISION,
            summary="决定使用 NetworkX 作为图存储后端",
            content="经过评估，选择 NetworkX 而非 Neo4j，因为项目规模较小，嵌入式方案更合适。",
        ),
    ]

    query = "CLI 重构"
    print(f"    Query: '{query}'")
    print(f"    Candidates: {len(test_events)} events")

    try:
        ranked = reranker.rank(query, test_events, top_k=3)
        print("    ✅ Rerank 成功！")
        print("    排序结果:")
        for i, event in enumerate(ranked):
            print(f"      #{i + 1}: [{event.type.value}] {event.summary}")
    except Exception as e:
        print(f"    ❌ Rerank 失败: {e}")
        import traceback

        traceback.print_exc()
        return

    # ============================================================
    # Phase 3: 汇总
    # ============================================================
    mem_final = get_current_rss_mb()
    mem_peak = get_memory_mb()

    print(f"\n{'=' * 60}")
    print("内存报告")
    print(f"{'=' * 60}")
    print(f"  Baseline:          {mem_baseline:.1f} MB")
    print(f"  After Embedding:   {mem_after_embed:.1f} MB (+{mem_after_embed - mem_baseline:.1f})")
    print(f"  After Release:     {mem_after_release:.1f} MB")
    print(f"  After Reranker:    {mem_after_reranker:.1f} MB")
    print(f"  Final:             {mem_final:.1f} MB")
    print(f"  Peak RSS:          {mem_peak:.1f} MB")
    print(f"{'=' * 60}")
    print("✅ 端到端测试完成！")


if __name__ == "__main__":
    main()
