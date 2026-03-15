from dataclasses import dataclass, field
from typing import Any, List, Optional

from dimcause.audit.mode import AuditMode
from dimcause.core.timeline import DailyStats


@dataclass
class SecurityFinding:
    """A specific security issue found during audit."""

    rule_id: str  # e.g. "SEC001", "BANDIT-B101"
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    file_path: str
    line: Optional[int]
    message: str
    context: Optional[str] = None


@dataclass
class AuditResult:
    """
    Unified result of an audit execution.
    Contains both security findings and timeline context.
    """

    mode: AuditMode
    success: bool
    exit_code: int

    # Timeline Context (from TimelineService)
    timeline_stats: Optional[DailyStats] = None

    # Security Issues
    findings: List[SecurityFinding] = field(default_factory=list)

    # Causal Issues (from AxiomValidator)
    causal_issues: List[Any] = field(default_factory=list)  # List[ValidationResult]

    # Legacy Check Results (for backward compat / raw details)
    raw_results: List[Any] = field(default_factory=list)

    @property
    def summary_text(self) -> str:
        """Generating a quick summary string."""
        parts = []
        if self.timeline_stats:
            parts.append(f"Events: {self.timeline_stats.total_events}")
        parts.append(f"Security: {len(self.findings)} findings")
        status = "PASSED" if self.success else "FAILED"
        return f"[{status}] {' | '.join(parts)}"
