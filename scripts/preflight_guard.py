#!/usr/bin/env python3
"""Preflight guard for branch naming and protected design doc writes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pr_ready  # noqa: E402


DEFAULT_WORK_CLASS_PREFIXES = {
    "product": ["codex/task-"],
    "ops": ["codex/ops-"],
    "rescue": ["codex/rescue-"],
    "rfc": ["codex/rfc-", "codex/rfc/", "rfc/"],
}


def load_branch_class_prefixes() -> dict[str, list[str]]:
    permissions_path = REPO_ROOT / ".agent" / "permissions.yaml"
    if not permissions_path.exists():
        return {key: list(value) for key, value in DEFAULT_WORK_CLASS_PREFIXES.items()}

    try:
        payload = yaml.safe_load(permissions_path.read_text(encoding="utf-8")) or {}
    except Exception:
        payload = {}
    section = payload.get("branch_classes", {})
    if not isinstance(section, dict):
        section = {}

    resolved: dict[str, list[str]] = {}
    for work_class, default_prefixes in DEFAULT_WORK_CLASS_PREFIXES.items():
        config = section.get(work_class, {})
        if not isinstance(config, dict):
            config = {}
        prefixes = config.get("allowed_prefixes")
        if not isinstance(prefixes, list):
            prefixes = list(default_prefixes)
        resolved[work_class] = [
            pr_ready._normalize_path(str(prefix)) for prefix in prefixes if str(prefix).strip()
        ]
    return resolved


def branch_matches_work_class(
    branch: str, work_class: str, branch_class_prefixes: dict[str, list[str]]
) -> bool:
    return any(branch.startswith(prefix) for prefix in branch_class_prefixes[work_class])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preflight guard before editing files.")
    parser.add_argument(
        "--work-class",
        required=True,
        choices=sorted(DEFAULT_WORK_CLASS_PREFIXES),
        help="Task class used to validate branch naming.",
    )
    parser.add_argument("--task-packet", type=Path, help="Optional task packet markdown path.")
    parser.add_argument(
        "--intent-file",
        action="append",
        default=[],
        help="Planned target file; repeat for multiple files when no task packet exists.",
    )
    parser.add_argument("--branch", help="Branch name override; defaults to current branch.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    branch_class_prefixes = load_branch_class_prefixes()

    packet = pr_ready.TaskPacket(
        task_id=None,
        allowed_files=[],
        protected_doc_override=False,
        user_approval_note=None,
        design_change_reason=None,
    )
    if args.task_packet:
        packet = pr_ready.parse_task_packet(args.task_packet)

    intent_files = [pr_ready._normalize_path(path) for path in args.intent_file if path.strip()]
    if packet.allowed_files:
        intent_files = packet.allowed_files
    if not intent_files:
        parser.error("preflight requires --task-packet with allowed files or repeated --intent-file")

    branch = args.branch or pr_ready.get_current_branch()
    if not branch_matches_work_class(branch, args.work_class, branch_class_prefixes):
        print(
            "[PREFLIGHT_ERROR] branch class mismatch: "
            f"branch '{branch}' is not valid for work class '{args.work_class}'",
            file=sys.stderr,
        )
        return 1

    protected_policy = pr_ready.load_protected_doc_policy()
    override_status, override_reason = pr_ready.validate_protected_doc_override_context(
        branch=branch,
        packet_override=packet.protected_doc_override,
        approval_note=packet.user_approval_note,
        design_change_reason=packet.design_change_reason,
        policy=protected_policy,
    )
    if override_status != "pass":
        print(
            "[PREFLIGHT_ERROR] protected design doc override gate failed: "
            f"{override_reason or 'unknown reason'}",
            file=sys.stderr,
        )
        return 1
    protected_status, protected_files, protected_reason = pr_ready.evaluate_protected_docs(
        changed_files=intent_files,
        branch=branch,
        packet_override=packet.protected_doc_override,
        approval_note=packet.user_approval_note,
        design_change_reason=packet.design_change_reason,
        policy=protected_policy,
    )
    if protected_status != "pass":
        print(
            "[PREFLIGHT_ERROR] protected design doc gate failed: "
            f"{protected_reason or 'unknown reason'}",
            file=sys.stderr,
        )
        for path in protected_files:
            print(f"  - {path}", file=sys.stderr)
        return 1

    print("[PREFLIGHT_OK]")
    print(f"branch: {branch}")
    print(f"work_class: {args.work_class}")
    if packet.task_id:
        print(f"task: {packet.task_id}")
    print("intent_files:")
    for path in intent_files:
        print(f"- {path}")
    print("protected_docs: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
