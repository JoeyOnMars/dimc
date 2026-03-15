# -*- coding: utf-8 -*-
"""
验证跨 Agent 数据交换 (Consumer Simulation)

此脚本模拟一个外部 Agent (Consumer)，读取 Dimcause 导出的 JSON-LD 文件，
并执行语义查询，以验证数据的互通性。

Scenario:
1. Load JSON-LD file.
2. Build a simple graph/index from the JSON-LD data.
3. Query: "Find all Decisions that implement Requirement X."
"""

import json
import sys
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

console = Console()


def load_jsonld(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_index(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build a simple ID-based index from JSON-LD @graph"""
    index = {}
    if "@graph" not in data:
        console.print("[red]Error: No @graph found in JSON-LD[/red]")
        return index

    for item in data["@graph"]:
        if "@id" in item:
            index[item["@id"]] = item
    return index


def find_implementing_decisions(index: Dict[str, Any], req_id: str) -> List[Dict[str, Any]]:
    """
    语义查询: 查找所有实现了指定需求的决策
    Logic: Find Decision D where D.implements contains req_id
    """
    decisions = []

    # 规范化 req_id (ensure prefix)
    if not req_id.startswith("dev:"):
        # 尝试匹配 ID 后缀
        pass

    for item in index.values():
        # Check type
        types = item.get("@type", [])
        if isinstance(types, str):
            types = [types]

        if "dev:Decision" in types or "Decision" in types:
            # Check implements relation
            # Note: JSON-LD expansion might differ, assuming compacted form from our export
            implements = item.get("implements", [])
            if isinstance(implements, dict):
                implements = [implements]

            for rel in implements:
                target_id = rel.get("@id")
                if target_id == req_id:
                    decisions.append(item)
                    break
    return decisions


def main():
    if len(sys.argv) < 2:
        console.print("Usage: python verify_jsonld_consumer.py <jsonld_file> [req_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    req_id = sys.argv[2] if len(sys.argv) > 2 else "dev:event/req_001"

    console.print(f"[bold blue]Consumer Agent[/bold blue]: Loading knowledge from {file_path}...")

    try:
        data = load_jsonld(file_path)
        index = build_index(data)
        console.print(f"Loaded {len(index)} entities.")

        console.print(f"\n[bold green]Query:[/bold green] Find Decisions implementing '{req_id}'")
        results = find_implementing_decisions(index, req_id)

        if results:
            table = Table(title=f"Decisions implementing {req_id}")
            table.add_column("ID", style="cyan")
            table.add_column("Summary", style="magenta")
            table.add_column("Timestamp", style="green")

            for res in results:
                table.add_row(
                    res.get("@id", "N/A"), res.get("summary", "N/A"), res.get("timestamp", "N/A")
                )
            console.print(table)
            console.print("\n[bold green]SUCCESS: Data interoperability verified![/bold green]")
        else:
            console.print(f"[yellow]No decisions found implementing {req_id}.[/yellow]")
            # debug print
            console.print("Available Entities:")
            for k, v in index.items():
                console.print(f"- {k} ({v.get('@type')})")

    except Exception as e:
        console.print(f"[red]Verification Failed:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
