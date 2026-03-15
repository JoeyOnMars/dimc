import subprocess
from pathlib import Path
from typing import List

from dimcause.audit.engine import BaseCheck, CheckResult


class MypyCheck(BaseCheck):
    name = "type"
    description = "Static type checking using MyPy"

    def run(self, files: List[Path]) -> CheckResult:
        # Directories: let mypy handle recursion; only filter individual files
        dirs = [str(f) for f in files if f.is_dir()]
        py_files = [str(f) for f in files if f.is_file() and f.suffix == ".py"]
        targets = dirs + py_files

        if not targets and files:
            return CheckResult(self.name, True, "No python files to check")

        cmd = ["mypy"]
        if targets:
            cmd.extend(targets)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            success = result.returncode == 0

            return CheckResult(
                check_name=self.name,
                success=success,
                message="Type check passed" if success else "Type errors found",
                details=result.stdout.splitlines() + result.stderr.splitlines(),
            )
        except Exception as e:
            return CheckResult(self.name, False, f"Execution failed: {e}")
