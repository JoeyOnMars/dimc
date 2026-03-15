from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from ..core.models import Event
from ..storage.markdown_store import MarkdownStore

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class RetrievalHit:
    source: str
    path: str
    kind: str
    title: Optional[str]
    snippet: Optional[str]
    line_no: Optional[int]
    score: float
    raw_id: Optional[str]


class UnixRetrievalService:
    """UNIX-native precision retrieval for events, docs, and code sources."""

    SOURCE_WEIGHTS = {
        "events": 0.9,
        "code": 0.85,
        "docs": 0.8,
    }

    SOURCE_GLOBS = {
        "events": ("*.md",),
        "docs": ("*.md", "*.yaml", "*.yml"),
        "code": ("*.py", "*.md", "*.sh", "*.zsh", "*.yaml", "*.yml", "*.toml"),
    }

    def __init__(
        self,
        markdown_store: Optional[MarkdownStore] = None,
        repo_root: Optional[Path] = None,
        include_agent_rules: bool = False,
    ):
        self.markdown_store = markdown_store or MarkdownStore()
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.include_agent_rules = include_agent_rules

    def resolve_source_roots(self) -> dict[str, list[Path]]:
        roots: dict[str, list[Path]] = {
            "events": [],
            "docs": [],
            "code": [],
        }

        base_dir = getattr(self.markdown_store, "base_dir", None)
        if base_dir:
            event_root = Path(base_dir)
            if event_root.exists():
                roots["events"].append(event_root)

        for relative in ("docs", "tmp/discussion"):
            candidate = self.repo_root / relative
            if candidate.exists():
                roots["docs"].append(candidate)

        for relative in ("src", "tests", "scripts"):
            candidate = self.repo_root / relative
            if candidate.exists():
                roots["code"].append(candidate)

        if self.include_agent_rules:
            agent_root = self.repo_root / ".agent"
            if agent_root.exists():
                roots["code"].append(agent_root)

        return roots

    def search_hits(
        self,
        query: str,
        top_k: int,
        sources: Optional[Iterable[str]] = None,
    ) -> list[RetrievalHit]:
        if not query.strip() or top_k <= 0:
            return []

        requested_sources = list(sources) if sources is not None else ["events", "code", "docs"]
        source_roots = self.resolve_source_roots()
        hits: list[RetrievalHit] = []

        for source in requested_sources:
            roots = source_roots.get(source, [])
            if not roots:
                continue
            hits.extend(self._search_source(source, query, roots, top_k))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def search_events(self, query: str, top_k: int) -> list[Event]:
        hits = self.search_hits(query=query, top_k=top_k, sources=("events",))
        results: list[Event] = []
        for hit in hits:
            event = self.markdown_store.load(hit.path)
            if event:
                results.append(event)
        return results[:top_k]

    def _search_source(
        self, source: str, query: str, roots: list[Path], top_k: int
    ) -> list[RetrievalHit]:
        result = self._run_rg(query=query, roots=roots, globs=self.SOURCE_GLOBS[source])
        if result is None or result.returncode == 1:
            return []
        if result.returncode != 0:
            return []

        return self._parse_rg_output(source=source, query=query, stdout=result.stdout, top_k=top_k)

    def _run_rg(
        self,
        query: str,
        roots: Iterable[Path],
        globs: Iterable[str],
    ) -> Optional[subprocess.CompletedProcess[str]]:
        cmd = [
            "rg",
            "--json",
            "--ignore-case",
            "--max-count",
            "1",
        ]
        for glob in globs:
            cmd.extend(["--glob", glob])
        cmd.append(query)
        cmd.extend(str(root) for root in roots)

        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def _parse_rg_output(
        self, source: str, query: str, stdout: str, top_k: int
    ) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        seen_paths: set[str] = set()

        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("type") != "match":
                continue

            data = payload.get("data", {})
            path_text = data.get("path", {}).get("text")
            if not path_text or path_text in seen_paths:
                continue

            lines_text = data.get("lines", {}).get("text", "").strip()
            line_number = data.get("line_number")
            path = Path(path_text)
            seen_paths.add(path_text)

            hits.append(
                RetrievalHit(
                    source=source,
                    path=path_text,
                    kind=self._kind_for_source(source),
                    title=path.stem,
                    snippet=lines_text or None,
                    line_no=line_number,
                    score=self._score_hit(
                        source=source, query=query, path=path, snippet=lines_text
                    ),
                    raw_id=path.stem if source == "events" else None,
                )
            )
            if len(hits) >= top_k:
                break

        return hits

    @staticmethod
    def _kind_for_source(source: str) -> str:
        if source == "events":
            return "event"
        if source == "code":
            return "code"
        return "document"

    def _score_hit(self, source: str, query: str, path: Path, snippet: str) -> float:
        score = self.SOURCE_WEIGHTS.get(source, 0.75)
        query_lower = query.lower()
        path_lower = path.as_posix().lower()

        if path.name.lower() == query_lower:
            score += 0.15
        elif path.stem.lower() == query_lower:
            score += 0.1
        elif query_lower in path_lower:
            score += 0.05

        if snippet and snippet.strip() == query.strip():
            score += 0.05

        return score
