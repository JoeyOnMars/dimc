"""
SearchEngine - 统一搜索引擎

聚合多种搜索方式：文本、语义、图谱
"""

# Type checking import
import hashlib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ..core.models import Event, EventType, SourceType
from ..storage.markdown_store import MarkdownStore
from ..storage.vector_store import VectorStore
from .unix_retrieval import RetrievalHit, UnixRetrievalService

if TYPE_CHECKING:
    from ..storage.graph_store import GraphStore


class SearchEngine:
    """
    统一搜索引擎

    实现 ISearchEngine 接口
    """

    # BFS 性能限制常量
    MAX_FANOUT_PER_LEVEL = 500  # 单层最大扇出节点数
    MAX_TOTAL_NODES = 2000  # 总探索节点数上限
    UNIX_SOURCE_MULTIPLIERS = {
        "events": 1.0,
        "code": 0.92,
        "docs": 0.84,
    }
    UNIX_LINE_HIT_BONUS = 0.02
    UNIX_EXACTNESS_BONUS_CAP = 0.2

    def __init__(
        self,
        markdown_store: Optional[MarkdownStore] = None,
        vector_store: Optional[VectorStore] = None,
        graph_store: Optional["GraphStore"] = None,
    ):
        self.markdown_store = markdown_store or MarkdownStore()
        self.vector_store = vector_store or VectorStore()
        self.unix_retrieval = UnixRetrievalService(markdown_store=self.markdown_store)

        if graph_store:
            self.graph_store = graph_store
        else:
            # Lazy load / Default
            from ..storage.graph_store import create_graph_store

            self.graph_store = create_graph_store()

    def search(
        self, query: str, mode: str = "hybrid", top_k: int = 10, use_reranker: bool = True
    ) -> List[Event]:
        """
        统一搜索接口

        Args:
            query: 搜索词
            mode: 搜索模式 (text, semantic, hybrid, graph, unix)
            top_k: 返回数量
            use_reranker: 是否启用语义重排序 (默认 True)

        Returns:
            匹配的 Events

        内存管理 (RT-000 §4.2):
            Embedding 和 Reranker 不同时驻留内存。
            搜索完成后释放 Embedding → 加载 Reranker → 完成后释放 Reranker。
        """
        # Fetch more candidates if reranking is enabled
        fetch_k = top_k * 3 if use_reranker else top_k

        needs_embedding = mode in ("semantic", "hybrid")

        try:
            if mode == "text":
                results = self._text_search(query, fetch_k)
            elif mode == "semantic":
                results = self._semantic_search(query, fetch_k)
            elif mode == "graph":
                results = self._graph_search(query, fetch_k)
            elif mode == "unix":
                results = self._unix_search(query, fetch_k)
            else:
                results = self._hybrid_search(query, fetch_k)
        finally:
            # 用完即释放：Embedding 做完就释放，无论有无结果、无论是否异常
            if needs_embedding:
                self.vector_store.release_model()

        if use_reranker and results:
            try:
                from .reranker import Reranker

                reranker = Reranker()
                results = reranker.rank(query, results, top_k)
            finally:
                # 用完即释放：Reranker 做完就释放，无论是否异常
                from .reranker import Reranker as _R

                _R.release_model()

        return results[:top_k]

    def trace(self, file_path: str, function_name: Optional[str] = None) -> List[Event]:
        """
        追溯代码历史
        """
        # 构建搜索查询
        query = file_path
        if function_name:
            query = f"{file_path} {function_name}"

        # 使用语义搜索 + Reranker
        return self.search(query, mode="semantic", top_k=20, use_reranker=True)

    def _semantic_search(self, query: str, top_k: int) -> List[Event]:
        """语义搜索（优先向量，失败时降级文本）"""
        if not query.strip():
            return []

        try:
            return self.vector_store.search(query=query, top_k=top_k)
        except Exception:
            # 向量模型不可用时，退化到文本，保持命令可用
            return self._text_search(query, top_k)

    def _hybrid_search(self, query: str, top_k: int) -> List[Event]:
        """
        混合检索（Vector Local + Graph Global + UNIX Grep + Text）。

        说明：
        - 先并行思维、串行执行多通道召回，再统一去重融合
        - 重排由上层 use_reranker 控制，此处仅做候选融合
        """
        if not query.strip():
            return []

        semantic_results = self._semantic_search(query, top_k)
        graph_results = self._graph_search(query, top_k)
        unix_results = self._unix_search(query, top_k)
        text_results = self._text_search(query, top_k)

        channel_results: List[Tuple[str, List[Event], float]] = [
            ("semantic", semantic_results, 1.0),
            ("graph", graph_results, 0.9),
            ("unix", unix_results, 0.8),
            ("text", text_results, 0.7),
        ]
        return self._merge_candidates(channel_results, top_k)

    def _merge_candidates(
        self, channel_results: List[Tuple[str, List[Event], float]], top_k: int
    ) -> List[Event]:
        """
        多通道候选融合：
        - event.id 去重
        - 按通道权重与通道内名次叠加打分
        - 同分时按 timestamp 新到旧
        """
        if top_k <= 0:
            return []

        score_map: Dict[str, float] = {}
        event_map: Dict[str, Event] = {}

        for _channel_name, results, weight in channel_results:
            if not results:
                continue

            total = max(len(results), 1)
            for idx, event in enumerate(results):
                event_id = getattr(event, "id", None)
                if not event_id:
                    continue

                # 通道内排名得分：rank 越高，增益越大
                rank_score = (total - idx) / total
                effective_weight = self._candidate_weight(_channel_name, event, weight)
                score_map[event_id] = score_map.get(event_id, 0.0) + (effective_weight * rank_score)

                # 首次出现保留对象，避免重复 load
                if event_id not in event_map:
                    event_map[event_id] = event

        # 先按融合分，再按时间（新到旧）
        ranked_ids = sorted(
            score_map.keys(),
            key=lambda eid: (
                score_map[eid],
                self._event_ts(getattr(event_map[eid], "timestamp", None)),
            ),
            reverse=True,
        )
        return [event_map[eid] for eid in ranked_ids[:top_k]]

    def _candidate_weight(self, channel_name: str, event: Event, base_weight: float) -> float:
        if channel_name != "unix":
            return base_weight
        return self._unix_candidate_weight(event, base_weight)

    def _unix_candidate_weight(self, event: Event, base_weight: float) -> float:
        metadata = getattr(event, "metadata", {}) or {}
        source_name = metadata.get("retrieval_source")
        if not source_name:
            return base_weight

        effective_weight = base_weight * self.UNIX_SOURCE_MULTIPLIERS.get(source_name, 0.8)
        retrieval_score = metadata.get("retrieval_score")
        source_base = UnixRetrievalService.SOURCE_WEIGHTS.get(source_name)

        if isinstance(retrieval_score, (int, float)) and isinstance(source_base, (int, float)):
            effective_weight += min(
                max(retrieval_score - source_base, 0.0),
                self.UNIX_EXACTNESS_BONUS_CAP,
            )

        if metadata.get("retrieval_line"):
            effective_weight += self.UNIX_LINE_HIT_BONUS

        return effective_weight

    @staticmethod
    def _event_ts(ts: object) -> float:
        """统一时间戳比较键，避免 datetime/str/None 混排报错。"""
        if isinstance(ts, datetime):
            return ts.timestamp()
        if isinstance(ts, (int, float)):
            return float(ts)
        return 0.0

    def _text_search(self, query: str, top_k: int) -> List[Event]:
        """纯文本搜索"""
        from datetime import datetime, timedelta

        results = []
        query_lower = query.lower()

        # 搜索最近 30 天的事件
        start = datetime.now() - timedelta(days=30)
        end = datetime.now()

        try:
            files = self.markdown_store.list_by_date(start, end)

            for file_path in files:
                try:
                    event = self.markdown_store.load(file_path)
                    if event:
                        # 在 summary 和 content 中搜索关键词
                        if (
                            query_lower in event.summary.lower()
                            or query_lower in event.content.lower()
                        ):
                            results.append(event)

                            # Note: Text search doesn't rank well, so we fetch enough
                            if len(results) >= top_k:
                                break
                except Exception:
                    continue
        except Exception:
            pass

        return results[:top_k]

    def _unix_search(
        self,
        query: str,
        top_k: int,
        sources: Optional[Tuple[str, ...]] = None,
    ) -> List[Event]:
        """
        UNIX grep 通道（基于 ripgrep 进行高精度文本召回）。

        约束：
        - 结果先经 UnixRetrievalService 统一建模
        - 当前阶段仍向外返回 Event，但允许包含 synthetic file hits
        - rg 不可用或执行失败时，返回空列表
        """
        hits = self.unix_retrieval.search_hits(query=query, top_k=top_k, sources=sources)
        return self._materialize_unix_hits(hits, top_k)

    def _materialize_unix_hits(self, hits: List[RetrievalHit], top_k: int) -> List[Event]:
        results: list[Event] = []

        for hit in hits:
            if hit.source == "events":
                event = self.markdown_store.load(hit.path)
                if event:
                    results.append(self._annotate_unix_event(event, hit))
            else:
                results.append(self._build_synthetic_retrieval_event(hit))

            if len(results) >= top_k:
                break

        return results

    def _annotate_unix_event(self, event: Event, hit: RetrievalHit) -> Event:
        annotated = event.model_copy(deep=True) if hasattr(event, "model_copy") else event
        path_label = self._relative_path(Path(hit.path))
        metadata = dict(getattr(annotated, "metadata", {}) or {})
        metadata.update(
            {
                "synthetic_result": False,
                "retrieval_source": hit.source,
                "retrieval_kind": hit.kind,
                "retrieval_path": Path(hit.path).as_posix(),
                "retrieval_display_path": path_label,
                "retrieval_line": hit.line_no,
                "retrieval_snippet": hit.snippet.strip() if hit.snippet else None,
                "retrieval_score": hit.score,
                "title": hit.title,
                "markdown_path": Path(hit.path).as_posix(),
            }
        )
        annotated.metadata = metadata

        related_files = list(getattr(annotated, "related_files", []) or [])
        if path_label not in related_files:
            related_files.append(path_label)
        annotated.related_files = related_files
        return annotated

    def _build_synthetic_retrieval_event(self, hit: RetrievalHit) -> Event:
        path_obj = Path(hit.path)
        timestamp = datetime.now()
        try:
            timestamp = datetime.fromtimestamp(path_obj.stat().st_mtime)
        except Exception:
            pass

        relative_path = self._relative_path(path_obj)
        path_label = relative_path or path_obj.as_posix()
        line_label = f":{hit.line_no}" if hit.line_no else ""
        summary = f"[{hit.source}] {path_label}{line_label}"
        if hit.snippet:
            snippet = hit.snippet.strip()
            if snippet:
                summary = f"{summary} - {snippet[:80]}"

        content_lines = [
            f"retrieval_source: {hit.source}",
            f"path: {path_label}",
        ]
        if hit.line_no:
            content_lines.append(f"line: {hit.line_no}")
        if hit.snippet:
            content_lines.extend(["", hit.snippet.strip()])

        return Event(
            id=self._synthetic_hit_id(hit),
            type=EventType.RESOURCE,
            timestamp=timestamp,
            summary=summary,
            content="\n".join(content_lines).strip(),
            source=SourceType.FILE,
            tags=["unix_search", hit.source, hit.kind, "synthetic"],
            related_files=[path_label],
            confidence=min(max(hit.score, 0.0), 1.0),
            metadata={
                "synthetic_result": True,
                "retrieval_source": hit.source,
                "retrieval_kind": hit.kind,
                "retrieval_path": path_obj.as_posix(),
                "retrieval_display_path": path_label,
                "retrieval_line": hit.line_no,
                "retrieval_snippet": hit.snippet.strip() if hit.snippet else None,
                "retrieval_score": hit.score,
                "title": hit.title,
                "markdown_path": path_obj.as_posix() if path_obj.suffix == ".md" else None,
            },
        )

    @staticmethod
    def _synthetic_hit_id(hit: RetrievalHit) -> str:
        digest = hashlib.sha1(
            f"{hit.source}|{hit.path}|{hit.line_no or 0}|{hit.snippet or ''}".encode("utf-8")
        ).hexdigest()[:12]
        return f"unix_{hit.source}_{digest}"

    def _relative_path(self, path_obj: Path) -> str:
        try:
            return (
                path_obj.resolve().relative_to(self.unix_retrieval.repo_root.resolve()).as_posix()
            )
        except Exception:
            return path_obj.as_posix()

    def _graph_search(self, query: str, top_k: int) -> List[Event]:
        """
        图谱搜索 (Task 1.3)

        基于查询词（通常是因果实体/文件名）在图谱中进行 BFS 搜索，
        找到相关的 Event 节点。

        优化：添加 Capped BFS 截断机制，防止大规模节点导致性能问题。
        """
        if not self.graph_store:
            return []

        # 1. 解析查询 (假设查询是文件名或实体名)
        # 简单策略：直接作为节点 ID 查询
        node_id = query.strip()

        # 2. 从 GraphStore 获取相关事件
        # HEURISTIC 1: Check file history if it's a file
        event_ids = self.graph_store.get_file_history(node_id, limit=top_k)

        # HEURISTIC 2: If no history or not a file, find related entities then events
        if not event_ids:
            # BFS 搜索 1 层（带截断）
            related_entities = self._capped_find_related(node_id, depth=1)

            # 如果相关实体是 Event 类型，收集 ID
            for entity in related_entities:
                if entity.type == "event":
                    event_ids.append(entity.name)

        # 3. 加载 Event 对象
        results = []
        seen = set()

        for eid in event_ids:
            if eid in seen:
                continue
            seen.add(eid)

            # 尝试从 MarkdownStore 加载完整内容
            meta = self.graph_store.get_event_metadata(eid)
            if meta and "markdown_path" in meta:
                event = self.markdown_store.load(meta["markdown_path"])
                if event:
                    results.append(event)
                    if len(results) >= top_k:
                        break
            else:
                # Fallback: 如果无法加载完整 Event，构造一个简略版？
                pass

        return results[:top_k]

    def _capped_find_related(self, entity_name: str, depth: int = 1) -> List:
        """
        带截断的 BFS 查找相关实体

        防止大规模节点导致性能问题：
        - 单层最大扇出节点数限制 (MAX_FANOUT_PER_LEVEL)
        - 总探索节点数上限 (MAX_TOTAL_NODES)

        Returns:
            相关实体列表（已截断）
        """
        if not self.graph_store:
            return []

        # 使用 GraphStore 的 find_related 获取基础结果
        related_entities = self.graph_store.find_related(entity_name, depth=depth)

        # 应用截断：限制总节点数
        if len(related_entities) > self.MAX_FANOUT_PER_LEVEL:
            related_entities = related_entities[: self.MAX_FANOUT_PER_LEVEL]

        return related_entities


# 便捷函数
def create_search_engine() -> SearchEngine:
    """创建搜索引擎实例"""
    return SearchEngine()
