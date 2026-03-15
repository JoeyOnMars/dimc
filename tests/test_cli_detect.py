import json
from typer.testing import CliRunner

from dimcause.cli import app
from dimcause.utils.config import CONFIG_FILENAME

runner = CliRunner()


def test_detect_lists_supported_tool_with_detected_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    (home / ".cursor" / "logs").mkdir(parents=True)
    project.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["detect"])

    assert result.exit_code == 0
    assert "Cursor" in result.stdout
    assert "detected" in result.stdout
    assert "config enable" in result.stdout


def test_config_enable_cursor_writes_project_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    (home / ".cursor" / "logs").mkdir(parents=True)
    project.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["config", "enable", "cursor"])

    assert result.exit_code == 0
    config_file = project / CONFIG_FILENAME
    assert config_file.exists()

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["watcher_cursor"]["enabled"] is True
    assert saved["watcher_cursor"]["path"] == str(home / ".cursor" / "logs")


def test_config_enable_antigravity_updates_export_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    exports = home / "Documents" / "AG_Exports"
    exports.mkdir(parents=True)
    project.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["config", "enable", "antigravity"])

    assert result.exit_code == 0
    saved = json.loads((project / CONFIG_FILENAME).read_text(encoding="utf-8"))
    assert saved["export_dir"] == str(exports)


def test_config_enable_continue_dev_writes_watcher_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    (home / ".continue" / "sessions").mkdir(parents=True)
    project.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["config", "enable", "continue_dev"])

    assert result.exit_code == 0
    saved = json.loads((project / CONFIG_FILENAME).read_text(encoding="utf-8"))
    assert saved["watcher_continue_dev"]["enabled"] is True
    assert saved["watcher_continue_dev"]["path"] == str(home / ".continue" / "sessions")


def test_config_set_writes_nested_llm_model(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["config", "set", "llm_primary.model", "deepseek-chat"])

    assert result.exit_code == 0
    saved = json.loads((project / CONFIG_FILENAME).read_text(encoding="utf-8"))
    assert saved["llm_primary"]["model"] == "deepseek-chat"


def test_config_set_supports_antigravity_alias(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["config", "set", "watchers.antigravity.path", "~/AG_Exports"])

    assert result.exit_code == 0
    saved = json.loads((project / CONFIG_FILENAME).read_text(encoding="utf-8"))
    assert saved["export_dir"] == "~/AG_Exports"
