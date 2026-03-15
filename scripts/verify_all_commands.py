import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Setup path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# MOCK EVERYTHING to isolate CLI logic
MOCK_MODULES = [
    "dimcause.core.models",
    "dimcause.core",
    "dimcause.core.trace",
    "dimcause.ui",
    "dimcause.ui.trace_view",
    "dimcause.search",
    "dimcause.utils",
    "dimcause.utils.linter",
    "dimcause.utils.security",
    "dimcause.core.history",
    "dimcause.brain",
    "dimcause.brain.why",
    "dimcause.scheduler",
    "dimcause.daemon",
    "dimcause.daemon.process",
    "dimcause.storage",
    "dimcause.core.stats",
    "dimcause.brain.analyzer",
    "dimcause.extractors",
    "dimcause.extractors.llm_client",
    "dimcause.core.event_index",
    "dimcause.core.state",
    "builtins.open",  # Mock file open to prevent reading
]

for mod in MOCK_MODULES:
    sys.modules[mod] = MagicMock()

# Specific mocks needed for imports to work
sys.modules["dimcause.core.models"].EventType = MagicMock()
sys.modules["dimcause.core.models"].SourceType = MagicMock()

# Mock rich.prompt to avoid hangs
sys.modules["rich.prompt"] = MagicMock()

# Import CLI
from dimcause import cli  # noqa: E402

# Patch Confirm/Prompt/IntPrompt locally just in case
cli.Confirm = MagicMock()
cli.Prompt = MagicMock()
cli.IntPrompt = MagicMock()
cli.Confirm.ask.return_value = True
cli.Prompt.ask.return_value = "y"
cli.IntPrompt.ask.return_value = 1


class TestAllCommands(unittest.TestCase):
    def check_command(self, func, name, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        print(f"Testing {name}...", end=" ", flush=True)
        try:
            func(*args, **kwargs)
            print("OK (Ran)")
        except TypeError as e:
            if "OptionInfo" in str(e):
                print("FAIL (OptionInfo Crash)")
                self.fail(f"Command '{name}' crashed with OptionInfo error: {e}")
            else:
                print(f"OK (TypeError safe: {e})")
        except Exception as e:
            # Any other exception means Typer didn't crash on arguments!
            print(f"OK (Exception safe: {type(e).__name__})")

    def test_all(self):
        # List of functions found via grep
        commands = [
            ("daily_start", cli.daily_start),
            ("daily_end", cli.daily_end),
            ("job_start", cli.job_start),
            ("job_end", cli.job_end),
            ("index", cli.index),
            ("context", cli.context),
            # ("version", cli.version), # Might not be top level if imported from package
            ("reflect", cli.reflect),
            ("log", cli.log_cmd),
            ("tasks", cli.tasks),
            ("sanitize", cli.sanitize),
            ("scan", cli.scan),
            ("trace", cli.trace),
            ("audit", cli.audit),
            ("init", cli.init),
            ("stats", cli.stats),
            ("search", cli.search),
            ("daemon", cli.daemon),
            ("capture", cli.capture),
            ("template_list", cli.template_list),
            ("template_show", cli.template_show),
            ("template_use", cli.template_use),
            ("history", cli.history),
            ("why", cli.why),
            ("timeline", cli.timeline),
            ("view", cli.view),
            ("agent_create", cli.agent_create),
            ("agent_list", cli.agent_list),
            ("agent_revoke", cli.agent_revoke),
            ("agent_cleanup", cli.agent_cleanup),
            ("agent_info", cli.agent_info),
            ("ingest_data", cli.ingest_data),
            ("migrate", cli.migrate),
            ("scheduler_plan", cli.scheduler_plan),
            ("scheduler_status", cli.scheduler_status),
            ("scheduler_run", cli.scheduler_run),
            ("scheduler_loop", cli.scheduler_loop),
            ("lint", cli.lint),
            ("dashboard", cli.dashboard),
            ("extract_file", cli.extract_file),
            ("extract_diff", cli.extract_diff),
        ]

        print(f"Verifying {len(commands)} commands...")

        for name, func in commands:
            # We call with no args. If function requires args, it will raise TypeError (missing arg),
            # but NOT "OptionInfo" error (which comes from defaults).
            # If it has defaults using Option(), they are evaluated.
            self.check_command(func, name)


if __name__ == "__main__":
    unittest.main()
