from unittest.mock import MagicMock

from dimcause.brain.decision_analyzer import DecisionAnalyzer
from dimcause.core.history import GitCommit


def test_analyze_evolution_prompt_structure():
    """Test that the prompt is built correctly from commits."""
    mock_client = MagicMock()
    # Mock complete to return a fixed string
    mock_client.complete.return_value = "This is a story about code."

    analyzer = DecisionAnalyzer(mock_client)

    # Create mock commits with context
    commit1 = GitCommit(hash="abc1234", date="2026-01-02", author="dev", message="feat: add login")
    # Attach context manully (simulating core.history)
    commit1.context_events = [
        {"type": "decision", "summary": "Decided to use OAuth", "id": "evt_1"}
    ]

    commit2 = GitCommit(hash="def5678", date="2026-01-01", author="dev", message="init")
    commit2.from_causal_chain = True

    commits = [commit1, commit2]

    # Run analysis
    result = analyzer.analyze_evolution(file_path="src/auth.py", commits=commits, lang="en")

    # Verify result
    assert result == "This is a story about code."

    # Verify client call
    mock_client.complete.assert_called_once()
    call_args = mock_client.complete.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]

    # Check prompt content
    assert "src/auth.py" in prompt
    assert "feat: add login" in prompt
    assert "Decided to use OAuth" in prompt  # Context should be included
    assert "Causal Evidence" in prompt
    assert "Write in English" in prompt
