from datetime import datetime
from types import SimpleNamespace

from dimcause.audit.context_injector import ContextInjector
from dimcause.extractors.data_collector import DataCollector, SessionData


def test_data_collector_only_reads_configured_export_dir(tmp_path, monkeypatch):
    export_dir = tmp_path / "external" / "AG_Exports"
    export_dir.mkdir(parents=True)
    external_file = export_dir / "2026-03-17-session-001.md"
    external_file.write_text("外部导出", encoding="utf-8")

    legacy_raw_dir = tmp_path / "docs" / "logs" / "raw" / "AG_Exports"
    legacy_raw_dir.mkdir(parents=True)
    legacy_file = legacy_raw_dir / "2026-03-17-session-legacy.md"
    legacy_file.write_text("仓库内旧导出", encoding="utf-8")

    fixed_ts = datetime(2026, 3, 17, 10, 0, 0).timestamp()
    for path in (external_file, legacy_file):
        path.touch()
        path.chmod(0o644)
        # mtime 对齐到同一天，避免测试因日期过滤失效
        import os

        os.utime(path, (fixed_ts, fixed_ts))

    fake_config = SimpleNamespace(
        export_dir=str(export_dir),
        brain_dir=None,
        root_dir=tmp_path,
        external_sources=[],
        claude_code_sessions_dir=None,
    )
    monkeypatch.setattr("dimcause.extractors.data_collector.get_config", lambda: fake_config)

    collector = DataCollector(session_id="session-001", date_str="2026-03-17")
    data = SessionData(session_id="session-001", date_str="2026-03-17")
    collector._collect_raw_chats(data)

    assert data.raw_chat_files == [external_file]


def test_context_injector_scans_configured_export_dir_only(tmp_path, monkeypatch):
    export_dir = tmp_path / "external" / "AG_Exports"
    export_dir.mkdir(parents=True)
    export_file = export_dir / "2026-03-17-session-abc.md"
    export_file.write_text(
        "### USER Objective:\n补齐 why 的对象证据解释。\n\n## Notes\n后续补测试。",
        encoding="utf-8",
    )

    legacy_raw_dir = tmp_path / "docs" / "logs" / "raw" / "AG_Exports"
    legacy_raw_dir.mkdir(parents=True)
    (legacy_raw_dir / "2026-03-17-session-abc.md").write_text(
        "### USER Objective:\n这份旧目录文件不应再被读取。",
        encoding="utf-8",
    )

    fake_config = SimpleNamespace(export_dir=str(export_dir), brain_dir=None)
    monkeypatch.setattr("dimcause.audit.context_injector.get_config", lambda: fake_config)

    injector = ContextInjector(root_dir=tmp_path)
    objective = injector._scan_ag_exports("session-abc", "2026-03-17")

    assert objective == "补齐 why 的对象证据解释。"
