"""
Security Module Tests - 敏感信息检测测试

测试新实现的SensitiveDataDetector类
"""

from dimcause.utils.security import (
    SensitiveDataDetector,
    detect_sensitive_data,
    get_detector,
    redact_sensitive_data,
    sanitize_text,
)

OPENAI_TEST_KEY = "sk-" + ("a" * 48)
GITHUB_TEST_TOKEN = "ghp_" + ("b" * 36)
SLACK_TEST_TOKEN = "xoxb-" + ("1" * 10) + "-" + ("2" * 10) + "-" + ("c" * 24)


class TestSensitiveDataDetector:
    """测试SensitiveDataDetector类"""

    def test_detect_openai_key(self):
        """检测OpenAI API Key"""
        detector = SensitiveDataDetector()
        text = f"My key is {OPENAI_TEST_KEY}"

        findings = detector.detect(text)

        assert len(findings) > 0
        assert any(f.type == "openai_key" for f in findings)
        assert findings[0].severity == "critical"

    def test_detect_github_token(self):
        """检测GitHub Token"""
        detector = SensitiveDataDetector()
        # GitHub PAT正确格式: ghp_ + 36字符
        text = f"GITHUB_TOKEN={GITHUB_TEST_TOKEN}"

        findings = detector.detect(text)

        assert len(findings) > 0
        assert any(f.type == "github_token" for f in findings)

    def test_detect_aws_access_key(self):
        """检测AWS Access Key"""
        detector = SensitiveDataDetector()
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"

        findings = detector.detect(text)

        assert len(findings) > 0
        assert any(f.type == "aws_access_key" for f in findings)

    def test_detect_private_key(self):
        """检测Private Key"""
        detector = SensitiveDataDetector()
        text = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----
"""

        findings = detector.detect(text)

        assert len(findings) > 0
        assert any(f.type == "private_key" for f in findings)

    def test_detect_jwt_token(self):
        """检测JWT Token"""
        detector = SensitiveDataDetector()
        text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123"

        findings = detector.detect(text)

        assert len(findings) > 0
        assert any(f.type == "jwt_token" for f in findings)

    def test_detect_email(self):
        """检测Email (PII)"""
        detector = SensitiveDataDetector()
        text = "Contact me at user@example.com"

        findings = detector.detect(text)

        assert len(findings) > 0
        assert any(f.type == "email" for f in findings)
        assert findings[0].severity == "medium"

    def test_redact(self):
        """测试脱敏功能"""
        detector = SensitiveDataDetector()
        text = f"Key: {OPENAI_TEST_KEY}"

        redacted = detector.redact(text)

        assert "sk-" not in redacted
        assert "[REDACTED" in redacted
        assert "OPENAI_KEY" in redacted.upper()

    def test_sanitize_for_storage(self):
        """测试存储前安全预处理"""
        detector = SensitiveDataDetector()
        text = f"API_KEY={OPENAI_TEST_KEY}"

        sanitized, findings = detector.sanitize_for_storage(text)

        assert len(findings) > 0
        assert "sk-" not in sanitized
        assert "[REDACTED" in sanitized

    def test_no_false_positive(self):
        """正常文本无误报"""
        detector = SensitiveDataDetector()
        text = """
This is normal code.
No sensitive information here.
Just some Python examples.
"""

        findings = detector.detect(text)

        assert len(findings) == 0

    def test_multiple_findings(self):
        """测试多个敏感信息"""
        detector = SensitiveDataDetector()
        text = f"""
