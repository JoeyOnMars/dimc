import logging
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType, SourceType
from dimcause.storage.vector_store import VectorStore
from dimcause.utils.state import get_today_dir

# Initialize FastMCP server
mcp = FastMCP("dimcause")


def _get_services():
    """Lazy load services to avoid overhead on import"""
    index = EventIndex()
    # VectorStore requires embedding model loading, might be slow
    vector_store = VectorStore()
    return index, vector_store


@mcp.resource("dimcause://events/recent")
def get_recent_events() -> str:
    """Get the 20 most recent events from Dimcause audit log."""
    index, _ = _get_services()
    events = index.query(limit=20)

    formatted = []
    for e in events:
        ts = e.get("timestamp", "")
        summary = e.get("summary", "")
        formatted.append(f"[{ts}] {summary}")

    return "\n".join(formatted)


@mcp.tool()
def add_event(content: str, type: str = "thought", tags: str = "") -> str:
    """
    Log a new event to Dimcause.

    Args:
        content: The content of the event
        type: Event type (thought, conversation, decision, tool_use)
        tags: Comma-separated tags
    """
    try:
        # 1. Create Event object
        event_type = EventType(type) if type in EventType._value2member_map_ else EventType.THOUGHT

        event = Event(
            content=content,
            type=event_type,
            source=SourceType.MCP,
            tags=tags.split(",") if tags else [],
            timestamp=datetime.now(),
        )

        # 2. Save to Markdown file
        today_dir = get_today_dir()
        filename = f"{datetime.now().strftime('%H%M%S')}_{getattr(event.type, 'value', str(event.type))}.md"
        path = today_dir / filename

        path.write_text(event.to_markdown(), encoding="utf-8")

        # 3. Index it
        index, vector_store = _get_services()
        index.add(event, str(path))

        # 4. Vectorize it (Best effort)
        try:
            vector_store.add(event)
        except Exception as e:
            logging.error(f"Vector add failed: {e}")

        return f"Event logged: {event.id}"

    except Exception as e:
        return f"Error logging event: {str(e)}"


@mcp.tool()
def search_events(query: str) -> str:
    """
    Search Dimcause events semanticly.

    Args:
        query: The search query
    """
    try:
        _, vector_store = _get_services()
        results = vector_store.search(query, top_k=5)

        if not results:
            return "No matching events found."

        formatted = []
        for e in results:
            formatted.append(f"--- Event: {e.id} ---\nTime: {e.timestamp}\nSummary: {e.summary}\n")

        return "\n".join(formatted)

    except Exception as e:
        return f"Error searching events: {str(e)}"


# ──────────────────────────────────────────────
# 差异化端点: 因果审计能力 (传统工具无法提供)
# ──────────────────────────────────────────────


def _get_graph_store():
    """Lazy load GraphStore"""
    from dimcause.storage.graph_store import GraphStore

    return GraphStore()


@mcp.tool()
def get_causal_chain(event_id: str, depth: int = 3) -> str:
    """
    追溯某个事件的因果链 (BFS 遍历因果图谱)。

    回答 "这个 commit/decision 是因为什么?" 的问题。
    返回该事件在因果图谱中的上下游关联实体列表。

    Args:
        event_id: 事件 ID (如 evt_xxx 或 commit hash)
        depth: 遍历深度 (默认 3 层)
    """
    try:
        store = _get_graph_store()
        related = store.find_related(event_id, depth=depth)

        if not related:
            return f"未找到 '{event_id}' 的因果关联。可能原因: 事件不在图谱中，或尚未运行 'dimc graph build'。"

        lines = [f"因果链追溯: {event_id} (深度 {depth})", ""]
        for entity in related:
            context_str = f" | {entity.context}" if entity.context else ""
            lines.append(f"  [{entity.type}] {entity.name}{context_str}")

        lines.append(f"\n共找到 {len(related)} 个关联实体。")
        return "\n".join(lines)

    except Exception as e:
        return f"因果链追溯失败: {str(e)}"


@mcp.tool()
def audit_check(scope: str = "recent") -> str:
    """
    运行公理验证器，检测因果图谱中的违规项。

    检测内容:
    - 孤立 Commit (无 Decision/Incident 关联)
    - Decision 循环依赖
    - Function 修改无法追溯到 Decision

    Args:
        scope: 检查范围 ("recent" 或 "full")
    """
    try:
        from dimcause.reasoning.validator import AxiomValidator

        store = _get_graph_store()
        graph = store._graph

        if graph is None or graph.number_of_nodes() == 0:
            return "图谱为空。请先运行 'dimc graph build' 构建因果图谱。"

        validator = AxiomValidator()
        results = validator.validate(graph)

        if not results:
            return "✅ 公理验证通过: 未发现任何违规项。"

        lines = [f"⚠️ 发现 {len(results)} 个违规项:", ""]
        for r in results:
            severity_icon = "🔴" if r.severity.value == "error" else "🟡"
            lines.append(f"  {severity_icon} [{r.axiom_id}] {r.message}")
            lines.append(f"     实体: {r.entity_id}")

        return "\n".join(lines)

    except Exception as e:
        return f"审计检查失败: {str(e)}"


@mcp.resource("dimcause://graph/summary")
def get_graph_context() -> str:
    """获取当前项目因果图谱的概览统计 (节点数、边数、类型分布)。"""
    try:
        store = _get_graph_store()
        stats = store.stats()
        graph = store._graph

        lines = [
            "Dimcause 因果图谱概览",
            f"  节点总数: {stats.get('nodes', 0)}",
            f"  边总数:   {stats.get('edges', 0)}",
        ]

        # 类型分布
        if graph and graph.number_of_nodes() > 0:
            type_counts: dict[str, int] = {}
            for _, attr in graph.nodes(data=True):
                t = str(attr.get("type", "unknown"))
                type_counts[t] = type_counts.get(t, 0) + 1

            lines.append("  类型分布:")
            for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                lines.append(f"    {t}: {count}")

        return "\n".join(lines)

    except Exception as e:
        return f"图谱概览获取失败: {str(e)}"


def run(transport: str = "stdio"):
    """启动 MCP 服务器

    Args:
        transport: 传输方式 ("stdio" 或 "http")
    """
    if transport == "http":
        mcp.run(transport="http", host="127.0.0.1", port=14243)
    else:
        mcp.run()
