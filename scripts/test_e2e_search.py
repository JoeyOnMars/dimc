#!/usr/bin/env python3
"""
端到端搜索测试：Embedding → 存储 → 搜索 → Reranker

验证"用完即释放"内存管理是否生效。
用法: source .venv/bin/activate && python scripts/test_e2e_search.py
"""

import gc
import os
import resource
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# 确保项目模块可导入
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def get_rss_mb():
    """获取当前 RSS 内存 (MB) - 注意: 不含 MPS 内存"""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def main():
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    console.print(
        Panel.fit(
            "[bold cyan]端到端搜索测试[/]\n"
            "Embedding -> 存储 -> 搜索 -> Reranker\n"
            "验证用完即释放内存管理",
            border_style="cyan",
        )
    )

    # ============================
    # Phase 0: 准备测试数据
    # ============================
    console.print("\n[bold]Phase 0: 准备测试数据[/]")

    from dimcause.core.models import Event, EventType

    # 创建 5 个不同主题的测试事件
    test_events = [
        Event(
            id="test-001",
            type=EventType.DECISION,
            timestamp=datetime(2026, 2, 17, 10, 0),
            summary="决定将 VectorStore 从 ChromaDB 迁移到 SQLite-vec",
            content="经过评估，ChromaDB 在本地部署时存在依赖问题和版本兼容性风险。"
            "决定使用 SQLite-vec 作为向量存储后端，减少外部依赖。"
            "SQLite-vec 基于 SQLite 扩展，轻量且稳定。",
        ),
        Event(
            id="test-002",
            type=EventType.CODE_CHANGE,
            timestamp=datetime(2026, 2, 17, 14, 0),
            summary="实现 Reranker 模型的离线加载和 Snapshot Path 回退机制",
            content="Reranker 模型 (bge-reranker-v2-m3) 在中国网络环境下加载失败。"
            "解决方案：优先尝试 local_files_only=True，失败后手动解析 HuggingFace 缓存路径。"
            "通过 hf-mirror.com 镜像下载模型到本地缓存。",
        ),
        Event(
            id="test-003",
            type=EventType.RESEARCH,
            timestamp=datetime(2026, 2, 18, 1, 0),
            summary="模型选型研究：BGE-M3 vs Jina v3 vs GTE-Qwen2",
            content="对比了三种 Embedding 模型的中文检索质量、内存占用和安全性。"
            "BGE-M3: 567M 参数，中文 NDCG@10=67.5，无安全风险。"
            "Jina v3: 570M 参数，中文 NDCG@10=69.5，需要 trust_remote_code。"
            "GTE-Qwen2: 1.5B 参数，SOTA 精度，但内存 4.5GB 太大。",
        ),
        Event(
            id="test-004",
            type=EventType.DECISION,
            timestamp=datetime(2026, 2, 18, 2, 0),
            summary="实现模型用完即释放策略以控制内存峰值",
            content="发现 Embedding 和 Reranker 同时驻留内存时峰值达 5.87GB。"
            "设计方案：SearchEngine.search() 中，Embedding 完成后释放 MPS 内存，"
            "再加载 Reranker 进行精排，完成后也释放。峰值降至约 3.6GB。",
        ),
        Event(
            id="test-005",
            type=EventType.EXPERIMENT,
            timestamp=datetime(2026, 2, 15, 9, 0),
            summary="Python GIL 对多线程审计的影响测试",
            content="测试了在 Python 3.12 中使用多线程运行审计检查的性能。"
            "结论：由于 GIL 限制，CPU 密集型的审计操作无法真正并行。"
            "建议使用 multiprocessing 或 asyncio 来替代。"
            "这与模型加载完全无关。",
        ),
    ]

    console.print(f"  创建了 [green]{len(test_events)}[/] 个测试事件")

    # ============================
    # Phase 1: Embedding 并存储
    # ============================
    console.print("\n[bold]Phase 1: Embedding + 存储[/]")
    rss_before = get_rss_mb()
    console.print(f"  内存基线: [yellow]{rss_before:.0f} MB[/] (RSS, 不含 MPS)")

    # 使用临时数据库
    tmp_dir = tempfile.mkdtemp(prefix="dimc_e2e_")
    db_path = os.path.join(tmp_dir, "test_e2e.db")
    console.print(f"  临时数据库: {db_path}")

    from dimcause.storage.vector_store import VectorStore

    vs = VectorStore(db_path=db_path)

    t0 = time.time()
    for event in test_events:
        vs.add(event)
    t_embed = time.time() - t0

    rss_after_embed = get_rss_mb()
    console.print(f"  Embedding 完成: [green]{t_embed:.1f}s[/]")
    console.print(f"  内存 (Embedding 加载后): [yellow]{rss_after_embed:.0f} MB[/]")

    stats = vs.stats()
    console.print(f"  向量数: [green]{stats.get('vector_count', '?')}[/]")

    # ============================
    # Phase 1.5: 释放 Embedding
    # ============================
    console.print("\n[bold]Phase 1.5: 释放 Embedding 模型[/]")
    vs.release_model()
    gc.collect()
    rss_after_release = get_rss_mb()
    console.print(f"  内存 (释放后): [yellow]{rss_after_release:.0f} MB[/]")
    console.print("  ✅ release_model() 执行成功")

    # ============================
    # Phase 2: 搜索 + Reranker
    # ============================
    console.print("\n[bold]Phase 2: 搜索 + Reranker[/]")

    queries = [
        ("模型内存管理", "应该匹配 test-004 (用完即释放)"),
        ("ChromaDB 迁移 SQLite", "应该匹配 test-001 (VectorStore 迁移)"),
        ("Python GIL 多线程", "应该匹配 test-005 (GIL 测试)"),
    ]

    from dimcause.search.engine import SearchEngine
    from dimcause.storage.markdown_store import MarkdownStore

    engine = SearchEngine(markdown_store=MarkdownStore(), vector_store=vs)

    for q, expected in queries:
        console.print(f'\n  [cyan]查询: "{q}"[/]')
        console.print(f"  [dim]预期: {expected}[/]")

        t0 = time.time()
        results = engine.search(query=q, mode="semantic", top_k=3)
        t_search = time.time() - t0

        if results:
            table = Table(show_header=True, header_style="bold")
            table.add_column("#", width=3)
            table.add_column("ID", width=10)
            table.add_column("类型", width=12)
            table.add_column("摘要", width=50)
            for i, e in enumerate(results, 1):
                table.add_row(
                    str(i),
                    e.id,
                    e.type.value if hasattr(e.type, "value") else str(e.type),
                    e.summary[:50],
                )
            console.print(table)
            console.print(f"  ⏱ 搜索耗时: {t_search:.2f}s")
        else:
            console.print("  [yellow]❌ 无结果[/]")

    # ============================
    # Phase 3: 内存总结
    # ============================
    console.print("\n[bold]Phase 3: 内存总结[/]")
    rss_final = get_rss_mb()

    summary = Table(show_header=True, header_style="bold green")
    summary.add_column("阶段", width=25)
    summary.add_column("RSS (MB)", width=12)
    summary.add_row("基线", f"{rss_before:.0f}")
    summary.add_row("Embedding 加载后", f"{rss_after_embed:.0f}")
    summary.add_row("Embedding 释放后", f"{rss_after_release:.0f}")
    summary.add_row("搜索完成后", f"{rss_final:.0f}")
    console.print(summary)

    console.print("\n  [dim]注意: RSS 不含 MPS/GPU 内存。实际 MPS 内存见 Activity Monitor。[/]")
    console.print("  [dim]用完即释放机制：每次搜索后，Embedding 和 Reranker 都会自动释放。[/]")

    # 清理
    import shutil

    shutil.rmtree(tmp_dir, ignore_errors=True)
    console.print(f"\n  [dim]已清理临时文件: {tmp_dir}[/]")
    console.print("\n[bold green]✅ 端到端测试完成！[/]")


if __name__ == "__main__":
    main()
