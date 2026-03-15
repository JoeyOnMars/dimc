"""Tool detection and config bootstrap for watcher integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DetectedTool:
    key: str
    label: str
    path: str
    detected: bool
    supported: bool
    note: str = ""


_TOOL_SPECS = {
    "cursor": {
        "label": "Cursor",
        "supported": True,
        "candidates": [
            "~/.cursor/logs",
            "~/Library/Application Support/Cursor/logs",
            "~/.config/Cursor/logs",
            "%APPDATA%/Cursor/logs",
        ],
    },
    "claude": {
        "label": "Claude Code",
        "supported": True,
        "candidates": [
            "~/.claude/history.jsonl",
        ],
    },
    "windsurf": {
        "label": "Windsurf",
        "supported": True,
        "candidates": [
            "~/.windsurf/logs",
            "~/Library/Application Support/Windsurf/logs",
            "~/.config/Windsurf/logs",
            "%APPDATA%/Windsurf/logs",
            "~/.codeium/windsurf/logs",
        ],
    },
    "antigravity": {
        "label": "Antigravity",
        "supported": True,
        "candidates": [
            os.environ.get("DIMCAUSE_EXPORT_DIR", "~/Documents/AG_Exports"),
        ],
    },
    "continue_dev": {
        "label": "Continue.dev",
        "supported": True,
        "candidates": [
            "~/.continue/sessions",
            "%USERPROFILE%/.continue/sessions",
        ],
    },
    "copilot_chat": {
        "label": "GitHub Copilot Chat",
        "supported": False,
        "candidates": [
            "~/.vscode/copilot_chat",
            "%APPDATA%/Code/User/workspaceStorage",
        ],
        "note": "目录可检测，但当前没有对应 watcher 实现",
    },
}

_ALIASES = {
    "claude_code": "claude",
    "claude-code": "claude",
    "continue": "continue_dev",
    "copilot": "copilot_chat",
}


def detect_tools() -> List[DetectedTool]:
    detections: List[DetectedTool] = []
    for key, spec in _TOOL_SPECS.items():
        detected_path = _detect_first_existing_path(spec["candidates"])
        detections.append(
            DetectedTool(
                key=key,
                label=spec["label"],
                path=detected_path or _expand_path(spec["candidates"][0]),
                detected=detected_path is not None,
                supported=bool(spec["supported"]),
                note=spec.get("note", ""),
            )
        )
    return detections


def normalize_tool_name(name: str) -> str:
    normalized = name.strip().lower().replace(" ", "_")
    return _ALIASES.get(normalized, normalized)


def build_enable_updates(tool_name: str, path: Optional[str] = None) -> Dict:
    tool = normalize_tool_name(tool_name)
    detection = next((item for item in detect_tools() if item.key == tool), None)
    if detection is None:
        raise ValueError(f"Unsupported tool: {tool_name}")
    if not detection.supported:
        raise ValueError(f"Tool is detectable but not yet configurable: {tool_name}")

    selected_path = _expand_path(path) if path else detection.path
    if tool == "cursor":
        return {
            "watcher_cursor": {
                "enabled": True,
                "path": selected_path,
                "debounce_seconds": 1.0,
            }
        }
    if tool == "claude":
        return {
            "watcher_claude": {
                "enabled": True,
                "path": selected_path,
                "debounce_seconds": 1.0,
            }
        }
    if tool == "windsurf":
        return {
            "watcher_windsurf": {
                "enabled": True,
                "path": selected_path,
                "debounce_seconds": 1.0,
            }
        }
    if tool == "continue_dev":
        return {
            "watcher_continue_dev": {
                "enabled": True,
                "path": selected_path,
                "debounce_seconds": 1.0,
            }
        }
    if tool == "antigravity":
        return {"export_dir": selected_path}

    raise ValueError(f"No enable strategy for tool: {tool_name}")


def supported_tool_names() -> List[str]:
    return sorted(key for key, spec in _TOOL_SPECS.items() if spec["supported"])


def _detect_first_existing_path(candidates: List[str]) -> Optional[str]:
    for candidate in candidates:
        expanded = _expand_path(candidate)
        if Path(expanded).exists():
            return expanded
    return None


def _expand_path(path_str: str) -> str:
    return os.path.expanduser(os.path.expandvars(path_str))
