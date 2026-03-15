"""
Claude Code JSONL Session Parser

Converts Claude Code per-session JSONL files into readable markdown transcripts
for ingestion by EventExtractor and ContextInjector.

File structure:
    ~/.claude/projects/{project-slug}/
        {sessionId}.jsonl                    <- Main session (flat)
        {sessionId}/                         <- Session subdirectory
            subagents/
                agent-{agentId}.jsonl        <- Subagent complete transcript
            tool-results/
                {hash}.txt                   <- Tool execution cache
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp to UTC-aware datetime."""
    if not ts_str:
        return None
    try:
        # Handle both 'Z' suffix and explicit offsets
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _local_naive_to_utc(dt: datetime) -> datetime:
    """Convert local naive datetime to UTC-aware datetime."""
    if dt.tzinfo is not None:
        return dt
    # Use current offset
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now()
    offset = now_utc - now_local
    return dt.replace(tzinfo=timezone.utc) + offset


@dataclass
class ClaudeSession:
    """Represents a matched Claude Code JSONL session."""

    jsonl_path: Path
    session_id: str  # UUID = filename stem
    slug: Optional[str]  # Human-readable session name
    first_ts: datetime  # UTC-aware, first record timestamp
    last_ts: datetime  # UTC-aware, last record timestamp
    git_branch: Optional[str] = None
    record_count: int = 0
    sidechain_paths: List[Path] = field(default_factory=list)


@dataclass
class DetectedJob:
    """A heuristically detected job boundary within a JSONL session."""

    start_ts: datetime
    end_ts: datetime
    first_user_message: str  # First user message text (for title)
    message_count: int
    session_id: str


@dataclass
class AgentJob:
    """Represents a subagent job extracted from Claude Code sessions."""

    agent_id: str  # "adde69a" (extracted from filename)
    jsonl_path: Path  # subagents/agent-adde69a.jsonl
    start_ts: datetime  # First record timestamp (UTC-aware)
    end_ts: datetime  # Last record timestamp (UTC-aware)
    goal: str  # First valid user message text (task description)
    result_summary: str  # Last assistant text message (truncated to 1000 chars)
    full_markdown: str  # parse_to_markdown() output for EventExtractor


def _extract_first_user_text(records: List[dict]) -> str:
    """Extract first valid user message text from records."""
    for rec in records:
        if rec.get("type") != "user":
            continue
        content = rec.get("message", {}).get("content", [])
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text = item.get("text", "").strip()
                    if text and not text.startswith(("<ide_", "<context>", "<system")):
                        return text[:500]
    return ""


def _extract_last_assistant_text(records: List[dict]) -> str:
    """Extract last assistant text message from records."""
    assistant_texts = []
    for rec in records:
        if rec.get("type") != "assistant":
            continue
        content = rec.get("message", {}).get("content", [])
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text = item.get("text", "").strip()
                    if text:
                        assistant_texts.append(text)

    if assistant_texts:
        result = assistant_texts[-1]
        return result[:1000] if len(result) > 1000 else result
    return ""


