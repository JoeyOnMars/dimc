"""
Trajectory Service (Layer 3)

负责构建和管理语义事件的因果轨迹 DAG (Directed Acyclic Graph)。
提供祖先追溯、后代影响分析和环检测功能。
"""

import logging
from collections import deque
from typing import Dict, List, Set

try:
    import networkx as nx
except ImportError:
    nx = None

from dimcause.core.models import SemanticEvent

logger = logging.getLogger(__name__)


class TrajectoryService:
    """
    轨迹服务: 管理事件因果图谱。
    """

    def __init__(self, events: List[SemanticEvent]):
        self.events_map = {e.uri: e for e in events if e.uri}
        self.graph = None

        # Fallback structures
        self._adj: Dict[str, List[str]] = {}
        self._rev_adj: Dict[str, List[str]] = {}

        if nx:
            self.graph = nx.DiGraph()
            self._build_graph_nx(events)
        else:
            self._build_graph_pure(events)

    def _build_graph_nx(self, events: List[SemanticEvent]):
        """构建 NetworkX 图。"""
        for event in events:
            if not event.uri:
                continue
            self.graph.add_node(event.uri, event=event)
            for link in event.causal_links:
                if link.source and link.target:
                    self.graph.add_edge(
                        link.source, link.target, relation=link.relation, weight=link.weight
                    )

    def _build_graph_pure(self, events: List[SemanticEvent]):
        """构建纯 Python 图结构 (Fallback)。"""
        for event in events:
            if not event.uri:
                continue
            # Ensure nodes exist
            if event.uri not in self._adj:
                self._adj[event.uri] = []
            if event.uri not in self._rev_adj:
                self._rev_adj[event.uri] = []

            for link in event.causal_links:
                if link.source and link.target:
                    # 记录边
                    if link.source not in self._adj:
                        self._adj[link.source] = []
                    self._adj[link.source].append(link.target)

                    if link.target not in self._rev_adj:
                        self._rev_adj[link.target] = []
                    self._rev_adj[link.target].append(link.source)

    def get_ancestors(self, event_uri: str) -> List[SemanticEvent]:
        """获取所有祖先节点 (上游原因)。"""
        if self.graph:
            if event_uri not in self.graph:
                return []
            ancestor_uris = nx.ancestors(self.graph, event_uri)
            return self._uris_to_events(ancestor_uris)

        # Fallback: BFS on reverse adjacency
        ancestors = set()
        queue = deque([event_uri])
        visited = {event_uri}

        while queue:
            curr = queue.popleft()
            parents = self._rev_adj.get(curr, [])
            for parent in parents:
                if parent not in visited:
                    visited.add(parent)
                    ancestors.add(parent)
                    queue.append(parent)

        return self._uris_to_events(ancestors)

    def get_descendants(self, event_uri: str) -> List[SemanticEvent]:
        """获取所有后代节点 (下游影响)。"""
        if self.graph:
            if event_uri not in self.graph:
                return []
            descendant_uris = nx.descendants(self.graph, event_uri)
            return self._uris_to_events(descendant_uris)

        # Fallback: BFS on adjacency
        descendants = set()
        queue = deque([event_uri])
        visited = {event_uri}

        while queue:
            curr = queue.popleft()
            children = self._adj.get(curr, [])
            for child in children:
                if child not in visited:
                    visited.add(child)
                    descendants.add(child)
                    queue.append(child)

        return self._uris_to_events(descendants)

    def detect_cycles(self) -> List[List[str]]:
        """检测因果图中的环。"""
        if self.graph:
            try:
                return list(nx.simple_cycles(self.graph))
            except Exception as e:
                logger.error(f"Cycle detection failed: {e}")
                return []

        # Fallback: DFS for cycle detection
        cycles = []
        visited = set()
        path = []
        path_set = set()

        def dfs(u):
            visited.add(u)
            path.append(u)
            path_set.add(u)

            for v in self._adj.get(u, []):
                if v in path_set:
                    # Found cycle
                    try:
                        cycle_start_index = path.index(v)
                        cycles.append(path[cycle_start_index:].copy())
                    except ValueError:
                        pass
                elif v not in visited:
                    dfs(v)

            path.pop()
            path_set.remove(u)

        # Iterate over all nodes to ensure full coverage
        all_nodes = set(self._adj.keys()) | set(self._rev_adj.keys())
        for node in all_nodes:
            if node not in visited:
                dfs(node)

        return cycles

    def _uris_to_events(self, uris: Set[str]) -> List[SemanticEvent]:
        """将 URI 集合转换为 Event 对象列表，按时间戳排序。"""
        events = []
        for uri in uris:
            evt = self.events_map.get(uri)
            if evt:
                events.append(evt)

        events.sort(key=lambda x: x.timestamp)
        return events
