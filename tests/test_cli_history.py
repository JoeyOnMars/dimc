from unittest.mock import patch

from typer.testing import CliRunner

from dimcause.cli import app
from dimcause.core.history import GitCommit, get_file_history

runner = CliRunner()


def test_history_command_structure():
    """Test that the history command exists and handles arguments correctly."""
    # This might fail until cli.py is fixed, but defines the contract
    result = runner.invoke(app, ["history", "--help"])
    assert result.exit_code == 0
    assert "history" in result.stdout


@patch("dimcause.core.event_index.EventIndex")
@patch("dimcause.core.history.get_file_history")
def test_history_command_non_interactive_renders_rows(mock_get_file_history, _mock_index):
    """history 命令在当前 live CLI 中应能以非交互模式渲染历史行。"""
    mock_get_file_history.return_value = [
        GitCommit(
            hash="abc1234",
            date="2026-01-01T10:00:00",
            message="init commit",
            author="tester",
            type="git_commit",
        )
    ]

    result = runner.invoke(app, ["history", "src/main.py", "--limit", "1", "--no-interactive"])

    assert result.exit_code == 0
    assert "History for src/main.py" in result.stdout
    assert "init commit" in result.stdout
    assert "tester" in result.stdout


@patch("dimcause.core.history.run_git")
def test_get_file_history_basic(mock_git):
    """Test core history retrieval logic."""
    # Mock git output
    mock_git.return_value = (0, "abc1234|2026-01-01|tester|init commit", "")

    history = get_file_history("src/main.py", limit=5)

    assert len(history) == 1
    assert isinstance(history[0], GitCommit)
    assert history[0].hash == "abc1234"
    assert history[0].message == "init commit"
    mock_git.assert_called_once()


@patch("dimcause.core.history.get_file_history")
def test_why_file_mode_enforces_causal_chain(mock_get_file_history, tmp_path, monkeypatch):
    """why 命令在文件模式下必须启用 use_causal_chain=True。"""
    monkeypatch.setenv("DIMCAUSE_USE_EVENT_INDEX", "false")
    target = tmp_path / "demo.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    mock_get_file_history.return_value = [
        GitCommit(hash="evt_1", date="2026-03-06", message="test", author="tester")
    ]

    result = runner.invoke(app, ["why", str(target), "--max-commits", "1", "--no-explain"])

    assert result.exit_code == 0
    assert mock_get_file_history.called
    assert mock_get_file_history.call_args.kwargs.get("use_causal_chain") is True


@patch("dimcause.core.history.get_file_history")
def test_why_directory_mode_enforces_causal_chain(mock_get_file_history, tmp_path, monkeypatch):
    """why 命令在目录模式下每次 history 查询都必须启用 use_causal_chain=True。"""
    monkeypatch.setenv("DIMCAUSE_USE_EVENT_INDEX", "false")
    target_dir = tmp_path / "pkg"
    target_dir.mkdir(parents=True)
    (target_dir / "a.py").write_text("print('a')\n", encoding="utf-8")
    (target_dir / "b.py").write_text("print('b')\n", encoding="utf-8")

    mock_get_file_history.return_value = [
        GitCommit(hash="evt_1", date="2026-03-06", message="test", author="tester")
    ]

    result = runner.invoke(app, ["why", str(target_dir), "--max-commits", "2", "--no-explain"])

    assert result.exit_code == 0
    assert mock_get_file_history.call_count >= 2
    for call in mock_get_file_history.call_args_list:
        assert call.kwargs.get("use_causal_chain") is True


@patch("dimcause.core.history.get_file_history")
def test_why_renders_causal_evidence_section(mock_get_file_history, tmp_path, monkeypatch):
    monkeypatch.setenv("DIMCAUSE_USE_EVENT_INDEX", "false")
    target = tmp_path / "demo.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    mock_get_file_history.return_value = [
        GitCommit(
            hash="evt_root",
            date="2026-03-06",
            message="root cause decision",
            author="tester",
            type="decision",
            from_causal_chain=True,
        ),
        GitCommit(hash="git_1", date="2026-03-05", message="git commit", author="tester"),
    ]

    result = runner.invoke(app, ["why", str(target), "--max-commits", "2", "--no-explain"])

    assert result.exit_code == 0
    assert "因果链证据" in result.stdout
    assert "root cause decision" in result.stdout
    assert "对象证据区" not in result.stdout


@patch("dimcause.core.history.get_file_history")
def test_why_renders_minimal_object_projection(mock_get_file_history, tmp_path, monkeypatch):
    monkeypatch.setenv("DIMCAUSE_USE_EVENT_INDEX", "false")
    target = tmp_path / "demo.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    mock_get_file_history.return_value = [
        GitCommit(
            hash="evt_projection",
            date="2026-03-06",
            message="projection backed decision",
            author="tester",
            type="decision",
            from_causal_chain=True,
            metadata={
                "object_projection": {
                    "material": {
                        "id": "mat_raw_1",
                        "title": "src/demo.py",
                        "source_ref": "raw:1",
                    },
                    "claims": [
                        {
                            "id": "claim_1",
                            "statement": "该文件引入了最小对象证据显示。",
                        }
                    ],
                }
            },
        )
    ]

    result = runner.invoke(app, ["why", str(target), "--max-commits", "1", "--no-explain"])

    assert result.exit_code == 0
    assert "对象证据区" in result.stdout
    assert "Material: src/demo.py" in result.stdout
    assert "Claim: 该文件引入了最小对象证据显示。" in result.stdout


@patch("dimcause.extractors.llm_client.LiteLLMClient.complete", return_value="解释已生成")
@patch("dimcause.core.history.get_file_history")
def test_why_explain_prompt_includes_object_projection(
    mock_get_file_history, mock_complete, tmp_path, monkeypatch
):
    monkeypatch.setenv("DIMCAUSE_USE_EVENT_INDEX", "false")
    target = tmp_path / "demo.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    mock_get_file_history.return_value = [
        GitCommit(
            hash="evt_projection",
            date="2026-03-06",
            message="projection backed decision",
            author="tester",
            type="decision",
            from_causal_chain=True,
            metadata={
                "object_projection": {
                    "material": {
                        "id": "mat_raw_1",
                        "title": "src/demo.py",
                        "source_ref": "raw:1",
                    },
                    "claims": [
                        {
                            "id": "claim_1",
                            "statement": "该文件引入了最小对象证据显示。",
                        }
                    ],
                }
            },
        )
    ]

    result = runner.invoke(app, ["why", str(target), "--max-commits", "1", "--explain"])

    assert result.exit_code == 0
    assert "解释已生成" in result.stdout

    prompt = mock_complete.call_args.kwargs["prompt"]
    assert "Object Evidence:" in prompt
    assert "Material: src/demo.py" in prompt
    assert "Claim: 该文件引入了最小对象证据显示。" in prompt
