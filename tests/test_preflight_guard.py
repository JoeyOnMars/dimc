import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "preflight_guard.py"
SPEC = importlib.util.spec_from_file_location("preflight_guard_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_branch_matches_work_class_accepts_expected_prefix():
    prefixes = MODULE.DEFAULT_WORK_CLASS_PREFIXES
    assert MODULE.branch_matches_work_class("codex/ops-preflight", "ops", prefixes) is True
    assert (
        MODULE.branch_matches_work_class("codex/rfc-protected-doc-update", "rfc", prefixes) is True
    )


def test_branch_matches_work_class_rejects_wrong_prefix():
    prefixes = MODULE.DEFAULT_WORK_CLASS_PREFIXES
    assert MODULE.branch_matches_work_class("codex/task-123", "ops", prefixes) is False
    assert MODULE.branch_matches_work_class("codex/ops-preflight", "product", prefixes) is False


def test_load_branch_class_prefixes_reads_permissions_template(tmp_path, monkeypatch):
    permissions_dir = tmp_path / ".agent"
    permissions_dir.mkdir()
    (permissions_dir / "permissions.yaml").write_text(
        "\n".join(
            [
                "branch_classes:",
                "  ops:",
                "    allowed_prefixes:",
                "      - codex/ops-",
                "      - ops/",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "REPO_ROOT", tmp_path)

    prefixes = MODULE.load_branch_class_prefixes()

    assert prefixes["ops"] == ["codex/ops-", "ops/"]
    assert prefixes["product"] == ["codex/task-"]


def test_main_rejects_protected_docs_without_override(capsys):
    policy = MODULE.pr_ready.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )
    argv = [
        "preflight_guard.py",
        "--work-class",
        "ops",
        "--branch",
        "codex/ops-guard-test",
        "--intent-file",
        "docs/PROJECT_ARCHITECTURE.md",
    ]

    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                MODULE, "load_branch_class_prefixes", lambda: MODULE.DEFAULT_WORK_CLASS_PREFIXES
            )
            monkeypatch.setattr(MODULE.pr_ready, "load_protected_doc_policy", lambda: policy)
            exit_code = MODULE.main()
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "protected design doc gate failed" in captured.err


def test_main_accepts_rfc_branch_with_override_task_packet(tmp_path, capsys):
    packet = tmp_path / "task_packet.md"
    packet.write_text(
        "\n".join(
            [
                "# Task Packet",
                "- `task_id`: rfc-protected-doc-update",
                "- `risk_level`: high",
                "- `protected_doc_override`: true",
                "- `user_approval_note`: User approved this RFC in the current turn.",
                "- `design_change_reason`: Need to update the target architecture contract.",
                "",
                "## 4. Allowed Files",
                "```text",
                "- docs/PROJECT_ARCHITECTURE.md",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    policy = MODULE.pr_ready.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )
    argv = [
        "preflight_guard.py",
        "--work-class",
        "rfc",
        "--branch",
        "codex/rfc-protected-doc-update",
        "--task-packet",
        str(packet),
    ]

    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                MODULE, "load_branch_class_prefixes", lambda: MODULE.DEFAULT_WORK_CLASS_PREFIXES
            )
            monkeypatch.setattr(MODULE.pr_ready, "load_protected_doc_policy", lambda: policy)
            exit_code = MODULE.main()
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[PREFLIGHT_OK]" in captured.out
    assert "protected_docs: pass" in captured.out


def test_main_rejects_rfc_packet_missing_approval_note(tmp_path, capsys):
    packet = tmp_path / "task_packet.md"
    packet.write_text(
        "\n".join(
            [
                "# Task Packet",
                "- `task_id`: rfc-protected-doc-update",
                "- `risk_level`: high",
                "- `protected_doc_override`: true",
                "- `user_approval_note`: ",
                "- `design_change_reason`: Need to update the target architecture contract.",
                "",
                "## 4. Allowed Files",
                "```text",
                "- docs/PROJECT_ARCHITECTURE.md",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    policy = MODULE.pr_ready.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )
    argv = [
        "preflight_guard.py",
        "--work-class",
        "rfc",
        "--branch",
        "codex/rfc-protected-doc-update",
        "--task-packet",
        str(packet),
    ]

    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                MODULE, "load_branch_class_prefixes", lambda: MODULE.DEFAULT_WORK_CLASS_PREFIXES
            )
            monkeypatch.setattr(MODULE.pr_ready, "load_protected_doc_policy", lambda: policy)
            exit_code = MODULE.main()
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "require a non-empty user_approval_note" in captured.err


def test_main_rejects_override_on_non_rfc_branch_even_without_protected_file(tmp_path, capsys):
    packet = tmp_path / "task_packet.md"
    packet.write_text(
        "\n".join(
            [
                "# Task Packet",
                "- `task_id`: ops-guard-hardening",
                "- `risk_level`: medium",
                "- `protected_doc_override`: true",
                "- `user_approval_note`: User approved this RFC in the current turn.",
                "- `design_change_reason`: Need to update the architecture baseline.",
                "",
                "## 4. Allowed Files",
                "```text",
                "- src/dimcause/cli.py",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    policy = MODULE.pr_ready.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )
    argv = [
        "preflight_guard.py",
        "--work-class",
        "ops",
        "--branch",
        "codex/ops-guard-hardening",
        "--task-packet",
        str(packet),
    ]

    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                MODULE, "load_branch_class_prefixes", lambda: MODULE.DEFAULT_WORK_CLASS_PREFIXES
            )
            monkeypatch.setattr(MODULE.pr_ready, "load_protected_doc_policy", lambda: policy)
            exit_code = MODULE.main()
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "protected_doc_override is only valid on RFC branches" in captured.err
