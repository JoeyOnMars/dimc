import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


def _patch_state_env(monkeypatch, root_dir: Path):
    logs_dir = root_dir / "docs" / "logs"
    agent_dir = root_dir / ".agent"
    lock_dir = root_dir / ".locks"
    logs_dir.mkdir(parents=True, exist_ok=True)
    agent_dir.mkdir(parents=True, exist_ok=True)
    lock_dir.mkdir(parents=True, exist_ok=True)

    cfg = SimpleNamespace(lock_dir=lock_dir, lock_timeout=5, lock_retry_base=0.01, lock_max_retries=5, timezone="Asia/Shanghai")
    monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
    monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)
    monkeypatch.setattr("dimcause.utils.state.get_config", lambda: cfg)
    monkeypatch.setattr("dimcause.utils.lock.get_config", lambda: cfg)
    monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
    return logs_dir, agent_dir


def test_record_job_start_writes_active_marker_and_get_active_job(monkeypatch, tmp_path):
    from dimcause.utils.state import get_active_job, record_job_start

    logs_dir, agent_dir = _patch_state_env(monkeypatch, tmp_path)
    today = datetime.now().strftime("%Y/%m-%d")
    job_dir = logs_dir / today / "jobs" / "feature-auth"
    job_dir.mkdir(parents=True)
    (job_dir / "job-start.md").write_text("---\ntype: job-start\n---\n", encoding="utf-8")

    record_job_start("feature-auth")

    marker = agent_dir / "active_job.json"
    assert marker.exists()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["job_id"] == "feature-auth"
    assert payload["job_path"] == str(job_dir)

    active = get_active_job()
    assert active == ("feature-auth", job_dir)


def test_record_job_end_clears_active_marker(monkeypatch, tmp_path):
    from dimcause.utils.state import record_job_end, record_job_start

    logs_dir, agent_dir = _patch_state_env(monkeypatch, tmp_path)
    today = datetime.now().strftime("%Y/%m-%d")
    job_dir = logs_dir / today / "jobs" / "feature-auth"
    job_dir.mkdir(parents=True)
    (job_dir / "job-start.md").write_text("---\ntype: job-start\n---\n", encoding="utf-8")

    record_job_start("feature-auth")
    assert (agent_dir / "active_job.json").exists()

    record_job_end()
    assert not (agent_dir / "active_job.json").exists()


def test_get_active_job_clears_stale_marker(monkeypatch, tmp_path):
    from dimcause.utils.state import get_active_job

    _logs_dir, agent_dir = _patch_state_env(monkeypatch, tmp_path)
    marker = agent_dir / "active_job.json"
    marker.write_text(
        json.dumps({"job_id": "missing", "job_path": str(tmp_path / "missing-job")}),
        encoding="utf-8",
    )

    assert get_active_job() is None
    assert not marker.exists()
