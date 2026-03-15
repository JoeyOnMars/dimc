# -*- coding: utf-8 -*-
"""
GraphStore 性能基准测试脚本
包含：
1. 数据生成 (数据合成)
2. 写入性能 (SQLite 写入)
3. 加载性能 (Hydration / 冷启动)
4. 遍历性能 (Traversal / 查询)
"""

import random
import statistics

# 调整路径以包含 src 目录
import sys
import time
from pathlib import Path
from typing import List

import networkx as nx
import typer
from rich.console import Console
from rich.table import Table

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

from dimcause.storage.graph_store import GraphStore  # noqa: E402

app = typer.Typer(help="GraphStore 性能基准测试工具")
console = Console()


def generate_synthetic_data(num_nodes: int, avg_degree: int = 3):
    """生成合成数据"""
    nodes = []
    edges = []

    # 生成节点
    for i in range(num_nodes):
        nodes.append(
            {
                "id": f"node_{i}",
                "type": random.choice(["decision", "event", "commit", "requirement"]),
                "data": {"timestamp": time.time(), "summary": f"合成事件 {i}"},
            }
        )

    # 生成边 (偏好链接或随机链接)
    for i in range(num_nodes):
        source = f"node_{i}"
        # 随机连接到之前的节点 (类似于 DAG 结构)
        if i > 0:
            targets = random.sample(range(i), k=min(i, random.randint(1, avg_degree)))
            for t in targets:
                target = f"node_{t}"
                edges.append(
                    {
                        "source": source,  # 边指向之前的节点？或者是向后？假设 source -> target
                        "target": target,
                        "relation": random.choice(["causes", "relates_to", "triggers"]),
                        "weight": random.random(),
                    }
                )
    return nodes, edges


@app.command()
def run(
    scale: List[int] = typer.Option([1000, 5000], help="测试的节点数量级列表"),
    db_path: str = "bench.db",
):
    """运行基准测试"""
    db_file = Path(db_path)

    results = []

    for n in scale:
        console.print(f"\n[bold blue]=== 基准测试规模: {n} 节点 ===[/bold blue]")

        # 清理
        if db_file.exists():
            db_file.unlink()

        store = GraphStore(db_path=str(db_file))

        # 1. 数据生成
        nodes, edges = generate_synthetic_data(n)
        num_edges = len(edges)
        console.print(f"已生成 {len(nodes)} 个节点, {num_edges} 条边")

        # 2. 写入性能
        start_time = time.time()
        # 使用批量插入逻辑（如果可用）或者循环
        # GraphStore 目前是单条插入。为了基准测试，我们使用循环。
        conn = store._get_conn()
        try:
            # 手动批量插入以确保公平（模拟批量导入或真实的持续摄入）
            # 实际上，让我们先测量使用公共 API 的原始插入速度以查看每次调用的开销
            # 但对于 10k 来说可能太慢了。让我们使用内部批量进行设置，
            # 或者只是接受它需要时间并测量它。
            # 为了测试 SQLite 数据库本身的极限写入吞吐量，
            # 我们使用直接 SQL 批量插入。这能够排除应用层逻辑开销，
            # 并作为后续 GraphStore 加载测试的高效数据准备步骤。

            # 批量插入节点
            conn.executemany(
                "INSERT INTO graph_nodes (id, type, data, last_updated) VALUES (?, ?, ?, ?)",
                [(node["id"], node["type"], "{}", time.time()) for node in nodes],
            )
            # 批量插入边
            conn.executemany(
                "INSERT INTO graph_edges (source, target, relation, weight, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (e["source"], e["target"], e["relation"], e["weight"], "{}", time.time())
                    for e in edges
                ],
            )
            conn.commit()
        finally:
            conn.close()

        write_time = time.time() - start_time
        console.print(f"写入时间 (批量 SQL): {write_time:.4f}s")

        # 3. 加载性能 (Hydration)
        # 重新初始化存储以强制加载
        start_time = time.time()
        load_store = GraphStore(db_path=str(db_file))
        # 访问 _graph 以触发延迟加载（目前它在 __init__ 中加载）
        hydration_time = time.time() - start_time
        console.print(f"加载时间 (SQLite -> NetworkX): {hydration_time:.4f}s")

        graph = load_store._graph
        assert len(graph.nodes) == n

        # 4. 遍历性能 (内存中)
        # 查找随机节点的后代 (BFS)
        sample_size = 100
        sample_nodes = random.sample(list(graph.nodes), min(n, sample_size))

        traversal_times = []
        for start_node in sample_nodes:
            t0 = time.time()
            # 2跳遍历模拟
            # nx.single_source_shortest_path_length(graph, start_node, cutoff=2)
            # 或者只是后代
            _ = list(nx.bfs_successors(graph, start_node, depth_limit=2))
            traversal_times.append(time.time() - t0)

        avg_traversal = statistics.mean(traversal_times) * 1000  # 毫秒
        console.print(f"平均遍历时间 (BFS 深度=2): {avg_traversal:.4f}ms")

        # 5. 峰值内存？(如果没有 psutil 很难在脚本内准确测量)
        # 我们暂时跳过。

        results.append(
            {
                "节点数": n,
                "边数": num_edges,
                "写入(s)": round(write_time, 4),
                "加载(s)": round(hydration_time, 4),
                "遍历(ms)": round(avg_traversal, 4),
            }
        )

    # 汇总表
    table = Table(title="GraphStore 性能基准测试 (NetworkX + SQLite)")
    table.add_column("节点数", justify="right")
    table.add_column("边数", justify="right")
    table.add_column("写入 (s)", justify="right")
    table.add_column("加载 (s)", justify="right")
    table.add_column("遍历 (ms)", justify="right")

    for r in results:
        table.add_row(
            str(r["节点数"]),
            str(r["边数"]),
            str(r["写入(s)"]),
            str(r["加载(s)"]),
            str(r["遍历(ms)"]),
        )

    console.print(table)

    # 清理
    if db_file.exists():
        db_file.unlink()


if __name__ == "__main__":
    app()