class ClaudeCodeLogParser:
    """Parser for Claude Code JSONL session files."""

    # Types to include in markdown
    INCLUDE_TYPES = {"user", "assistant"}

    # Content types to skip
    SKIP_CONTENT_TYPES = {"thinking", "tool_result"}

    # Text prefixes to skip in user messages
    SKIP_TEXT_PREFIXES = ("<ide_", "<context>", "<system")

    def __init__(
        self,
        root_dir: Optional[Path] = None,
        sessions_dir: Optional[Path] = None,
    ):
        self.root_dir = root_dir
        self.sessions_dir = self._resolve_sessions_dir(sessions_dir)

    def _resolve_sessions_dir(self, sessions_dir: Optional[Path]) -> Optional[Path]:
        """Resolve sessions directory from config or auto-detect."""
        if sessions_dir:
            return sessions_dir if sessions_dir.exists() else None

        if not self.root_dir:
            return None

        # Auto-detect: ~/.claude/projects/{project-slug}/
        # project_slug = str(root_dir).replace('/', '-')  # keeps leading '-'
        # But actual path uses full path with slashes replaced by hyphens
        project_slug = str(self.root_dir).replace("/", "-").lstrip("-")
        candidate = Path.home() / ".claude" / "projects" / project_slug

        if candidate.exists() and any(candidate.glob("*.jsonl")):
            return candidate

        # Try with leading hyphen preserved
        candidate = Path.home() / ".claude" / "projects" / f"-{project_slug}"
        if candidate.exists() and any(candidate.glob("*.jsonl")):
            return candidate

        return None

    def find_sessions(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[ClaudeSession]:
        """Find Claude Code sessions matching the time window."""
        if not self.sessions_dir:
            logger.debug("No Claude Code sessions directory found.")
            return []

        # Extend window to match AG_Exports logic
        search_start = start_time - timedelta(seconds=3600)
        search_end = end_time + timedelta(seconds=300)

        sessions: List[ClaudeSession] = []
        seen_slugs: dict = {}

        for jsonl_path in self.sessions_dir.glob("*.jsonl"):
            if jsonl_path.is_dir():
                continue

            try:
                first_ts = None
                last_ts = None
                session_id = jsonl_path.stem
                slug = None
                git_branch = None
                record_count = 0

                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            record_count += 1

                            ts_str = d.get("timestamp")
                            if ts_str:
                                ts = _parse_timestamp(ts_str)
                                if ts:
                                    if first_ts is None:
                                        first_ts = ts
                                    last_ts = ts

                            if not slug and d.get("slug"):
                                slug = d["slug"]
                            if not git_branch and d.get("gitBranch"):
                                git_branch = d["gitBranch"]

                        except json.JSONDecodeError:
                            continue

                # Skip empty files (no user/assistant records)
                if first_ts is None or last_ts is None:
                    continue

                # Window overlap test
                if not (first_ts <= search_end and last_ts >= search_start):
                    continue

                # Deduplicate by slug: prefer larger file
                if slug:
                    if slug in seen_slugs:
                        existing = seen_slugs[slug]
                        if existing.record_count >= record_count:
                            continue  # Keep existing, skip this one
                        # Replace existing with larger
                        sessions = [s for s in sessions if s.session_id != existing.session_id]
                    seen_slugs[slug] = ClaudeSession(
                        jsonl_path=jsonl_path,
                        session_id=session_id,
                        slug=slug,
                        first_ts=first_ts,
                        last_ts=last_ts,
                        git_branch=git_branch,
                        record_count=record_count,
                    )
                    sessions.append(seen_slugs[slug])
                else:
                    # No slug, use session_id directly
                    sessions.append(
                        ClaudeSession(
                            jsonl_path=jsonl_path,
                            session_id=session_id,
                            slug=slug,
                            first_ts=first_ts,
                            last_ts=last_ts,
                            git_branch=git_branch,
                            record_count=record_count,
                        )
                    )

            except Exception as e:
                logger.debug(f"Error parsing {jsonl_path}: {e}")
                continue

        # Sort by first_ts ascending
        sessions.sort(key=lambda s: s.first_ts)
        return sessions

    def parse_to_markdown(
        self,
        session: ClaudeSession,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_chars: int = 80_000,
    ) -> str:
        """Parse a session to markdown transcript."""
        records = self._load_and_filter_records(session, start_time, end_time)

        if not records:
            return ""

        # Detect job segments
        jobs = self._detect_jobs(records)

        # Build markdown
        parts = []

        # Header
        local_first = session.first_ts.astimezone().strftime("%Y-%m-%d %H:%M")
        local_last = session.last_ts.astimezone().strftime("%Y-%m-%d %H:%M")
        parts.append(f"# Claude Code Session: {session.slug or session.session_id}")
        parts.append("")
        parts.append(f"**Session ID**: {session.session_id}")
        parts.append(f"**Branch**: {session.git_branch or 'N/A'}")
        parts.append(f"**Time Range**: {local_first} — {local_last}")
        parts.append("")

        # Job segments
        if jobs:
            for i, job in enumerate(jobs, 1):
                parts.append("---")
                title = (
                    job.first_user_message[:60] + "..."
                    if len(job.first_user_message) > 60
                    else job.first_user_message
                )
                parts.append(f"## Detected Job Segment {i}: {title}")
                parts.append(
                    f"*{job.start_ts.astimezone().strftime('%H:%M')} — {job.end_ts.astimezone().strftime('%H:%M')}*"
                )
                parts.append("")

                # Add messages in this segment
                segment_start_ts = job.start_ts.timestamp()
                segment_end_ts = job.end_ts.timestamp()

                for rec in records:
                    ts_str = rec.get("timestamp")
                    if ts_str:
                        ts = _parse_timestamp(ts_str)
                        if ts:
                            rec_ts = ts.timestamp()
                            if rec_ts < segment_start_ts or rec_ts > segment_end_ts:
                                continue

                    self._append_message_markdown(parts, rec)

                parts.append("")
        else:
            # No job segmentation, just append all messages
            for rec in records:
                self._append_message_markdown(parts, rec)

        markdown = "\n".join(parts)

        # Truncate if too long
        if len(markdown) > max_chars:
            # Find last message boundary before max_chars
            last_user_pos = markdown.rfind("### USER ", 0, max_chars)
            last_asst_pos = markdown.rfind("### ASSISTANT ", 0, max_chars)
            cutoff = max(last_user_pos, last_asst_pos)
            if cutoff > 0:
                markdown = markdown[:cutoff] + "\n\n... (truncated)"
                logger.warning(f"Markdown truncated from {len(markdown)} to {max_chars} chars")

        return markdown

    def _load_and_filter_records(
        self,
        session: ClaudeSession,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> List[dict]:
        """Load and filter records from JSONL."""
        records = []

        try:
            with open(session.jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)

                        # Skip non-message types
                        if d.get("type") not in self.INCLUDE_TYPES:
                            continue

                        # Skip sidechain (sub-agent) messages in main session
                        if d.get("isSidechain", False):
                            continue

                        # Time window filter
                        ts_str = d.get("timestamp")
                        if ts_str and (start_time or end_time):
                            ts = _parse_timestamp(ts_str)
                            if ts:
                                if start_time and ts < start_time:
                                    continue
                                if end_time and ts > end_time:
                                    continue

                        records.append(d)

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to load {session.jsonl_path}: {e}")

        # Sort by timestamp
        records.sort(key=lambda r: r.get("timestamp", ""))
        return records

    def _append_message_markdown(self, parts: List[str], record: dict):
        """Append a single message as markdown."""
        msg_type = record.get("type")
        ts_str = record.get("timestamp", "")
        ts = _parse_timestamp(ts_str)
        ts_formatted = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts else ""

        role = "USER" if msg_type == "user" else "ASSISTANT"
        parts.append(f"### {role} ({ts_formatted})")

        content = record.get("message", {}).get("content", [])
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue

                item_type = item.get("type")

                # Skip unwanted types
                if item_type in self.SKIP_CONTENT_TYPES:
                    continue

                if item_type == "text":
                    text = item.get("text", "").strip()
                    # Skip IDE context injections
                    if text and not text.startswith(self.SKIP_TEXT_PREFIXES):
                        parts.append(text)
                        parts.append("")

                elif item_type == "tool_use":
                    name = item.get("name", "Unknown")
                    inp = item.get("input", {})

                    # Extract key input for summary
                    key = None
                    for key_name in ("command", "file_path", "pattern", "query"):
                        if key_name in inp:
                            key = str(inp[key_name])
                            break

                    if key:
                        key = key[:80]  # Truncate for summary
                        parts.append(f"> **[{name}]** `{key}`")
                    else:
                        parts.append(f"> **[{name}]**")
                    parts.append("")

        parts.append("")

    def _detect_jobs(
        self,
        records: List[dict],
        gap_threshold_seconds: int = 600,
    ) -> List[DetectedJob]:
        """Detect job boundaries based on time gaps."""
        if not records:
            return []

        # Extract user messages with timestamps
        user_messages = []
        for rec in records:
            if rec.get("type") != "user":
                continue

            ts_str = rec.get("timestamp")
            if not ts_str:
                continue
            ts = _parse_timestamp(ts_str)
            if not ts:
                continue

            content = rec.get("message", {}).get("content", [])
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        text = item.get("text", "").strip()
                        # Skip noise
                        if text and not text.startswith(self.SKIP_TEXT_PREFIXES):
                            user_messages.append((ts, text))
                            break

        if len(user_messages) < 2:
            return []

        # Find gaps
        jobs: List[DetectedJob] = []
        current_start_ts, current_msg = user_messages[0]
        current_messages = 1
        session_id = ""

        for i in range(1, len(user_messages)):
            ts, msg = user_messages[i]
            gap = (ts - user_messages[i - 1][0]).total_seconds()

            if gap >= gap_threshold_seconds:
                # New job boundary
                jobs.append(
                    DetectedJob(
                        start_ts=current_start_ts,
                        end_ts=user_messages[i - 1][0],
                        first_user_message=current_msg,
                        message_count=current_messages,
                        session_id=session_id,
                    )
                )
                current_start_ts = ts
                current_msg = msg
                current_messages = 1
            else:
                current_messages += 1

        # Don't forget the last job
        if current_messages > 0:
            jobs.append(
                DetectedJob(
                    start_ts=current_start_ts,
                    end_ts=user_messages[-1][0],
                    first_user_message=current_msg,
                    message_count=current_messages,
                    session_id=session_id,
                )
            )

        return jobs

    def extract_agent_jobs(self, session: ClaudeSession) -> List[AgentJob]:
        """
        Extract subagent jobs from {sessionId}/subagents/ directory.

        Scans for agent-*.jsonl files and extracts job information:
        - agent_id from filename
        - goal from first user message
        - result_summary from last assistant message
        - full_markdown for EventExtractor
        """
        jobs: List[AgentJob] = []

        # Find the subagents directory: {sessions_dir}/{session_id}/subagents/
        sessions_dir = self.sessions_dir
        if not sessions_dir:
            return jobs

        subagents_dir = sessions_dir / session.session_id / "subagents"
        if not subagents_dir.exists() or not subagents_dir.is_dir():
            logger.debug(f"Subagents directory not found: {subagents_dir}")
            return jobs

        # Scan for agent-*.jsonl files
        for agent_file in subagents_dir.glob("agent-*.jsonl"):
            try:
                agent_id = agent_file.stem.replace("agent-", "")  # Remove "agent-" prefix

                # Load all records
                records = []
                with open(agent_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            if d.get("type") in self.INCLUDE_TYPES:
                                records.append(d)
                        except json.JSONDecodeError:
                            continue

                if not records:
                    continue

                # Sort by timestamp
                records.sort(key=lambda r: r.get("timestamp", ""))

                # Extract timestamps
                first_ts = None
                last_ts = None
                for rec in records:
                    ts_str = rec.get("timestamp")
                    if ts_str:
                        ts = _parse_timestamp(ts_str)
                        if ts:
                            if first_ts is None:
                                first_ts = ts
                            last_ts = ts

                if not first_ts or not last_ts:
                    continue

                # Extract goal and result
                goal = _extract_first_user_text(records)
                result_summary = _extract_last_assistant_text(records)

                # Generate full markdown
                full_markdown = self._parse_single_agent_to_markdown(records, agent_id)

                jobs.append(
                    AgentJob(
                        agent_id=agent_id,
                        jsonl_path=agent_file,
                        start_ts=first_ts,
                        end_ts=last_ts,
                        goal=goal,
                        result_summary=result_summary,
                        full_markdown=full_markdown,
                    )
                )

            except Exception as e:
                logger.warning(f"Error extracting agent job from {agent_file}: {e}")
                continue

        return jobs

    def _parse_single_agent_to_markdown(self, records: List[dict], agent_id: str) -> str:
        """Parse a single agent's records to markdown."""
        parts = []
        parts.append(f"# Claude Code Subagent: {agent_id}")
        parts.append("")

        for rec in records:
            self._append_message_markdown(parts, rec)

        return "\n".join(parts)


def find_claude_sessions_dir(root_dir: Path) -> Optional[Path]:
    """Utility function to find Claude Code sessions directory for a project."""
    # Try with leading hyphen preserved
    project_slug = f"-{str(root_dir).replace('/', '-').lstrip('-')}"
    candidate = Path.home() / ".claude" / "projects" / project_slug

    if candidate.exists() and any(candidate.glob("*.jsonl")):
        return candidate

    # Try without leading hyphen
    project_slug = str(root_dir).replace("/", "-").lstrip("-")
    candidate = Path.home() / ".claude" / "projects" / project_slug

    if candidate.exists() and any(candidate.glob("*.jsonl")):
        return candidate

    return None
