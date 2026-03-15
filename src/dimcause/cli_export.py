# -*- coding: utf-8 -*-
"""
Dimcause Export CLI
"""

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from dimcause.core.models import Event, EventType
from dimcause.storage.graph_store import GraphStore

app = typer.Typer(help="导出数据到外部格式")
console = Console()


@app.command("jsonld")
def export_jsonld(
    out: Path = typer.Option("dimcause_export.jsonld", help="输出 JSON-LD 文件路径"),
    db_path: str = typer.Option("~/.dimcause/index.db", help="SQLite 数据库路径"),
):
    """
    导出因果图谱为 JSON-LD 格式 (Schema.org/Prov-O)
    """
    store = GraphStore(db_path=db_path)

    # 1. 获取所有事件
    if store._graph is None:
        console.print("[red]错误: 图数据未加载，请检查 SQLite 数据库是否存在[/red]")
        raise typer.Exit(1)

    graph = store._graph
    export_objects = []

    with console.status(f"正在导出 {len(graph.nodes)} 个节点..."):
        for node_id, node_data in graph.nodes(data=True):
            try:
                # 构造 Event 对象以利用 to_jsonld
                # GraphStore node data: type=..., **data_json

                evt_type_str = node_data.get("type", "unknown")
                try:
                    evt_type = EventType(evt_type_str)
                except ValueError:
                    evt_type = EventType.UNKNOWN

                # 尝试解析 timestamp
                ts_input = node_data.get("timestamp")
                timestamp = datetime.now()

                if isinstance(ts_input, (int, float)):
                    timestamp = datetime.fromtimestamp(ts_input)
                elif isinstance(ts_input, str):
                    try:
                        timestamp = datetime.fromisoformat(ts_input)
                    except ValueError:
                        pass

                # 构造临时 Event 对象
                # 注意：content 可能在 metadata 中，也可能没有
                evt = Event(
                    id=node_id,
                    type=evt_type,
                    timestamp=timestamp,
                    summary=node_data.get("summary", node_id),
                    content=node_data.get("content", ""),
                    tags=node_data.get("tags", []),
                    metadata=node_data,  # 保留原始数据
                )

                data = evt.to_jsonld()

                # 注入关系 (从 Graph Edges)
                # NetworkX DiGraph: graph.out_edges(node_id, data=True) -> (src, tgt, data)
                out_edges = graph.out_edges(node_id, data=True)
                for _src, tgt, edge_data in out_edges:
                    rel = edge_data.get("relation", "relatesTo")
                    target_uri = f"dev:event/{tgt}"  # 假设目标也是Event

                    if rel not in data:
                        data[rel] = []

                    # 避免重复
                    if not any(link["@id"] == target_uri for link in data[rel]):
                        data[rel].append({"@id": target_uri})

                export_objects.append(data)
            except Exception as e:
                console.print(f"[yellow]警告: 跳过节点 {node_id}: {e}[/yellow]")

    # 2. 构造最终 JSON-LD 文档
    from dimcause.core.ontology import get_ontology

    # Load context explicitly if not already loaded (e.g. singleton)
    ont = get_ontology()
    context = ont.get_jsonld_context().get("@context", {})

    jsonld_doc = {"@context": context, "@graph": export_objects}

    # 3. 写入文件
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(jsonld_doc, f, indent=2, ensure_ascii=False)

    console.print(f"[green]成功导出 {len(export_objects)} 个对象到: {out}[/green]")
