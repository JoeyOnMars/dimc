"""
Audit Engine
Core logic for registering and running quality checks.
"""

import abc
import concurrent.futures
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dimcause.audit.mode import STANDARD_MODE, AuditMode

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single audit check execution."""

    check_name: str
    success: bool
    message: str = ""
    details: list[str] = field(default_factory=list)  # Detailed warnings/errors
    file_path: Optional[str] = None
    execution_time: float = 0.0
    is_blocking: bool = True  # If False, failure is treated as warning


class BaseCheck(abc.ABC):
    """Abstract base class for all audit checks."""

    name: str = "base_check"
    description: str = "Base audit check"

    def __init__(self, config: Dict[str, Any] = None, mode: AuditMode = STANDARD_MODE):
        self.config = config or {}
        self.mode = mode

    @abc.abstractmethod
    def run(self, files: List[Path]) -> CheckResult:
        """
        Run the check on the provided files.
        Returns a CheckResult.
        """
        pass


class AuditEngine:
    """
    Registry and runner for audit checks.
    """

    def __init__(self, mode: AuditMode = STANDARD_MODE):
        self._checks: List[BaseCheck] = []
        self.mode = mode

    def register(self, check: BaseCheck):
        """Register a check instance to be run."""
        self._checks.append(check)
        logger.debug(f"Registered check: {check.name}")

    def run_all(self, files: List[Path], parallel: bool = True) -> List[CheckResult]:
        """Run all registered checks."""
        results = []

        logger.info(f"Running {len(self._checks)} checks on {len(files)} files...")

        if parallel and len(self._checks) > 1:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_check = {
                    executor.submit(check.run, files): check for check in self._checks
                }
                for future in concurrent.futures.as_completed(future_to_check):
                    check = future_to_check[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Check {check.name} crashed: {e}")
                        results.append(
                            CheckResult(
                                check_name=check.name, success=False, message=f"Crashed: {e}"
                            )
                        )
        else:
            for check in self._checks:
                try:
                    results.append(check.run(files))
                except Exception as e:
                    logger.error(f"Check {check.name} crashed: {e}")
                    results.append(
                        CheckResult(check_name=check.name, success=False, message=f"Crashed: {e}")
                    )

        return results
