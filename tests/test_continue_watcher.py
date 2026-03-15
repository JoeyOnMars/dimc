import json

from dimcause.core.models import SourceType
from dimcause.watchers.continue_watcher import ContinueWatcher


def test_continue_watcher_parses_messages_array(tmp_path):
    watch_dir = tmp_path / "sessions"
    watch_dir.mkdir()
    watcher = ContinueWatcher(watch_path=str(watch_dir))

    content = json.dumps(
        {
            "messages": [
                {"role": "user", "content": "Look at src/app.py"},
                {"role": "assistant", "content": "I updated docs/README.md"},
            ]
        }
    )

    raw = watcher._parse_content(content)

    assert raw is not None
    assert raw.source == SourceType.CONTINUE_DEV
    assert raw.metadata["message_count"] == 2
    assert "src/app.py" in raw.files_mentioned
    assert "docs/README.md" in raw.files_mentioned


def test_continue_watcher_parses_jsonl_fallback(tmp_path):
    watch_dir = tmp_path / "sessions"
    watch_dir.mkdir()
    watcher = ContinueWatcher(watch_path=str(watch_dir))

    content = "\n".join(
        [
            json.dumps({"role": "user", "content": "Trace src/main.py"}),
            json.dumps({"role": "assistant", "content": "Opened tests/test_main.py"}),
        ]
    )

    raw = watcher._parse_content(content)

    assert raw is not None
    assert raw.source == SourceType.CONTINUE_DEV
    assert raw.metadata["message_count"] == 2
    assert "src/main.py" in raw.files_mentioned
    assert "tests/test_main.py" in raw.files_mentioned
