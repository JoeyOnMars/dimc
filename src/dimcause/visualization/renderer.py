import networkx as nx


class GraphRenderer:
    """
    负责将 NetworkX 图谱渲染为不同格式 (ASCII, Mermaid, etc.)
    """

    @staticmethod
    def to_ascii(graph: nx.DiGraph) -> str:
        """
        渲染为简单的 ASCII 树状列表 (基于 BFS/DFS)
        或者打印节点统计信息。
        由于 ASCII 图形渲染复杂，这里先提供摘要统计 + 关键路径列表。
        """
        lines = []
        lines.append("Graph Summary:")
        lines.append(f"  Nodes: {graph.number_of_nodes()}")
        lines.append(f"  Edges: {graph.number_of_edges()}")

        # 统计节点类型
        type_counts = {}
        for _n, attr in graph.nodes(data=True):
            t = str(attr.get("type", "unknown"))
            type_counts[t] = type_counts.get(t, 0) + 1

        lines.append(f"  Types: {type_counts}")

        lines.append("\nTop 10 Connected Nodes (Degree Centrality):")
        degree = dict(graph.degree())
        top_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]
        for node, deg in top_nodes:
            attr = graph.nodes[node]
            summary = attr.get("summary", "")[:50]
            lines.append(f"  - {node} [{attr.get('type')}]: {deg} edges ({summary}...)")

        return "\n".join(lines)

    @staticmethod
    def to_mermaid(graph: nx.DiGraph, direction: str = "TD") -> str:
        """
        渲染为 Mermaid Flowchart
        """
        lines = [f"graph {direction}"]

        # 样式定义
        lines.append("  classDef commit fill:#f9f,stroke:#333,stroke-width:2px;")
        lines.append("  classDef decision fill:#ccf,stroke:#333,stroke-width:2px;")
        lines.append("  classDef requirement fill:#bfb,stroke:#333,stroke-width:2px;")
        lines.append("  classDef incident fill:#fcc,stroke:#333,stroke-width:2px;")
        lines.append("  classDef default fill:#fff,stroke:#333,stroke-width:1px;")

        for u, v, attr in graph.edges(data=True):
            # 获取节点标签 (截断摘要)
            u_attr = graph.nodes[u]
            v_attr = graph.nodes[v]

            u_label = GraphRenderer._sanitize_label(u_attr.get("summary", u))
            v_label = GraphRenderer._sanitize_label(v_attr.get("summary", v))

            # 使用 ID 作为节点标识，Label 显示内容
            # Mermaid ID 不能包含特殊字符，使用 hash 或清洗后的 ID
            u_id = GraphRenderer._sanitize_id(u)
            v_id = GraphRenderer._sanitize_id(v)

            # 关系标签
            rel = attr.get("relation", "related_to")

            # 节点定义 (首次出现时)
            lines.append(f'  {u_id}["{u_label}"]::: {u_attr.get("type", "default")}')
            lines.append(f'  {v_id}["{v_label}"]::: {v_attr.get("type", "default")}')

            # 边定义
            lines.append(f"  {u_id} -- {rel} --> {v_id}")

        return "\n".join(lines)

    @staticmethod
    def _sanitize_id(text: str) -> str:
        """清洗 Mermaid ID"""
        return text.replace("-", "_").replace(".", "_").replace("/", "_").replace(":", "_")

    @staticmethod
    def _sanitize_label(text: str) -> str:
        """清洗 Label"""
        return str(text).replace('"', "'").replace("\n", " ")[:30]
