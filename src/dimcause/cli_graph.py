from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

# Imports
from dimcause.core.event_index import EventIndex
from dimcause.core.models import SemanticEvent
from dimcause.reasoning.engine import HybridInferenceEngine
from dimcause.reasoning.validator import AxiomValidator, ValidationSeverity
from dimcause.storage.graph_store import GraphStore  # Updated to storage
from dimcause.visualization.renderer import GraphRenderer

app = typer.Typer(help="因果图谱命令: build, check, show, stats, explore")
console = Console()


def _load_graph(limit: int = 1000):
    """Helper: Load graph from GraphStore"""
    store = GraphStore()
    # Assuming the store hydrates itself on init or we access ._graph
    # My new implementation hydrates on init.
    # But let's expose a public property or method to get the graph if needed.
    # For now, accessing _graph is okay, or I should add a property.
    return store._graph if store._graph is not None else None


@app.command("explore")
def explore():
    """
    启动交互式图谱探索器 (TUI)。
    """
    from dimcause.tui.app import GraphExploreApp

    app = GraphExploreApp()
    app.run()
    store = GraphStore()
    return store.load_graph()


@app.command("stats")
def stats():
    """
    显示图谱统计信息
    """
    store = GraphStore()
    conn = store._get_conn()
    try:
        nodes = conn.execute("SELECT count(*) FROM graph_nodes").fetchone()[0]
        edges = conn.execute("SELECT count(*) FROM graph_edges").fetchone()[0]

        console.print(
            Panel(
                f"[bold]GraphStore 统计[/]\n\n"
                f"节点总数: [green]{nodes}[/]\n"
                f"边总数:   [green]{edges}[/]",
                title="图谱统计",
                border_style="blue",
            )
        )
    finally:
        conn.close()


@app.command("build")
def build(
    dry_run: bool = typer.Option(False, "--dry-run", help="不保存链接到数据库"),
    limit: int = typer.Option(100, help="处理的最近事件数量"),
    threshold: Optional[float] = typer.Option(
        None, "--threshold", "-t", help="语义相似度阈值 (覆盖配置)"
    ),
):
    """
    使用混合推理引擎构建/更新因果图谱。
    """
    console.print(f"[bold blue]正在构建因果图谱 (Limit: {limit})...[/bold blue]")
    if threshold is not None:
        console.print(f"[bold blue]使用语义阈值覆盖: {threshold}[/bold blue]")

    # 1. Fetch recent events
    index = EventIndex()
    events_data = index.query(limit=limit)
    events = []
    for ed in events_data:
        # Need full Event objects for semantic linking
        # Use load_event to get content
        ev = index.load_event(ed["id"])
        if ev:
            events.append(ev)

    if not events:
        console.print("[yellow]未找到事件。[/yellow]")
        return

    # 2. Run Inference
    engine = HybridInferenceEngine(semantic_threshold=threshold)

    # 检查 LLM 可用性并向用户反馈
    if engine.llm_linker and not engine.llm_linker.available:
        reason = engine.llm_linker.unavailable_reason or "未知原因"
        console.print(f"[yellow]⚠️  LLM 推理已跳过: {reason}[/yellow]")
        console.print(
            "[dim]提示: 在项目 .env 文件中设置 DEEPSEEK_API_KEY=sk-xxx 即可启用 LLM 推理[/dim]"
        )

    links = engine.infer(events)

    console.print(f"[green]推断出 {len(links)} 个因果链接。[/green]")

    # 3. Save Links
    if not dry_run:
        # We need to update the Event objects in the index with the new links
        # Currently EventIndex.add replaces the event.
        # But SemanticEvent stores links in itself.
        # So we need to attach links to source events and save them.

        # Group links by source
        links_by_source = {}
        for link in links:
            if link.source not in links_by_source:
                links_by_source[link.source] = []
            links_by_source[link.source].append(link)

        updated_count = 0
        for source_id, source_links in links_by_source.items():
            ev = index.load_event(source_id)
            if ev:
                # Upgrade to SemanticEvent to store links
                try:
                    ev_data = ev.model_dump()
                    semantic_ev = SemanticEvent(**ev_data)
                    semantic_ev.causal_links = source_links

                    # Get path from index
                    row = index.get_by_id(source_id)
                    path = row["markdown_path"] if row else "unknown_path.md"

                    if index.add(semantic_ev, path):
                        updated_count += 1
                except Exception as e:
                    console.print(f"[red]更新事件 {source_id} 失败: {e}[/red]")

        console.print(f"已更新 {updated_count} 个事件的链接。")
    else:
        console.print("[dim]空跑模式: 未保存链接。[/dim]")


@app.command("show")
def show(
    format: str = typer.Option("ascii", "--format", "-f", help="输出格式: ascii, mermaid"),
    limit: int = typer.Option(100, help="节点数量限制"),
):
    """
    可视化因果图谱。
    """
    graph = _load_graph(limit=limit)

    if format == "ascii":
        print(GraphRenderer.to_ascii(graph))
    elif format == "mermaid":
        print(GraphRenderer.to_mermaid(graph))
    else:
        console.print(f"[red]未知格式: {format}[/red]")


