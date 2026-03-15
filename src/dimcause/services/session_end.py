"""
Session End Service (L0)

编排 Session End 流程的业务逻辑层。
负责协调 L1 (DataCollector), L2 (ContextInjector, EventIndex) 等组件。
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from dimcause.audit.context_injector import ContextInjector
from dimcause.core.event_index import EventIndex
from dimcause.core.indexer import update_index
from dimcause.extractors.data_collector import DataCollector, SessionData
from dimcause.extractors.extraction_pipeline import ExtractionPipeline
from dimcause.services.workflow import create_daily_log
from dimcause.storage.chunk_store import ChunkStore
from dimcause.storage.graph_store import GraphStore
from dimcause.storage.vector_store import VectorStore
from dimcause.utils.config import get_config
from dimcause.utils.state import get_session_start_timestamp


class SessionEndService:
    def __init__(self, console: Optional[Console] = None):
        self.config = get_config()
        self.root_dir = self.config.root_dir
        self.console = console or Console()
        self.injector = ContextInjector(self.root_dir)

    def execute(
        self, session_id: str, date_str: str, end_timestamp: Optional[datetime] = None
    ) -> bool:
        """执行 Session End 流程"""

        # 1. 采集数据 (L1)
        self.console.print("[dim]Collecting session data...[/]")
        start_ts = get_session_start_timestamp(session_id)
        if start_ts and end_timestamp:
            self.console.print(
                f"[dim]Using time window: {start_ts.strftime('%H:%M:%S')} to {end_timestamp.strftime('%H:%M:%S')}[/]"
            )

        collector = DataCollector(
            session_id, date_str, session_start=start_ts, session_end=end_timestamp
        )
        session_data = collector.collect_all()
        self._print_data_summary(session_data)

        # Interactive Check: If no critical data found, warn user
        # (Preserves legacy CLI behavior)
        has_logs = bool(session_data.raw_chat_files or session_data.external_source_files)
        has_brain = bool(session_data.brain_artifacts or session_data.brain_metadata)

        if not has_logs and not has_brain:
            from rich.prompt import Confirm

            self.console.print("[yellow]⚠️  No Session Data Found (No Logs, No Brain Artifacts)[/]")
            self.console.print(
                "   Current configuration might be missing 'brain_dir' or 'export_dir' targets."
            )
            if not Confirm.ask("Continue with empty session end?", default=False):
                self.console.print("[red]Aborted by user.[/]")
                return False
        elif not has_logs:
            self.console.print("[yellow]⚠️  No AI Logs found.[/]")
            # We assume brain artifacts might be enough, but warn anyway
            # The original CLI stopped if no logs were found.
            # Let's be gentle but informative.
            from rich.prompt import Confirm

            if not Confirm.ask("No AI logs detected. Continue?", default=True):
                return False

        # 2. 创建 end.md (L0)
        res = create_daily_log("end")
        if res.data and "path" in res.data:
            # success=True (新建) 或 success=False but file exists (复用)
            log_path = Path(res.data["path"])
            if not res.success:
                self.console.print(f"[yellow]Using existing log: {log_path.name}[/]")
        else:
            self.console.print(f"[red]{res.message}[/]")
            return False

        # 3. 注入上下文 (L2)
        self.console.print(f"[dim]Injecting context into {log_path.name}...[/]")
        self.injector.inject(log_path, session_data=session_data)

        # 3.5 生成 Claude Code Subagent Job 文件
        self._generate_claude_code_jobs(session_data, date_str)

        # 4. 运行 ExtractionPipeline (L1 + 可选 L2)
        self.console.print("[bold]Running ExtractionPipeline...[/]")
        self._run_extraction_pipeline(session_id)

        # 4.5 Auto-Embedding 兜底 (Task 013)
        self._auto_embed_recent_events()

        return True

    def _run_extraction_pipeline(self, session_id: str) -> None:
        """运行 ExtractionPipeline 流水线。"""
        config = get_config()
        data_dir = config.data_dir

        # 实例化存储层
        chunk_store = ChunkStore(db_path=data_dir / "chunks.db")
        event_index = EventIndex(db_path=data_dir / "index.db")
        graph_store = GraphStore(db_path=data_dir / "graph.db")

        # 实例化流水线
        pipeline = ExtractionPipeline(
            event_index=event_index,
            graph_store=graph_store,
            chunk_store=chunk_store,
        )

        # 执行
        stats = pipeline.run(session_id)

        # 打印统计
        self.console.print(
            Panel(
                f"[bold]L1 Events:[/] {stats['l1_count']}\n"
                f"[bold]L2 Events:[/] {stats['l2_count']}\n"
                f"[bold]Errors:[/]   {stats['errors']}",
                title="Extraction Stats",
            )
        )

    def finalize(self, session_id: str) -> bool:
        """完成 Session End: 更新索引和提交 Git"""

        # 1. Update Index
        self.console.print("[dim]Updating knowledge index...[/]")
        try:
            stats = update_index()
            # 简单展示 stats
            self.console.print(
                f"[green]Index Updated[/]: Processed {stats.get('processed', 0)} files"
            )
        except Exception as e:
            self.console.print(f"[red]Index update failed: {e}[/]")
            # Index failure shouldn't stop the process? Probably not.

        # 2. Git Commit
        if self.config.git_integration:
            self.console.print("[dim]Committing to Git...[/]")
            try:
                # Add all changes
                subprocess.run(["git", "add", "."], cwd=self.root_dir, check=True)

                # Commit message
                msg = f"docs: session end {self.config.agent_id} {session_id}"
                subprocess.run(
                    ["git", "commit", "-m", msg], cwd=self.root_dir, check=False
                )  # check=False in case nothing to commit
                self.console.print("[green]Git commit successful[/]")
            except subprocess.CalledProcessError as e:
                self.console.print(f"[red]Git commit failed: {e}[/]")

        return True

    def _print_data_summary(self, data: SessionData):
        """打印采集统计 (TUI)"""
        brain_files = len(data.brain_artifacts)
        raw_chats = len(data.raw_chat_files)
        ext_files = len(data.external_source_files)
        job_logs = len(data.job_logs)
        jsonl_sessions = len(data.claude_code_sessions)
        git_len = len(data.git_diff) + len(data.git_log)

        msg = (
            f"Brain Artifacts: [bold]{brain_files}[/]\n"
            f"Raw Chats:       [bold]{raw_chats}[/] (AG_Exports)\n"
            f"JSONL Sessions:   [bold]{jsonl_sessions}[/] (Claude Code)\n"
            f"External Files:  [bold]{ext_files}[/] (Claude/Other)\n"
            f"Job Logs:        [bold]{job_logs}[/]\n"
            f"Git Context:     [bold]{git_len} chars[/]"
        )
        self.console.print(Panel(msg, title="L1 Data Collection Summary", border_style="blue"))

    def _generate_claude_code_jobs(self, session_data: SessionData, date_str: str):
        """生成 Claude Code Subagent Job 文件。"""
        if not session_data.claude_code_sessions:
            return

        try:
            from dimcause.extractors.claude_code_parser import ClaudeCodeLogParser
            from dimcause.utils.config import get_config

            config = get_config()
            sessions_dir = config.claude_code_sessions_dir
            if not sessions_dir:
                return

            parser = ClaudeCodeLogParser(root_dir=config.root_dir, sessions_dir=sessions_dir)

            # Find the logs directory
            logs_dir = config.root_dir / "docs/logs" / date_str / "jobs"
            jobs_generated = 0

            for session in session_data.claude_code_sessions:
                jobs = parser.extract_agent_jobs(session)

                for job in jobs:
                    # Generate job_id with cc- prefix
                    job_id = f"cc-{job.agent_id[:8]}"  # Use first 8 chars of agent_id
                    job_dir = logs_dir / job_id

                    # Skip if already exists (don't overwrite manual edits)
                    job_start = job_dir / "job-start.md"
                    job_end = job_dir / "job-end.md"

                    if job_start.exists() or job_end.exists():
                        self.console.print(f"[dim]Skipping existing job: {job_id}[/]")
                        continue

                    # Create job directory
                    job_dir.mkdir(parents=True, exist_ok=True)

                    # Write job-start.md
                    start_content = f"""---
