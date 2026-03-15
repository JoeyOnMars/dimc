from dataclasses import dataclass, field
from typing import Set


@dataclass
class AuditMode:
    """
    Configuration for Audit Execution Mode.
    Controls blocking behavior, file filtering, and severity thresholds.
    """

    name: str
    is_blocking: bool
    exclude_patterns: Set[str] = field(default_factory=set)
    include_patterns: Set[str] = field(default_factory=set)  # If empty, include all not excluded

    # Future extensibility
    min_severity: str = "WARNING"


# Base exclusions for all modes (noise reduction)
# Note: specific checks might add their own logic, but this is the global filter
BASE_EXCLUSIONS = {
    ".git",
    ".DS_Store",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "dimcause.egg-info",
    "htmlcov",
    "coverage.xml",
    "uv.lock",
    "poetry.lock",
    "package-lock.json",
    "*.pyc",
    ".gemini",
    ".agent",
}

# Standard Mode: Experience First (Non-blocking, ignores docs/tests)
STANDARD_MODE = AuditMode(
    name="standard",
    is_blocking=False,
    exclude_patterns=BASE_EXCLUSIONS
    | {
        "docs",
        "tests",
        "Archive",
        "conversation",
        "logs",
        "tmp",
        "*.md",
        "*.txt",  # Standard mode focuses on Code
    },
)

# Strict Mode: Safety First (Blocking, scans everything feasible)
STRICT_MODE = AuditMode(
    name="strict",
    is_blocking=True,
    exclude_patterns=BASE_EXCLUSIONS
    | {
        # Strict mode scans docs/tests, but still skips binary/system noise
        "tmp"
    },
)
