import time
from datetime import datetime

from dimcause.cli import _get_daily_template
from dimcause.utils.state import get_all_recent_sessions, get_today_dir


def setup_dummy_sessions():
    """Create some dummy sessions for testing"""
    today_dir = get_today_dir()
    if not today_dir.exists():
        today_dir.mkdir(parents=True)

    # Session 1: Agent A, Completed
    seq1 = "A1"
    start1 = today_dir / f"{seq1}-start.md"
    end1 = today_dir / f"{seq1}-end.md"
    start1.write_text(f"---\nagent: agent_A\ndate: {datetime.now()}\n---\n", encoding="utf-8")
    end1.write_text("---\ndescription: Finished Task A\n---\n", encoding="utf-8")

    # Session 2: Agent B, Active
    seq2 = "B1"
    start2 = today_dir / f"{seq2}-start.md"
    start2.write_text(f"---\nagent: agent_B\ndate: {datetime.now()}\n---\n", encoding="utf-8")

    # Session 3: Agent A, Completed with Summary Section
    time.sleep(1)  # Ensure time difference
    seq3 = "A2"
    start3 = today_dir / f"{seq3}-start.md"
    end3 = today_dir / f"{seq3}-end.md"
    start3.write_text(f"---\nagent: agent_A\ndate: {datetime.now()}\n---\n", encoding="utf-8")
    end3.write_text(
        "---\nstatus: done\n---\n\n## Summary\nImplemented complex feature X.\n", encoding="utf-8"
    )

    print(f"Created dummy sessions in {today_dir}")
    return today_dir


def verify_context():
    setup_dummy_sessions()

    # Test get_all_recent_sessions
    sessions = get_all_recent_sessions(lookback_days=1)
    print(f"\nFound {len(sessions)} recent sessions:")
    for s in sessions:
        print(f"- {s.seq} (Agent: {s.agent}) Summary: {s.summary}")

    # Test template generation
    print("\nGenerating template...")
    # Mock date_str and session_id
    date_str = datetime.now().strftime("%Y-%m-%d")
    session_id = f"{date_str}-NEW"

    template = _get_daily_template("start", date_str, session_id)

    print("\n--- Generated Context Section ---")
    context_section = template.split("## 🧠 上下文 (Context)")[1].split("## 🎯 今日目标")[0]
    print(context_section.strip())

    # Assertions
    if "agent_A" in context_section and "agent_B" in context_section:
        if (
            "Finished Task A" in context_section
            and "Implemented complex feature X" in context_section
        ):
            print("\nSUCCESS: Context contains expected agent info and summaries.")
        else:
            print("\nFAILURE: Context missing summaries.")
    else:
        print("\nFAILURE: Context missing agent IDs.")


if __name__ == "__main__":
    verify_context()
