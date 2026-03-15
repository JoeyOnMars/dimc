from datetime import datetime
from pathlib import Path

from dimcause.core.models import Event, EventType, SourceType
from dimcause.scheduler.orchestrator import Orchestrator


def test_persist_task_evidence_on_start_writes_task_event_markdown(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "STATUS.md").write_text(
        "\n".join(
            [
                "# Status",
                "",
                "## 3. V6.1 进度 (审计修复与 Production Polish)",
                "",
                "| 任务 | 内容 | 状态 |",
                "|:---|:---|:---|",
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
        encoding="utf-8",
    )
    task_packet = tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md"
    task_packet.parent.mkdir(parents=True, exist_ok=True)
    task_packet.write_text("# Task Packet\n\n## Goal\n- test\n", encoding="utf-8")
    context_file = tmp_path / "tmp" / "context" / "L0_调度_context.md"
    context_file.parent.mkdir(parents=True, exist_ok=True)
    context_file.write_text("context", encoding="utf-8")

    orch = Orchestrator(project_root=tmp_path)
    recorded = {}

    def fake_sync(event, markdown_path):
        recorded["event"] = event
        recorded["markdown_path"] = markdown_path
        return True

    monkeypatch.setattr(orch, "_sync_task_event_to_knowledge", fake_sync)

    job_dir = orch.persist_task_evidence_on_start(
        task_id="L0 调度",
        job_id="l0-调度-auto",
        context_file=context_file,
        task_packet_file=task_packet,
        branch="codex/task-067",
        worktree=str(tmp_path),
    )

    durable_packet = job_dir / "task-packet.md"
    content = durable_packet.read_text(encoding="utf-8")
    assert "type: task" in content
    assert "artifact_type: task_start" in content
    assert "Task Packet: L0 调度 - Orchestrator 核心调度器" in content
    assert recorded["event"].id == orch._task_event_id("l0-调度-auto", "start")
    assert recorded["markdown_path"] == durable_packet


def test_sync_task_event_to_knowledge_calls_index_and_vector(monkeypatch, tmp_path):
    orch = Orchestrator(project_root=tmp_path)
    monkeypatch.setattr(orch, "_scheduler_data_dir", lambda: tmp_path / ".dimcause")

    recorded = {}

    class FakeEventIndex:
        def __init__(self, db_path):
            recorded["db_path"] = db_path

        def add(self, event, markdown_path):
            recorded["indexed_event_id"] = event.id
            recorded["indexed_path"] = markdown_path
            return True

    class FakeVectorStore:
        def __init__(self, persist_dir, db_path):
            recorded["vector_persist_dir"] = persist_dir
            recorded["vector_db_path"] = db_path

        def add(self, event):
            recorded["vector_event_id"] = event.id

        def release_model(self):
            recorded["released"] = True

    monkeypatch.setattr("dimcause.core.event_index.EventIndex", FakeEventIndex)
    monkeypatch.setattr("dimcause.storage.vector_store.VectorStore", FakeVectorStore)

    event = Event(
        id="scheduler-task-start-demo",
        type=EventType.TASK,
        timestamp=datetime.now(),
        summary="Task Packet: demo",
        content="demo content",
        source=SourceType.MANUAL,
    )
    markdown_path = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "demo" / "task-packet.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(event.to_markdown(), encoding="utf-8")

    assert orch._sync_task_event_to_knowledge(event, markdown_path) is True
    assert recorded["indexed_event_id"] == event.id
    assert recorded["indexed_path"] == str(markdown_path)
    assert recorded["vector_event_id"] == event.id
    assert recorded["released"] is True


def test_link_task_lifecycle_events_upserts_leads_to_link(monkeypatch, tmp_path):
    orch = Orchestrator(project_root=tmp_path)
    monkeypatch.setattr(orch, "_scheduler_data_dir", lambda: tmp_path / ".dimcause")

    recorded = {}

    class FakeEventIndex:
        def __init__(self, db_path):
            recorded["db_path"] = db_path

        def upsert_links(self, event_id, links):
            recorded["event_id"] = event_id
            recorded["links"] = links
            return True

    monkeypatch.setattr("dimcause.core.event_index.EventIndex", FakeEventIndex)

    orch._link_task_lifecycle_events(
        source_event_id="scheduler-task-start-demo",
        target_event_id="scheduler-task-result-demo",
        outcome="done",
    )

    assert recorded["event_id"] == "scheduler-task-start-demo"
    assert len(recorded["links"]) == 1
    link = recorded["links"][0]
    assert link.source == "scheduler-task-start-demo"
    assert link.target == "scheduler-task-result-demo"
    assert link.relation == "leads_to"
    assert link.metadata["outcome"] == "done"
