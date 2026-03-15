import subprocess
from pathlib import Path
from typing import List

from dimcause.audit.engine import BaseCheck, CheckResult


def _resolve_targets(files: List[Path]) -> tuple[List[str], bool]:
    """Resolve file/directory mix into targets for ruff/mypy.

    Returns (target_strings, has_valid_targets).
    Directories are passed through (ruff/mypy handle recursion).
    Individual files are filtered to .py only.
    """
    dirs = [str(f) for f in files if f.is_dir()]
    py_files = [str(f) for f in files if f.is_file() and f.suffix == ".py"]
    targets = dirs + py_files
    return targets, len(targets) > 0


class RuffCheck(BaseCheck):
    name = "lint"
    description = "Code linting using Ruff"

    def run(self, files: List[Path]) -> CheckResult:
        targets, has_targets = _resolve_targets(files)

        if not has_targets and files:
            return CheckResult(self.name, True, "No python files to lint")

        cmd = ["ruff", "check"]

        if self.config.get("fix", False):
            cmd.append("--fix")

        if targets:
            cmd.extend(targets)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            success = result.returncode == 0

            details = result.stdout.splitlines() + result.stderr.splitlines()

            return CheckResult(
                check_name=self.name,
                success=success,
                message="Lint check passed"
                if success
                else f"Found {len([line for line in details if 'error' in line.lower()])} issues",
                details=details,
            )
        except Exception as e:
            return CheckResult(self.name, False, f"Execution failed: {e}")


class FormatCheck(BaseCheck):
    name = "format"
    description = "Code formatting check using Ruff"

    def run(self, files: List[Path]) -> CheckResult:
        targets, has_targets = _resolve_targets(files)

        if not has_targets and files:
            return CheckResult(self.name, True, "No python files to format")

        cmd = ["ruff", "format", "--check"]
        if self.config.get("fix", False):
            cmd = ["ruff", "format"]

        if targets:
            cmd.extend(targets)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            success = result.returncode == 0

            msg = "Format check passed"
            if not success:
                if self.config.get("fix"):
                    msg = "Formatted files"
                else:
                    msg = "Files need formatting (run with --fix)"

            return CheckResult(
                check_name=self.name,
                success=success,
                message=msg,
                details=result.stdout.splitlines() + result.stderr.splitlines(),
            )
        except Exception as e:
            return CheckResult(self.name, False, f"Execution failed: {e}")


class MypyCheck(BaseCheck):
    name = "type_check"
    description = "Static type checking using Mypy"

    def run(self, files: List[Path]) -> CheckResult:
        targets, has_targets = _resolve_targets(files)

        if not has_targets and files:
            return CheckResult(self.name, True, "No python files to type check")

        cmd = ["mypy", "--ignore-missing-imports"]

        if targets:
            cmd.extend(targets)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            success = result.returncode == 0

            output_lines = result.stdout.splitlines() + result.stderr.splitlines()

            return CheckResult(
                check_name=self.name,
                success=success,
                message="Type check passed" if success else "Found type issues",
                details=output_lines,
            )
        except FileNotFoundError:
            return CheckResult(
                self.name, True, "Mypy not installed (skipped)", details=["pip install mypy"]
            )
        except Exception as e:
            return CheckResult(self.name, False, f"Execution failed: {e}")
