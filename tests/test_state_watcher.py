from datetime import datetime

from dimcause.core.models import SourceType
from dimcause.watchers.state_watcher import CodeStateDriver, StateWatcher


def test_code_state_driver_emits_change_on_new_head(monkeypatch):
    driver = CodeStateDriver(".")
    monkeypatch.setattr(driver.repo, "get_head_commit", lambda: "new-head")
    monkeypatch.setattr(
        driver.repo,
        "get_commit_info",
        lambda _commit: {"author": "tester", "message": "Add feature"},
    )
    monkeypatch.setattr(
        driver.repo, "get_changed_files", lambda _old, _new: ["src/dimcause/cli.py"]
    )
    monkeypatch.setattr(
        driver.repo,
        "get_diff_range",
        lambda _old, _new: "diff --git a/src/dimcause/cli.py b/src/dimcause/cli.py\n+print('x')\n",
    )
    driver.last_head = "old-head"

    changes = driver.check()

    assert len(changes) == 1
    assert changes[0]["type"] == "code_state_change"
    assert changes[0]["details"]["commit"] == "new-head"
    assert changes[0]["details"]["previous_commit"] == "old-head"
    assert changes[0]["details"]["files_changed"] == ["src/dimcause/cli.py"]
    assert "print('x')" in changes[0]["details"]["diff_excerpt"]
    assert changes[0]["summary"] == "Add feature"


def test_code_state_driver_emits_change_on_working_tree_diff(monkeypatch):
    driver = CodeStateDriver(".")
    monkeypatch.setattr(driver.repo, "get_head_commit", lambda: driver.last_head)
    monkeypatch.setattr(
        driver.repo,
        "get_status",
        lambda: [" M src/dimcause/watchers/state_watcher.py", "?? tests/test_state_watcher.py"],
    )
    monkeypatch.setattr(
        driver.repo,
        "get_working_tree_diff",
        lambda: "diff --git a/src/dimcause/watchers/state_watcher.py b/src/dimcause/watchers/state_watcher.py\n+logger.info('changed')\n",
    )
    driver.last_status = ()

    changes = driver.check()

    assert len(changes) == 1
    assert changes[0]["type"] == "working_tree_change"
    assert changes[0]["details"]["files_changed"] == [
        "src/dimcause/watchers/state_watcher.py",
        "tests/test_state_watcher.py",
    ]
    assert "logger.info('changed')" in changes[0]["details"]["diff_excerpt"]


def test_code_state_driver_truncates_large_diff_excerpt():
    driver = CodeStateDriver(".")
    large_diff = "\n".join(f"+line {idx}" for idx in range(200))

    details = driver._truncate_diff_excerpt(large_diff)

    assert details["diff_truncated"] is True
    assert details["diff_excerpt"].endswith("... [truncated]")


def test_state_watcher_converts_change_to_raw_data(tmp_path):
    watcher = StateWatcher(project_path=str(tmp_path), interval_seconds=0.01)
    change = {
        "type": "code_state_change",
        "summary": "Fix scheduler",
        "details": {
            "commit": "abc123",
            "author": "tester",
            "files_changed": ["src/dimcause/scheduler/loop.py"],
            "diff_excerpt": "+loop.run()",
        },
        "timestamp": datetime.now().isoformat(),
    }

    raw = watcher._change_to_raw_data(change)

    assert raw.source == SourceType.FILE
    assert raw.content == "Fix scheduler"
    assert raw.project_path == str(tmp_path)
    assert raw.files_mentioned == ["src/dimcause/scheduler/loop.py"]
    assert raw.metadata["commit"] == "abc123"
    assert raw.metadata["diff_excerpt"] == "+loop.run()"