@app.command("check")
def check(limit: int = typer.Option(1000, help="检查的节点数量限制")):
    """
    运行公理验证器 (Axiom Validator) 检查图谱。
    """
    graph = _load_graph(limit=limit)
    validator = AxiomValidator()
    results = validator.validate(graph)

    if not results:
        console.print("[bold green]✅ 未发现公理违规。[/bold green]")
        return

    console.print(f"[bold red]发现 {len(results)} 个违规项:[/bold red]")

    for res in results:
        color = "red" if res.severity == ValidationSeverity.ERROR else "yellow"
        console.print(
            Panel(
                f"规则: {res.axiom_id}\n实体: {res.entity_id}\n消息: {res.message}",
                title=f"[{color}]{res.severity.upper()}[/{color}]",
                border_style=color,
            )
        )


@app.command("link")
def link(
    source: str = typer.Argument(..., help="源事件 ID"),
    target: str = typer.Argument(..., help="目标事件 ID"),
    relation: str = typer.Option(
        ...,
        "--relation",
        "-r",
        help="关系类型 (e.g. implements, realizes, modifies, triggers, validates, overrides, fixes)",
    ),
):
    """
    手动标注两个事件之间的因果关系。

    示例: dimc graph link evt_001 evt_002 --relation realizes
    """
    from dimcause.core.ontology import get_ontology
    from dimcause.reasoning.causal import CausalLink

    # 1. 校验关系合法性
    ontology = get_ontology()
    valid_relations = [r["name"] for r in ontology.relations]
    if relation not in valid_relations:
        console.print(f"[red]❌ 无效关系: '{relation}'[/red]")
        console.print(f"[dim]合法关系: {', '.join(valid_relations)}[/dim]")
        raise typer.Exit(1)

    # 2. 校验事件存在
    index = EventIndex()
    source_row = index.get_by_id(source)
    target_row = index.get_by_id(target)

    if not source_row:
        console.print(f"[red]❌ 源事件不存在: {source}[/red]")
        raise typer.Exit(1)
    if not target_row:
        console.print(f"[red]❌ 目标事件不存在: {target}[/red]")
        raise typer.Exit(1)

    # 3. 创建 CausalLink 并写入
    causal_link = CausalLink(
        source=source,
        target=target,
        relation=relation,
        weight=1.0,
        metadata={"origin": "manual", "annotator": "cli"},
    )

    # 加载源事件并附加链接
    ev = index.load_event(source)
    if ev:
        try:
            ev_data = ev.model_dump()
            semantic_ev = SemanticEvent(**ev_data)
            # 追加而非覆盖
            existing_links = getattr(semantic_ev, "causal_links", []) or []
            existing_links.append(causal_link)
            semantic_ev.causal_links = existing_links

            path = source_row["markdown_path"] if source_row else "unknown.md"
            if index.add(semantic_ev, path):
                console.print(
                    Panel(
                        f"[green]✅ 已建立因果关系[/green]\n\n"
                        f"  {source} --[{relation}]--> {target}\n\n"
                        f"来源: 手动标注 (CLI)",
                        title="因果链接",
                        border_style="green",
                    )
                )
            else:
                console.print("[red]❌ 写入失败[/red]")
        except Exception as e:
            console.print(f"[red]❌ 标注失败: {e}[/red]")
    else:
        console.print(f"[red]❌ 无法加载源事件: {source}[/red]")


@app.command("query")
def query(
    entity_id: str = typer.Argument(..., help="要查询的实体 ID"),
    depth: int = typer.Option(2, "--depth", "-d", help="遍历深度"),
):
    """
    查询图谱中某个实体的邻居关系 (BFS)。

    示例: dimc graph query evt_001 --depth 2
    """
    from rich.table import Table

    graph = _load_graph(limit=10000)
    if graph is None or len(graph) == 0:
        console.print("[yellow]图谱为空或加载失败。[/yellow]")
        raise typer.Exit(1)

    if entity_id not in graph:
        console.print(f"[red]❌ 实体 '{entity_id}' 不在图谱中。[/red]")
        # 模糊匹配建议
        candidates = [n for n in graph.nodes if entity_id.lower() in str(n).lower()]
        if candidates:
            console.print(f"[dim]你是不是想查: {', '.join(candidates[:5])}[/dim]")
        raise typer.Exit(1)

    # BFS 遍历
    visited = set()
    queue = [(entity_id, 0)]
    results = []

    while queue:
        node, d = queue.pop(0)
        if node in visited or d > depth:
            continue
        visited.add(node)

        # 获取邻居 (出边和入边)
        for _, neighbor, data in graph.out_edges(node, data=True):
            relation = data.get("relation", "unknown")
            results.append((node, relation, neighbor, d, "→"))
            if neighbor not in visited and d + 1 <= depth:
                queue.append((neighbor, d + 1))

        for predecessor, _, data in graph.in_edges(node, data=True):
            relation = data.get("relation", "unknown")
            results.append((predecessor, relation, node, d, "←"))
            if predecessor not in visited and d + 1 <= depth:
                queue.append((predecessor, d + 1))

    if not results:
        console.print(f"[yellow]实体 '{entity_id}' 无邻居关系。[/yellow]")
        return

    # 输出表格
    table = Table(title=f"图谱查询: {entity_id} (深度 {depth})")
    table.add_column("源", style="cyan")
    table.add_column("关系", style="green")
    table.add_column("目标", style="magenta")
    table.add_column("深度", justify="center")
    table.add_column("方向", justify="center")

    for src, rel, tgt, d, direction in results:
        table.add_row(src, rel, tgt, str(d), direction)

    console.print(table)
    console.print(f"\n[dim]共找到 {len(results)} 条关系。[/dim]")


if __name__ == "__main__":
    app()