openai_key = {OPENAI_TEST_KEY}
github_token = {GITHUB_TEST_TOKEN}
email = test@example.com
"""

        findings = detector.detect(text)

        assert len(findings) >= 3
        types = {f.type for f in findings}
        assert "openai_key" in types
        assert "github_token" in types
        assert "email" in types

    def test_disabled_detector(self):
        """禁用检测器"""
        detector = SensitiveDataDetector(enabled=False)
        text = OPENAI_TEST_KEY

        findings = detector.detect(text)

        assert len(findings) == 0

    def test_has_sensitive_data(self):
        """快速检查是否有敏感数据"""
        detector = SensitiveDataDetector()

        assert detector.has_sensitive_data(OPENAI_TEST_KEY) is True
        assert detector.has_sensitive_data("normal text") is False


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_detect_sensitive_data(self):
        """测试全局检测函数"""
        text = OPENAI_TEST_KEY
        findings = detect_sensitive_data(text)

        assert len(findings) > 0

    def test_redact_sensitive_data(self):
        """测试全局脱敏函数"""
        text = f"My key: {OPENAI_TEST_KEY}"
        redacted = redact_sensitive_data(text)

        assert "sk-" not in redacted
        assert "[REDACTED" in redacted

    def test_sanitize_text(self):
        """测试全局安全预处理"""
        text = GITHUB_TEST_TOKEN
        sanitized, findings = sanitize_text(text)

        assert len(findings) > 0
        assert "ghp_" not in sanitized

    def test_singleton_detector(self):
        """测试单例模式"""
        detector1 = get_detector()
        detector2 = get_detector()

        assert detector1 is detector2


def test_real_world_claude_conversation():
    """真实Claude对话场景"""
    detector = SensitiveDataDetector()

    conversation = f"""
User: Help me debug this
```python
import openai
openai.api_key = '{OPENAI_TEST_KEY}'
response = openai.Completion.create(...)
```
Assistant: I see the issue...
"""

    sanitized, findings = detector.sanitize_for_storage(conversation)

    # 应该检测到API key
    assert len(findings) > 0
    assert any(f.type == "openai_key" for f in findings)

    # 脱敏后不应包含真实key
    assert OPENAI_TEST_KEY[:12] not in sanitized

    # 应保留代码结构
    assert "import openai" in sanitized
    # "openai.api_key"可能被脱敏成"openai.[REDACTED]_GENERIC_API_KEY",这是正确行为
    assert "openai" in sanitized


def test_anthropic_key_detection():
    """测试Anthropic API Key检测"""
    detector = SensitiveDataDetector()

    # 模拟Anthropic key (sk-ant- + 95+ chars)
    text = "sk-ant-" + "a" * 95

    findings = detector.detect(text)

    assert len(findings) > 0
    assert findings[0].type == "anthropic_key"


def test_slack_token_detection():
    """测试Slack Token检测"""
    detector = SensitiveDataDetector()

    text = f"SLACK_TOKEN={SLACK_TEST_TOKEN}"

    findings = detector.detect(text)

    assert len(findings) > 0
    assert any(f.type == "slack_token" for f in findings)


def test_credit_card_detection():
    """测试信用卡号检测"""
    detector = SensitiveDataDetector()

    text = "Card: 1234 5678 9012 3456"

    findings = detector.detect(text)

    assert len(findings) > 0
    assert any(f.type == "credit_card" for f in findings)


def test_ssn_detection():
    """测试SSN检测"""
    detector = SensitiveDataDetector()

    text = "SSN: 123-45-6789"

    findings = detector.detect(text)

    assert len(findings) > 0
    assert any(f.type == "ssn" for f in findings)


def test_password_assignment_detection():
    """测试密码赋值检测"""
    detector = SensitiveDataDetector()

    text = 'password = "mysecretpass123"'

    findings = detector.detect(text)

    assert len(findings) > 0
    assert any(f.type == "password_assignment" for f in findings)


def test_performance_large_text():
    """测试大文本性能"""
    detector = SensitiveDataDetector()

    # 1MB文本
    large_text = "normal text " * 100000
    large_text += " " + OPENAI_TEST_KEY

    import time

    start = time.time()
    findings = detector.detect(large_text)
    duration = time.time() - start

    assert len(findings) > 0
    assert duration < 1.0  # 应该在1秒内完成
