"""
Dimcause Core Pipeline
负责处理从 Watcher 接收到的 RawData，执行安全检测、信息提取并分发到存储层。
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from dimcause.core.event_index import EventIndex
from dimcause.core.models import DimcauseConfig, Event, RawData
from dimcause.extractors import ASTAnalyzer, BasicExtractor, LiteLLMClient
from dimcause.objects import attach_object_projection, project_raw_event_bundle
from dimcause.reasoning.causal import CausalLink
from dimcause.reasoning.causal_engine import CAUSAL_RELATIONS_SET, CausalEngine
from dimcause.reasoning.engine import HybridInferenceEngine
from dimcause.reasoning.relation_inference import infer_directed_ontology_relation
from dimcause.storage import GraphStore, MarkdownStore, VectorStore
from dimcause.utils.security import get_detector, sanitize_text
from dimcause.utils.wal import WriteAheadLog

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Data Processing Pipeline
    RawData -> Security -> Extraction -> Storage
    """

    REASONING_CANDIDATE_LIMIT = 12

    def __init__(
        self, config: Optional[DimcauseConfig] = None, wal_manager: Optional[WriteAheadLog] = None
    ):
        self.config = config or DimcauseConfig()
        self.wal = wal_manager

        # Initialize Components
        self._setup_storage()
        self._setup_extractors()
        self._setup_reasoning()

        # Security & Reliability
        self._security_detector = get_detector(enabled=True)

        self._event_count = 0

    def _setup_storage(self):
        data_dir = Path(os.path.expanduser(self.config.data_dir))
        data_dir.mkdir(parents=True, exist_ok=True)

        self.markdown_store = MarkdownStore(base_dir=str(data_dir / "events"))
        self.event_index = EventIndex(db_path=str(data_dir / "index.db"))
        self.vector_store = VectorStore(
            persist_dir=str(data_dir / "chroma"),
            db_path=str(data_dir / "index.db"),
        )
        self.graph_store = GraphStore(db_path=str(data_dir / "graph.db"))

    def _setup_extractors(self):
        # LLM Client
        if LiteLLMClient:
            try:
                self.llm_client = LiteLLMClient(
                    config=self.config.llm_primary, fallback_config=self.config.llm_fallback
                )
            except Exception as e:
                logger.warning(f"LLM client init failed: {e}")
                self.llm_client = None
        else:
            self.llm_client = None

        # Extractor
        if self.llm_client and BasicExtractor:
            try:
                self.extractor = BasicExtractor(llm_client=self.llm_client)
            except Exception:
                self.extractor = None
        else:
            self.extractor = None

        # AST Analyzer
        self.ast_analyzer = ASTAnalyzer()

    def _setup_reasoning(self):
        try:
            self.reasoning_engine = HybridInferenceEngine()
        except Exception as e:
            logger.warning(f"Reasoning engine init failed: {e}")
            self.reasoning_engine = None

        self.causal_engine = CausalEngine(graph_store=self.graph_store)

    def process(self, raw: RawData) -> None:
        """
        Process incoming RawData through the pipeline.
        """
        # 1. WAL: Write (if configured)
        if self.wal:
            self.wal.append_pending(raw.id, raw.model_dump())

        event_id = f"evt_{raw.id}_{int(time.time())}"

        try:
            logger.info(
                f"📥 Pipeline received: {raw.id} from {getattr(raw.source, 'value', str(raw.source))}"
            )

            # 2. Security: Sanitize
            sanitized_content, findings = sanitize_text(raw.content)
            if findings:
                logger.warning(f"🔒 Redacted {len(findings)} sensitive items in {event_id}")

            # 3. Layer 2: Extract Event
            extractor = self.extractor
            if not extractor:
                # Fallback to BasicExtractor to attempt type inference
                from dimcause.extractors.extractor import BasicExtractor

                extractor = BasicExtractor()

            event = extractor.extract(sanitized_content)
            event.raw_data_id = raw.id
            event.source = raw.source
            self._merge_raw_context(raw, event)

            # Add security metadata
            if findings:
                if not event.metadata:
                    event.metadata = {}
                event.metadata["redacted"] = True
                event.metadata["redacted_count"] = len(findings)

            # 4. AST Analysis (Code Entities)
            self._analyze_code_entities(raw, event)

            # 5. 对象投影：在保留 Event 主链的同时，挂入最小对象视图。
            attach_object_projection(event, project_raw_event_bundle(raw, event))

            # 5. Layer 3: Storage
            self._save_event(event)
            self._link_event(event)

            self._event_count += 1
            logger.info(
                f"✅ Processed: {getattr(event.type, 'value', str(event.type))} - {event.summary[:50]}..."
            )

            # 6. WAL: ACK
            if self.wal:
                self.wal.mark_completed(raw.id)

        except Exception as e:
            logger.error(f"Pipeline error processing {event_id}: {e}")
            # Note: We do NOT mark done here, so it remains pending for retry/recovery
            raise e

    def _analyze_code_entities(self, raw: RawData, event: Event):
        for file_path in raw.files_mentioned:
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        code = f.read()

                    from dimcause.extractors.ast_analyzer import detect_language

                    lang = detect_language(file_path)

                    if lang != "unknown":
                        funcs = self.ast_analyzer.extract_functions(code, lang, file_path)
                        classes = self.ast_analyzer.extract_classes(code, lang, file_path)
                        event.code_entities.extend(funcs)
                        event.code_entities.extend(classes)
                except Exception as e:
                    logger.debug(f"AST analysis failed for {file_path}: {e}")

    def _merge_raw_context(self, raw: RawData, event: Event) -> None:
        raw_meta = dict(raw.metadata or {})
        event_meta = dict(event.metadata or {})
        merged_meta = {**raw_meta, **event_meta}

        if raw.project_path and "project_path" not in merged_meta:
            merged_meta["project_path"] = raw.project_path

        related_files: List[str] = []
        seen_files = set()
        for file_path in [*(event.related_files or []), *(raw.files_mentioned or [])]:
            normalized = str(file_path).strip()
            if not normalized or normalized in seen_files:
                continue
            seen_files.add(normalized)
            related_files.append(normalized)

        if related_files:
            merged_meta.setdefault("files_mentioned", related_files)
            if len(related_files) == 1 and "module_path" not in merged_meta:
                merged_meta["module_path"] = related_files[0]

        event.metadata = merged_meta
        event.related_files = related_files

    def _load_reasoning_candidates(self, event: Event) -> List[Event]:
        candidates: List[Event] = []
        rows = self.event_index.query(limit=self.REASONING_CANDIDATE_LIMIT * 4)
        for row in rows:
            if row["id"] == event.id:
                continue
            candidate = self.event_index.load_event(row["id"])
            if candidate is None:
                continue
            if self._shares_reasoning_context(event, candidate):
                candidates.append(candidate)
            if len(candidates) >= self.REASONING_CANDIDATE_LIMIT:
                break
        return candidates

    def _shares_reasoning_context(self, event: Event, candidate: Event) -> bool:
        event_meta = event.metadata or {}
        candidate_meta = candidate.metadata or {}

        session_id = event_meta.get("session_id")
        if session_id and session_id == candidate_meta.get("session_id"):
            return True

        job_id = event_meta.get("job_id")
        if job_id and job_id == candidate_meta.get("job_id"):
            return True

        module_path = event_meta.get("module_path")
        if module_path and module_path == candidate_meta.get("module_path"):
            return True

        current_files = set(event.related_files or [])
        candidate_files = set(candidate.related_files or [])
        if current_files and candidate_files and current_files & candidate_files:
            return True

        return False

    def _link_event(self, event: Event) -> None:
        links_written = 0

        links_written += self._link_explicit_relations(event)

        if self.reasoning_engine:
            candidates = self._load_reasoning_candidates(event)
            if candidates:
                try:
                    inferred_links = self.reasoning_engine.infer([*candidates, event])
                    event_lookup: Dict[str, Event] = {event.id: event}
                    for candidate in candidates:
                        event_lookup[candidate.id] = candidate
                    links_written += self._persist_reasoning_links(
                        event, inferred_links, event_lookup
                    )
                except Exception as e:
                    logger.warning(f"Reasoning inference failed for {event.id}: {e}")

        if links_written:
            logger.info("🧠 Linked %s reasoning edges for %s", links_written, event.id)

    def _link_explicit_relations(self, event: Event) -> int:
        related_ids = event.related_event_ids or []
        links_written = 0

        for target_id in related_ids:
            target_raw = self.event_index.get_by_id(target_id)
            if target_raw is None:
                logger.warning("Explicit relation target missing: %s", target_id)
                continue

            target_event = self.event_index.load_event(target_id)
            if target_event is None:
                logger.warning("Explicit relation target failed to load: %s", target_id)
                continue

            relation_info = infer_directed_ontology_relation(event, target_event)
            if relation_info is None:
                logger.warning(
                    "No ontology relation available for explicit link: %s -> %s",
                    event.id,
                    target_id,
                )
                continue

            relation, source_event, target_event = relation_info
            metadata = {
                "strategy": "explicit_reference",
                "source_event_id": event.id,
                "target_event_id": target_event.id,
            }
            if self._persist_reasoning_link(
                CausalLink(
                    source=source_event.id,
                    target=target_event.id,
                    relation=relation,
                    weight=1.0,
                    metadata=metadata,
                ),
                {event.id: event, target_event.id: target_event},
            ):
                links_written += 1

        return links_written

    def _persist_reasoning_links(
        self,
        event: Event,
        links: List[CausalLink],
        event_lookup: Dict[str, Event],
    ) -> int:
        written = 0
        seen_edges = set()

        for link in links:
            if event.id not in {link.source, link.target}:
                continue

            edge_key = (link.source, link.target, link.relation)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            if self._persist_reasoning_link(link, event_lookup):
                written += 1

        return written

    def _persist_reasoning_link(self, link: CausalLink, event_lookup: Dict[str, Event]) -> bool:
        source_event = event_lookup.get(link.source)
        target_event = event_lookup.get(link.target)
        if source_event is None or target_event is None:
            logger.warning(
                "Reasoning link references unknown event(s): %s -> %s", link.source, link.target
            )
            return False

        metadata = {
            **(link.metadata or {}),
            "pipeline_reasoning": True,
        }

        try:
            if link.relation in CAUSAL_RELATIONS_SET:
                self.causal_engine.link_causal(
                    source=source_event,
                    target=target_event,
                    relation=link.relation,
                    weight=link.weight,
                    metadata=metadata,
                )
            else:
                self.graph_store.add_semantic_relation(
                    source=source_event.id,
                    target=target_event.id,
                    relation=link.relation,
                    weight=link.weight,
                    metadata=metadata,
                )
            if not self.event_index.upsert_links(link.source, [link]):
                logger.warning("EventIndex link upsert failed for owner %s", link.source)
            return True
        except Exception as e:
            logger.warning(
                "Reasoning link persistence failed for %s --%s--> %s: %s",
                link.source,
                link.relation,
                link.target,
                e,
            )
            return False

    def _save_event(self, event: Event):
        try:
            markdown_path = self.markdown_store.save(event)
        except Exception as e:
            logger.error(f"Markdown save failed: {e}")
            raise

        try:
            ok = self.event_index.add(event, markdown_path)
            if not ok:
                raise RuntimeError(f"EventIndex add returned False for {event.id}")
        except Exception as e:
            logger.error(f"EventIndex save failed: {e}")
            raise

        # Vector
        try:
            self.vector_store.add(event)
        except Exception as e:
            logger.warning(f"Vector save failed: {e}")

        # Graph
        try:
            self.graph_store.add_event_relations(event)
        except Exception as e:
            logger.warning(f"Graph save failed: {e}")

    def get_stats(self):
        return {
            "event_count": self._event_count,
            "indexed_event_db": str(self.event_index.db_path) if self.event_index else "",
            "graph_stats": self.graph_store.stats() if self.graph_store else {},
        }
