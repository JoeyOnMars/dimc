from pathlib import Path
from unittest.mock import patch

import pytest

from dimcause.audit.checks.security import BanditCheck, SensitiveInfoCheck

OPENAI_TEST_KEY = "sk-" + ("a" * 48)


@pytest.fixture
def clean_file(tmp_path):
    f = tmp_path / "safe.py"
    f.write_text("print('hello')", encoding="utf-8")
    return f


@pytest.fixture
def dirty_file(tmp_path):
    f = tmp_path / "unsafe.py"
    f.write_text(f'KEY = "{OPENAI_TEST_KEY}"', encoding="utf-8")
    return f


def test_sensitive_check_safe(clean_file):
    check = SensitiveInfoCheck()
    result = check.run([clean_file])
    assert result.success
    assert "No leaks found" in result.message


def test_sensitive_check_unsafe(dirty_file):
    # Mocking get_detector if needed, but SensitiveDataDetector logic is pure regex (no external calls).
    # So we can run it "live".
    # The key in dirty_file matches 'openai_key' pattern (sk- + 48 chars)

    check = SensitiveInfoCheck()
    result = check.run([dirty_file])
    if result.success:
        pytest.fail(f"Should have failed. Findings: {result.details}")

    assert not result.success
    # It might find multiple (e.g. OpenAI key also looks like Generic key or AWS secret)
    # So we check if it found AT LEAST 1
    assert "Found" in result.message
    # Check details contain type
    assert any("openai_key" in d for d in result.details)


@patch("subprocess.run")
def test_bandit_check_success(mock_run):
    mock_run.return_value.stdout = '{"results": [], "metrics": {}}'
    mock_run.return_value.returncode = 0

    check = BanditCheck()
    result = check.run([Path(".")])
    assert result.success
    assert "Bandit passed" in result.message


@patch("subprocess.run")
def test_bandit_check_failure(mock_run):
    json_output = """
    {
        "results": [
            {
                "issue_severity": "HIGH",
                "filename": "test.py",
                "line_number": 10,
                "issue_text": "Hardcoded password"
            }
        ],
        "metrics": {}
    }
    """
    mock_run.return_value.stdout = json_output
    mock_run.return_value.returncode = 1

    check = BanditCheck()
    result = check.run([Path(".")])
    assert not result.success
    assert "Found 1" in result.message
    assert "test.py" in result.details[0]
