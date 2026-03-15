import json
import subprocess
from pathlib import Path
from typing import List

from dimcause.audit.engine import BaseCheck, CheckResult
from dimcause.utils.security import SensitiveFinding, get_detector


class SensitiveInfoCheck(BaseCheck):
    name = "sensitive_data"
    description = "Scan source code for hardcoded secrets (API keys, tokens)"

    def run(self, files: List[Path]) -> CheckResult:
        detector = get_detector()
        issues = []
        scanned_count = 0

        from fnmatch import fnmatch

        # Use exclusions from AuditMode
        exclusions = self.mode.exclude_patterns

        # Binary or non-text extensions to skip (always skip these)
        skip_extensions = {
            ".pyc",
            ".mo",
            ".db",
            ".sqlite",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".ico",
        }

        for file_path in files:
            # Recursive expansion if directory
            if file_path.is_dir():
                for f in file_path.rglob("*"):
                    if f.is_file():
                        # Check global exclusions (path parts)
                        if any(part in exclusions for part in f.parts):
                            continue
                        # Check pattern exclusions (glob)
                        # Note: we check simple glob against file name for now for backward compat
                        if any(fnmatch(f.name, pat) for pat in exclusions):
                            continue

                        if f.suffix in skip_extensions:
                            continue
                        if f.name == ".DS_Store":
                            continue

                        self._scan_file(f, detector, issues)
                        scanned_count += 1
            else:
                # Check exclusions for direct files
                if any(part in exclusions for part in file_path.parts):
                    continue
                if any(fnmatch(file_path.name, pat) for pat in exclusions):
                    continue

                if file_path.suffix not in skip_extensions and file_path.name != ".DS_Store":
                    self._scan_file(file_path, detector, issues)
                    scanned_count += 1

        # Blocking logic controlled by AuditMode
        is_blocking = self.mode.is_blocking
        success = len(issues) == 0

        msg = f"Scanned {scanned_count} files. " + (
            "No leaks found." if success else f"Found {len(issues)} items."
        )

        return CheckResult(
            check_name=self.name,
            success=success,
            is_blocking=is_blocking,
            message=msg,
            details=issues,
        )

    def _scan_file(self, file_path: Path, detector, issues: List[str]):
        try:
            # Skip large files > 1MB
            if file_path.stat().st_size > 1024 * 1024:
                return

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            findings: List[SensitiveFinding] = detector.detect(content)

            for f in findings:
                # Format: [CRITICAL] path/to/file.py: Found openai_key
                issues.append(
                    f"[{f.severity.upper()}] {file_path}: Found {f.type} (pos: {f.position})"
                )

        except Exception:
            # Ignore read errors
            pass


class BanditCheck(BaseCheck):
    name = "bandit"
    description = "Security linter for Python code (common vulnerabilities)"

    def run(self, files: List[Path]) -> CheckResult:
        # Bandit handles recursion on directories.
        targets = [str(f) for f in files]

        cmd = ["bandit", "-f", "json", "-q", "-r"] + targets

        # If config file exists, use it? Bandit auto-detects .bandit?
        # We enforce some defaults via -LLL if strict?
        # For now, standard run.

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            # Bandit returns 0 on success (no issues), 1 on issues.

            try:
                data = json.loads(result.stdout)
                results = data.get("results", [])
                data.get("metrics", {})

                issues = []
                for item in results:
                    severity = item.get("issue_severity")
                    filename = item.get("filename")
                    line = item.get("line_number")
                    msg = item.get("issue_text")
                    # Make path relative if possible
                    try:
                        filename = Path(filename).relative_to(Path.cwd())
                    except Exception:
                        pass
                    issues.append(f"[{severity}] {filename}:{line} - {msg}")

                success = len(issues) == 0
                return CheckResult(
                    check_name=self.name,
                    success=success,
                    message="Bandit passed" if success else f"Found {len(issues)} security issues",
                    details=issues,
                )

            except json.JSONDecodeError:
                # Maybe bandit failed to run or produced non-json output (stderr)
                return CheckResult(self.name, False, f"Bandit execution failed: {result.stderr}")

        except FileNotFoundError:
            return CheckResult(
                self.name, True, "Bandit not installed (skipped)", details=["pip install bandit"]
            )
        except Exception as e:
            return CheckResult(self.name, False, f"Execution failed: {e}")
