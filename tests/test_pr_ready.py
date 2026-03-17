import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pr_ready.py"
SPEC = importlib.util.spec_from_file_location("pr_ready_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_parse_task_packet_extracts_task_id_and_allowed_files(tmp_path):
    packet = tmp_path / "task_packet.md"
    packet.write_text(
        "\n".join(
            [
                "# Task Packet",
                "- `task_id`: task-031",
                "- `risk_level`: low",
                "- `protected_doc_override`: false",
                "",
                "## 4. Allowed Files",
                "```text",
                "- src/dimcause/search/",
                "- tests/test_pr_ready.py",
                "```",
            ]
        ),
        encoding="utf-8",
    )

    parsed = MODULE.parse_task_packet(packet)

    assert parsed.task_id == "task-031"
    assert parsed.allowed_files == ["src/dimcause/search/", "tests/test_pr_ready.py"]
    assert parsed.risk_level == "low"
    assert parsed.protected_doc_override is False
    assert parsed.user_approval_note is None
    assert parsed.design_change_reason is None


def test_parse_task_packet_extracts_protected_doc_metadata(tmp_path):
    packet = tmp_path / "task_packet.md"
    packet.write_text(
        "\n".join(
            [
                "# Task Packet",
                "- `task_id`: task-rfc-001",
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

    parsed = MODULE.parse_task_packet(packet)

    assert parsed.risk_level == "high"
    assert parsed.protected_doc_override is True
    assert parsed.user_approval_note == "User approved this RFC in the current turn."
    assert parsed.design_change_reason == "Need to update the target architecture contract."


def test_evaluate_whitelist_accepts_exact_and_directory_prefix_entries():
    changed_files = [
        "src/dimcause/search/engine.py",
        "tests/test_pr_ready.py",
    ]

    status, violations = MODULE.evaluate_whitelist(
        changed_files,
        ["src/dimcause/search/", "tests/test_pr_ready.py"],
    )

    assert status == "pass"
    assert violations == []


def test_evaluate_whitelist_flags_out_of_scope_files():
    changed_files = [
        "src/dimcause/search/engine.py",
        "docs/STATUS.md",
    ]

    status, violations = MODULE.evaluate_whitelist(
        changed_files,
        ["src/dimcause/search/"],
    )

    assert status == "fail"
    assert violations == ["docs/STATUS.md"]


def test_evaluate_protected_docs_rejects_override_missing():
    policy = MODULE.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )

    status, touched, reason = MODULE.evaluate_protected_docs(
        changed_files=["docs/PROJECT_ARCHITECTURE.md"],
        branch="codex/ops-protected-design-doc-gates",
        packet_override=False,
        approval_note=None,
        design_change_reason=None,
        policy=policy,
    )

    assert status == "fail"
    assert touched == ["docs/PROJECT_ARCHITECTURE.md"]
    assert reason == "protected design docs touched without task packet override"


def test_evaluate_protected_docs_rejects_non_rfc_branch():
    policy = MODULE.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )

    status, touched, reason = MODULE.evaluate_protected_docs(
        changed_files=["docs/PROJECT_ARCHITECTURE.md"],
        branch="codex/ops-protected-design-doc-gates",
        packet_override=True,
        approval_note="User approved this RFC in the current turn.",
        design_change_reason="Need to update the architecture baseline.",
        policy=policy,
    )

    assert status == "fail"
    assert touched == ["docs/PROJECT_ARCHITECTURE.md"]
    assert reason == "protected_doc_override is only valid on RFC branches"


def test_evaluate_protected_docs_rejects_missing_approval_note():
    policy = MODULE.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )

    status, touched, reason = MODULE.evaluate_protected_docs(
        changed_files=["docs/PROJECT_ARCHITECTURE.md"],
        branch="codex/rfc-protected-doc-update",
        packet_override=True,
        approval_note="",
        design_change_reason="Need to update the architecture baseline.",
        policy=policy,
    )

    assert status == "fail"
    assert touched == ["docs/PROJECT_ARCHITECTURE.md"]
    assert reason == "protected design docs require a non-empty user_approval_note"


def test_evaluate_protected_docs_rejects_missing_design_change_reason():
    policy = MODULE.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )

    status, touched, reason = MODULE.evaluate_protected_docs(
        changed_files=["docs/PROJECT_ARCHITECTURE.md"],
        branch="codex/rfc-protected-doc-update",
        packet_override=True,
        approval_note="User approved this RFC in the current turn.",
        design_change_reason="",
        policy=policy,
    )

    assert status == "fail"
    assert touched == ["docs/PROJECT_ARCHITECTURE.md"]
    assert reason == "protected design docs require a non-empty design_change_reason"


def test_validate_protected_doc_override_context_rejects_non_rfc_branch_even_without_touch():
    policy = MODULE.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )

    status, reason = MODULE.validate_protected_doc_override_context(
        branch="codex/ops-guard-hardening",
        packet_override=True,
        approval_note="User approved this RFC in the current turn.",
        design_change_reason="Need to update the architecture baseline.",
        policy=policy,
    )

    assert status == "fail"
    assert reason == "protected_doc_override is only valid on RFC branches"


def test_evaluate_protected_docs_accepts_rfc_branch_with_override_and_metadata():
    policy = MODULE.ProtectedDocPolicy(
        files=["docs/PROJECT_ARCHITECTURE.md"],
        allowed_branch_prefixes=["codex/rfc-"],
        require_explicit_user_authorization=True,
        default_override=False,
        approval_note_field="user_approval_note",
        design_change_reason_field="design_change_reason",
    )

    status, touched, reason = MODULE.evaluate_protected_docs(
        changed_files=["docs/PROJECT_ARCHITECTURE.md"],
        branch="codex/rfc-protected-doc-update",
        packet_override=True,
        approval_note="User approved this RFC in the current turn.",
        design_change_reason="Need to update the architecture baseline.",
        policy=policy,
    )

    assert status == "pass"
    assert touched == ["docs/PROJECT_ARCHITECTURE.md"]
    assert reason is None
