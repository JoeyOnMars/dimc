#!/usr/bin/env python3
"""Build a minimal PR_READY report with check output and whitelist validation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPO_ROOT / "tmp" / "check-report.json"
DEFAULT_PROTECTED_DOC_FILES = [
    "docs/PROJECT_ARCHITECTURE.md",
    "docs/STORAGE_ARCHITECTURE.md",
    "docs/V6.0/DEV_ONTOLOGY.md",
]
DEFAULT_PROTECTED_DOC_BRANCH_PREFIXES = [
    "codex/rfc-",
    "codex/rfc/",
    "rfc/",
]


@dataclass
class TaskPacket:
    task_id: str | None
    allowed_files: list[str]
    protected_doc_override: bool
    user_approval_note: str | None
    design_change_reason: str | None


@dataclass
class ProtectedDocPolicy:
    files: list[str]
    allowed_branch_prefixes: list[str]
    require_explicit_user_authorization: bool
    default_override: bool
    approval_note_field: str
    design_change_reason_field: str


def _normalize_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip()


def _extract_markdown_field(text: str, field_name: str) -> str | None:
    pattern = rf"^-?[ \t]*`{re.escape(field_name)}`:[ \t]*(.*)$"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    candidate = match.group(1).strip().strip("`")
    return candidate or None


def parse_task_packet(path: Path) -> TaskPacket:
    text = path.read_text(encoding="utf-8")
    task_id: str | None = None
    allowed_files: list[str] = []
    protected_doc_override = False
    user_approval_note: str | None = None
    design_change_reason: str | None = None

    task_id = _extract_markdown_field(text, "task_id")

    protected_candidate = _extract_markdown_field(text, "protected_doc_override")
    if protected_candidate is not None:
        candidate = protected_candidate.lower()
        protected_doc_override = candidate in {"true", "yes", "1"}
    user_approval_note = _extract_markdown_field(text, "user_approval_note")
    design_change_reason = _extract_markdown_field(text, "design_change_reason")

    lines = text.splitlines()
    in_allowed_section = False
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_allowed_section and stripped != "## 4. Allowed Files":
                break
            in_allowed_section = stripped == "## 4. Allowed Files"
            in_fence = False
            continue
        if not in_allowed_section:
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and stripped.startswith("- "):
            entry = _normalize_path(stripped[2:])
            if entry:
                allowed_files.append(entry)

    return TaskPacket(
        task_id=task_id,
        allowed_files=allowed_files,
        protected_doc_override=protected_doc_override,
        user_approval_note=user_approval_note,
        design_change_reason=design_change_reason,
    )


def load_protected_doc_policy() -> ProtectedDocPolicy:
    permissions_path = REPO_ROOT / ".agent" / "permissions.yaml"
    if not permissions_path.exists():
        return ProtectedDocPolicy(
            files=list(DEFAULT_PROTECTED_DOC_FILES),
            allowed_branch_prefixes=list(DEFAULT_PROTECTED_DOC_BRANCH_PREFIXES),
            require_explicit_user_authorization=True,
            default_override=False,
            approval_note_field="user_approval_note",
            design_change_reason_field="design_change_reason",
        )

    try:
        payload = yaml.safe_load(permissions_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {}
    section = payload.get("protected_design_docs", {})
    if not isinstance(section, dict):
        section = {}

    files = section.get("files")
    if not isinstance(files, list):
        files = list(DEFAULT_PROTECTED_DOC_FILES)
    prefixes = section.get("allowed_branch_prefixes")
    if not isinstance(prefixes, list):
        prefixes = list(DEFAULT_PROTECTED_DOC_BRANCH_PREFIXES)

    return ProtectedDocPolicy(
        files=[_normalize_path(str(item)) for item in files if str(item).strip()],
        allowed_branch_prefixes=[
            _normalize_path(str(item)) for item in prefixes if str(item).strip()
        ],
        require_explicit_user_authorization=bool(
            section.get("require_explicit_user_authorization", True)
        ),
        default_override=bool(section.get("default_override", False)),
        approval_note_field=str(section.get("approval_note_field", "user_approval_note")),
        design_change_reason_field=str(
            section.get("design_change_reason_field", "design_change_reason")
        ),
    )


def _has_meaningful_text(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().strip("`").strip()
    if not normalized:
        return False
    return normalized.lower() not in {
        "tbd",
        "todo",
        "n/a",
        "na",
        "none",
        "<required>",
        "<fill-me>",
        "<approval>",
        "<reason>",
    }


def file_is_allowed(changed_file: str, allowed_entries: Iterable[str]) -> bool:
    normalized_file = _normalize_path(changed_file)
    for entry in allowed_entries:
        normalized_entry = _normalize_path(entry)
        if not normalized_entry:
            continue
        if normalized_entry.endswith("/"):
            if normalized_file.startswith(normalized_entry):
                return True
            continue
        if normalized_file == normalized_entry:
            return True
        if normalized_file.startswith(normalized_entry + "/"):
            return True
    return False


def evaluate_whitelist(changed_files: Iterable[str], allowed_entries: Iterable[str]) -> tuple[str, list[str]]:
    allowed_list = [entry for entry in allowed_entries if _normalize_path(entry)]
    violations = [path for path in changed_files if not file_is_allowed(path, allowed_list)]
    status = "pass" if not violations else "fail"
    return status, violations


def branch_is_allowed_for_protected_docs(
    branch: str, allowed_prefixes: Iterable[str]
) -> bool:
    return any(branch.startswith(prefix) for prefix in allowed_prefixes if prefix)


def validate_protected_doc_override_context(
    *,
    branch: str,
    packet_override: bool,
    approval_note: str | None,
    design_change_reason: str | None,
    policy: ProtectedDocPolicy,
) -> tuple[str, str | None]:
    override_enabled = packet_override or policy.default_override
    if not override_enabled:
        return "pass", None

    if not branch_is_allowed_for_protected_docs(branch, policy.allowed_branch_prefixes):
        return "fail", "protected_doc_override is only valid on RFC branches"

    if policy.require_explicit_user_authorization and not _has_meaningful_text(approval_note):
        return "fail", f"protected design docs require a non-empty {policy.approval_note_field}"

    if not _has_meaningful_text(design_change_reason):
        return "fail", f"protected design docs require a non-empty {policy.design_change_reason_field}"

    return "pass", None


def evaluate_protected_docs(
    *,
    changed_files: Iterable[str],
    branch: str,
    packet_override: bool,
    approval_note: str | None,
    design_change_reason: str | None,
    policy: ProtectedDocPolicy,
) -> tuple[str, list[str], str | None]:
    protected_files = {_normalize_path(path) for path in policy.files}
    touched = [path for path in changed_files if _normalize_path(path) in protected_files]
    if not touched:
        return "pass", [], None

    if not (packet_override or policy.default_override):
        return (
            "fail",
            touched,
            "protected design docs touched without task packet override",
        )

    override_status, override_reason = validate_protected_doc_override_context(
        branch=branch,
        packet_override=packet_override,
        approval_note=approval_note,
        design_change_reason=design_change_reason,
        policy=policy,
    )
    if override_status != "pass":
        return "fail", touched, override_reason

    return "pass", touched, None


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def get_current_branch() -> str:
    result = run_command(["git", "branch", "--show-current"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to resolve current branch")
    return result.stdout.strip()


def get_changed_files(base_ref: str) -> list[str]:
    result = run_command(["git", "diff", "--name-only", f"{base_ref}...HEAD"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to collect changed files")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def ensure_clean_worktree() -> None:
    result = run_command(["git", "status", "--short"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to inspect worktree status")
    if result.stdout.strip():
        raise RuntimeError("working tree is not clean; commit or stash changes before PR_READY")


def load_check_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_check(report_path: Path) -> dict:
    command = ["zsh", str(REPO_ROOT / "scripts" / "check.zsh"), "--report-file", str(report_path)]
    result = run_command(command)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError("scripts/check.zsh failed")
    return load_check_report(report_path)


def render_pr_ready(
    branch: str,
    task_id: str,
    report: dict,
    changed_files: list[str],
    whitelist_status: str,
    protected_docs_status: str,
    risks: list[str],
    violations: list[str],
    protected_doc_files: list[str],
    protected_doc_reason: str | None,
) -> str:
    lines = [
        "[PR_READY]",
        f"branch: {branch}",
        f"task: {task_id}",
        "checks:",
    ]
    for step in report.get("steps", []):
        command = step.get("command", "unknown")
        status = step.get("status", "unknown")
        lines.append(f"- {command} [{status}]")
    lines.append("files:")
    if changed_files:
        lines.extend(f"- {path}" for path in changed_files)
    else:
        lines.append("- <none>")
    lines.append(f"whitelist: {whitelist_status}")
    if violations:
        lines.append("whitelist_violations:")
        lines.extend(f"- {path}" for path in violations)
    lines.append(f"protected_docs: {protected_docs_status}")
    if protected_doc_files:
        lines.append("protected_doc_files:")
        lines.extend(f"- {path}" for path in protected_doc_files)
    if protected_doc_reason:
        lines.append(f"protected_doc_reason: {protected_doc_reason}")
    lines.append("risks:")
    if risks:
        lines.extend(f"- {risk}" for risk in risks)
    else:
        lines.append("- none")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a minimal PR_READY report.")
    parser.add_argument("--task-id", help="Task identifier used in the PR_READY block.")
    parser.add_argument("--task-packet", type=Path, help="Path to a task packet markdown file.")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Allowed file or directory prefix; repeat for multiple entries.",
    )
    parser.add_argument("--risk", action="append", default=[], help="Residual risk to include.")
    parser.add_argument("--base-ref", default="main", help="Base ref used to compute changed files.")
    parser.add_argument(
        "--report-file",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path for the machine-readable check report.",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Reuse an existing check report instead of running scripts/check.zsh.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Skip the clean worktree guard. Intended only for diagnostics.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    packet = TaskPacket(
        task_id=None,
        allowed_files=[],
        protected_doc_override=False,
        user_approval_note=None,
        design_change_reason=None,
    )
    if args.task_packet:
        packet = parse_task_packet(args.task_packet)

    task_id = args.task_id or packet.task_id
    if not task_id:
        parser.error("task_id is required via --task-id or a populated task packet")

    allowed_entries = packet.allowed_files + list(args.allow)
    if not allowed_entries:
        parser.error("whitelist is required via --task-packet or repeated --allow")

    try:
        branch = get_current_branch()
        if not args.allow_dirty:
            ensure_clean_worktree()
        report = load_check_report(args.report_file) if args.skip_check else run_check(args.report_file)
        if report.get("status") != "pass":
            raise RuntimeError("check report status is not pass")
        changed_files = get_changed_files(args.base_ref)
        whitelist_status, violations = evaluate_whitelist(changed_files, allowed_entries)
        protected_policy = load_protected_doc_policy()
        override_status, override_reason = validate_protected_doc_override_context(
            branch=branch,
            packet_override=packet.protected_doc_override,
            approval_note=packet.user_approval_note,
            design_change_reason=packet.design_change_reason,
            policy=protected_policy,
        )
        if override_status != "pass":
            raise RuntimeError(override_reason or "invalid protected_doc_override configuration")
        protected_docs_status, protected_doc_files, protected_doc_reason = evaluate_protected_docs(
            changed_files=changed_files,
            branch=branch,
            packet_override=packet.protected_doc_override,
            approval_note=packet.user_approval_note,
            design_change_reason=packet.design_change_reason,
            policy=protected_policy,
        )
    except RuntimeError as exc:
        print(f"[PR_READY_ERROR] {exc}", file=sys.stderr)
        return 1

    print(
        render_pr_ready(
            branch=branch,
            task_id=task_id,
            report=report,
            changed_files=changed_files,
            whitelist_status=whitelist_status,
            protected_docs_status=protected_docs_status,
            risks=args.risk,
            violations=violations,
            protected_doc_files=protected_doc_files,
            protected_doc_reason=protected_doc_reason,
        )
    )
    return 0 if whitelist_status == "pass" and protected_docs_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
