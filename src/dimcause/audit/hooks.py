import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

HOOK_TEMPLATE = """#!/bin/sh
# Dimcause Audit Hook
# Installed by `dimc audit --install-hooks`

echo "📝 Dimcause Audit Gate: Running pre-commit checks..."

# Check if dimc is available
if ! command -v dimc &> /dev/null; then
    # Try using the venv from the project root if visible
    # Assuming hook runs from repository root
    if [ -f ".venv/bin/dimc" ]; then
        DIMCAUSE_CMD=".venv/bin/dimc"
    else
        echo "⚠️  'dimc' command not found. Skipping audit."
        exit 0
    fi
else
    DIMCAUSE_CMD="dimc"
fi

# Run audit on staged files?
# Currently `dimc audit` runs on . (all files).
# Ideally we should filter staged files, but for now we run full scan.
# Faster if we respect gitignore.

$DIMCAUSE_CMD audit

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ Dimcause Audit Failed. Fix issues or use 'git commit --no-verify' to bypass."
    exit $EXIT_CODE
fi

echo "✅ Dimcause Audit Passed."
exit 0
"""


def install_pre_commit_hook():
    """Install the pre-commit hook in the current .git repository."""

    # 1. Find .git directory
    # Assume CWD is repo root, or search up?
    cwd = Path.cwd()
    git_dir = cwd / ".git"

    if not git_dir.exists():
        if (cwd.parent / ".git").exists():
            git_dir = cwd.parent / ".git"
        else:
            raise FileNotFoundError(
                "Could not find .git directory. Are you in the repository root?"
            )

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / "pre-commit"

    # 2. Check if hook exists
    if hook_path.exists():
        # Read content to see if it's ours
        content = hook_path.read_text(encoding="utf-8", errors="ignore")
        if "Dimcause Audit Hook" in content:
            logger.info("Dimcause pre-commit hook already installed.")
            return "Hook already installed."
        else:
            # Don't overwrite existing user hooks blindly
            # NOTE: Append? For now, we are cautious.
            raise FileExistsError(
                f"A pre-commit hook already exists at {hook_path}. Please remove or edit it manually."
            )

    # 3. Write hook
    logger.info(f"Installing hook to {hook_path}...")
    hook_path.write_text(HOOK_TEMPLATE, encoding="utf-8")

    # 4. Make executable
    current_mode = os.stat(hook_path).st_mode
    os.chmod(hook_path, current_mode | stat.S_IEXEC)

    return f"Successfully installed pre-commit hook at {hook_path}"