type: job-start
job_id: "{job_id}"
date: "{date_str}"
status: active
generated_by: claude_code_jsonl
---

# Job: {job_id}

## Goal
> {job.goal[:500] if job.goal else "N/A"}

## Notes
- Agent ID: {job.agent_id}
- Start Time: {job.start_ts.astimezone().strftime("%Y-%m-%d %H:%M:%S")}
- Source: Claude Code Subagent
"""
                    job_start.write_text(start_content, encoding="utf-8")

                    # Write job-end.md
                    end_content = f"""---
type: job-end
job_id: "{job_id}"
date: "{date_str}"
status: done
description: "Claude Code Subagent 自动生成"
tags: ["claude-code", "subagent", "auto-generated"]
generated_by: claude_code_jsonl
---

# Job Complete: {job_id}

## Summary
{job.result_summary[:1000] if job.result_summary else "N/A"}

## Metadata
- Agent ID: {job.agent_id}
- Start Time: {job.start_ts.astimezone().strftime("%Y-%m-%d %H:%M:%S")}
- End Time: {job.end_ts.astimezone().strftime("%Y-%m-%d %H:%M:%S")}
- Source: Claude Code Subagent (auto-generated)

## Full Transcript
{job.full_markdown[:5000] if job.full_markdown else "N/A"}...
"""
                    job_end.write_text(end_content, encoding="utf-8")

                    jobs_generated += 1
                    self.console.print(f"[green]Generated job: {job_id}[/]")

            if jobs_generated > 0:
                self.console.print(f"[green]Generated {jobs_generated} Claude Code job files[/]")

        except Exception as e:
            self.console.print(f"[yellow]Job generation skipped: {e}[/]")

    def _auto_embed_recent_events(self, limit: int = 30) -> None:
        """Auto-Embedding 兜底：自动找出尚未嵌入的事件并批量向量化"""
        import logging
        import os
        import sqlite3

        from dimcause.core.event_index import Event

        logger = logging.getLogger(__name__)

        # 使用 config.data_dir
        db_path = self.config.data_dir / "index.db"

        if not os.path.exists(str(db_path)):
            logger.info("Auto-embedding skipped: index.db does not exist")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(db_path))

            # 防护风险 1：确保 event_vectors 表存在
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS event_vectors (
                        event_id TEXT,
                        chunk_seq INTEGER,
                        chunk_pos INTEGER,
                        chunk_text TEXT,
                        embedding BLOB,
                        PRIMARY KEY (event_id, chunk_seq)
                    )
                """)
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.info(f"Auto-embedding skipped: event_vectors table error: {e}")
                return

            # 核心 SQL：差集 + LIMIT + 从最老孤儿开始
            cursor.execute(
                """
                SELECT id, json_cache
                FROM events
                WHERE id NOT IN (SELECT DISTINCT event_id FROM event_vectors)
                ORDER BY id ASC
                LIMIT ?
            """,
                (min(limit, 100),),
            )

            rows = cursor.fetchall()
            if not rows:
                logger.info("Auto-embedding: no orphan events found")
                return

            # 解析 json_cache → List[Event]
            events = []
            parse_failures = 0
            for event_id, json_cache in rows:
                try:
                    if json_cache:
                        event = Event.model_validate_json(json_cache)
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Auto-embedding: failed to parse event {event_id}: {e}")
                    parse_failures += 1

            if not events:
                logger.info(
                    f"Auto-embedding: no valid events to embed (parse failures: {parse_failures})"
                )
                return

            # 初始化 VectorStore 并批量写入
            vector_store = VectorStore()
            try:
                vector_store.add_batch(events)
                success_count = len(events)
                logger.info(f"Auto-embedded {success_count} events")
                self.console.print(f"[green]Auto-embedded {success_count} events[/]")
            except Exception as e:
                # 降级：逐条 add
                logger.warning(f"add_batch failed, falling back to single add: {e}")
                success_count = 0
                failure_count = 0
                for event in events:
                    try:
                        vector_store.add(event)
                        success_count += 1
                    except Exception:
                        failure_count += 1
                msg = f"Auto-embedded {success_count} events"
                if failure_count > 0:
                    msg += f" ({failure_count} failures)"
                logger.info(msg)
                self.console.print(f"[yellow]{msg}[/]")
            finally:
                # 防护风险 2：释放模型
                vector_store.release_model()

        except sqlite3.OperationalError as e:
            logger.info(f"Auto-embedding skipped: {e}")
        except Exception as e:
            logger.warning(f"Auto-embedding failed: {e}")
        finally:
            if conn:
                conn.close()
