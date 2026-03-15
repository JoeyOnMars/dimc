"""
Dimcause Security Utilities - 敏感信息检测与脱敏

Critical P0 Implementation: 防止 API Keys/Tokens 泄露到日志和索引
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SensitiveFinding:
    """敏感信息发现记录"""

    type: str  # openai_key, github_token, etc.
    matched_text: str  # 匹配到的原文(用于审计,不会存储)
    position: Tuple[int, int]  # (start, end)
    severity: str  # critical, high, medium


class SensitiveDataDetector:
    """
    敏感信息检测器

    检测并脱敏常见的API密钥、Token、密码等敏感信息。
    防止这些信息被索引到Vector DB或写入Markdown日志。
    """

    # 敏感信息正则模式 (基于真实泄露案例)
    PATTERNS: Dict[str, Tuple[str, str]] = {
        # OpenAI API Keys
        "openai_key": (r"sk-[a-zA-Z0-9]{48}", "critical"),
        # Anthropic API Keys
        "anthropic_key": (r"sk-ant-[a-zA-Z0-9\-]{95,}", "critical"),
        # GitHub Personal Access Tokens
        "github_token": (r"ghp_[a-zA-Z0-9]{36}", "critical"),
        # GitHub OAuth Tokens
        "github_oauth": (r"gho_[a-zA-Z0-9]{36}", "critical"),
        # AWS Access Keys
        "aws_access_key": (r"AKIA[0-9A-Z]{16}", "critical"),
        # AWS Secret Keys (partial detection)
        "aws_secret_key": (
            r"[A-Za-z0-9/+=]{40}",  # 需要配合上下文判断
            "high",
        ),
        # Slack Tokens
        "slack_token": (r"xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,}", "critical"),
        # JWT Tokens
        "jwt_token": (r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", "high"),
        # Generic API Keys (common patterns)
        "generic_api_key": (
            r'(?i)(api[_-]?key|apikey|api[_-]?secret)[\s:=]+["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            "high",
        ),
        # Email addresses (PII)
        "email": (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "medium"),
        # Credit Card numbers (basic pattern)
        "credit_card": (r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b", "critical"),
        # US Social Security Numbers
        "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "critical"),
        # Private Keys (PEM format)
        "private_key": (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "critical"),
        # Passwords in common formats
        "password_assignment": (
            r'(?i)(password|passwd|pwd)[\s:=]+["\']?([^\s"\']{8,})["\']?',
            "high",
        ),
    }

    def __init__(self, enabled: bool = True):
        """
        初始化检测器

        Args:
            enabled: 是否启用检测(默认启用)
        """
        self.enabled = enabled
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, Tuple[re.Pattern, str]]:
        """预编译所有正则模式(性能优化)"""
        compiled = {}
        for key, (pattern, severity) in self.PATTERNS.items():
            try:
                compiled[key] = (re.compile(pattern), severity)
            except re.error as e:
                logger.error(f"Failed to compile pattern '{key}': {e}")
        return compiled

    def detect(self, text: str) -> List[SensitiveFinding]:
        """
        检测文本中的敏感信息

        Args:
            text: 要检测的文本

        Returns:
            敏感信息发现列表
        """
        if not self.enabled or not text:
            return []

        findings = []

        for key, (pattern, severity) in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                findings.append(
                    SensitiveFinding(
                        type=key,
                        matched_text=match.group(0),
                        position=(match.start(), match.end()),
                        severity=severity,
                    )
                )

        return findings

    def redact(self, text: str, placeholder: str = "[REDACTED]") -> str:
        """
        脱敏文本中的敏感信息

        Args:
            text: 要脱敏的文本
            placeholder: 替换占位符(默认 [REDACTED])

        Returns:
            脱敏后的文本
        """
        if not self.enabled or not text:
            return text

        redacted = text

        # 按位置倒序替换(避免索引偏移)
        findings = sorted(self.detect(text), key=lambda f: f.position[0], reverse=True)

        for finding in findings:
            start, end = finding.position
            replacement = f"{placeholder}_{finding.type.upper()}"
            redacted = redacted[:start] + replacement + redacted[end:]

        return redacted

    def sanitize_for_storage(self, text: str) -> Tuple[str, List[SensitiveFinding]]:
        """
        为存储准备文本(检测+脱敏+审计)

        这是推荐的安全存储预处理方法。

        Args:
            text: 原始文本

        Returns:
            (脱敏后的文本, 发现的敏感信息列表)
        """
        findings = self.detect(text)

        if findings:
            # 记录审计日志(不记录具体内容,只记录类型和数量)
            logger.warning(
                f"⚠️ Detected {len(findings)} sensitive items: "
                f"{', '.join({f.type for f in findings})}"
            )

        sanitized_text = self.redact(text)

        return sanitized_text, findings

    def has_sensitive_data(self, text: str) -> bool:
        """
        快速检查文本是否包含敏感信息

        Args:
            text: 要检查的文本

        Returns:
            True if 包含敏感信息
        """
        return len(self.detect(text)) > 0


# 全局单例实例
_detector_instance = None


def get_detector(enabled: bool = True) -> SensitiveDataDetector:
    """获取全局检测器实例(单例模式)"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = SensitiveDataDetector(enabled=enabled)
    return _detector_instance


# 便捷函数
def detect_sensitive_data(text: str) -> List[SensitiveFinding]:
    """便捷函数:检测敏感信息"""
    return get_detector().detect(text)


def redact_sensitive_data(text: str) -> str:
    """便捷函数:脱敏敏感信息"""
    return get_detector().redact(text)


def sanitize_text(text: str) -> Tuple[str, List[SensitiveFinding]]:
    """便捷函数:安全预处理(推荐使用)"""
    return get_detector().sanitize_for_storage(text)


# ========== 测试兼容性别名 ==========
detect_sensitive = detect_sensitive_data


def sanitize(text: str) -> Tuple[str, List[SensitiveFinding]]:
    """脱敏文本并返回发现的敏感信息（兼容测试API）"""
    return sanitize_text(text)


def is_safe(text: str) -> bool:
    """检查文本是否安全（不含敏感信息）"""
    return not get_detector().has_sensitive_data(text)


def sanitize_file(file_path: str, dry_run: bool = False) -> Dict[str, any]:
    """
    脱敏文件内容（返回 CLI 兼容的字典格式）

    Args:
        file_path: 文件路径
        dry_run: 仅检测不修改（默认 False）

    Returns:
        {
            "file": 文件路径,
            "matches": 发现数量,
            "details": 发现详情列表,
            "content": 脱敏后内容,
            "sanitized": 是否已写入
        }
    """
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    content = path.read_text(encoding="utf-8", errors="ignore")
    sanitized, findings = sanitize_text(content)

    sanitized_flag = False
    if not dry_run and findings:
        path.write_text(sanitized, encoding="utf-8")
        sanitized_flag = True

    # 构建 details 列表
    details = []
    for finding in findings:
        details.append(
            {
                "type": finding.type,
                "preview": finding.matched_text[:20] + "..."
                if len(finding.matched_text) > 20
                else finding.matched_text,
                "severity": finding.severity,
            }
        )

    return {
        "file": str(file_path),
        "matches": len(findings),
        "details": details,
        "content": sanitized,
        "sanitized": sanitized_flag,
    }
