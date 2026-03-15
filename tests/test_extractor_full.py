"""
DIMCAUSE v0.1 Extractor 完整测试

覆盖 BasicExtractor 的所有方法
"""

import json
from unittest.mock import MagicMock, patch


class TestBasicExtractorRegex:
    """测试 Regex 降级提取"""

    def test_extract_without_llm(self):
        """测试无 LLM 时的 Regex 提取"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor

        # 不传入 LLM 客户端
        extractor = BasicExtractor(llm_client=None)

        event = extractor.extract("我决定使用 FastAPI 框架")

        assert event is not None
        assert event.type == EventType.DECISION
        assert event.confidence == 0.5  # Regex 置信度

    def test_detect_type_decision(self):
        """测试检测决策类型"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        texts = [
            "我们决定使用 PostgreSQL",
            "I decide to use Redis",
            "选择了 FastAPI 框架",
            "will use JWT for auth",
            "采用微服务架构",
        ]

        for text in texts:
            result = extractor._detect_type_regex(text)
            assert result == EventType.DECISION, f"Failed for: {text}"

    def test_detect_type_code_change(self):
        """测试检测代码变更类型"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        texts = [
            "修改了登录函数",
            "修复了内存泄漏",
            "fix the bug in auth.py",
            "implement new feature",
            "实现用户注册功能",
        ]

        for text in texts:
            result = extractor._detect_type_regex(text)
            assert result == EventType.CODE_CHANGE, f"Failed for: {text}"

    def test_detect_type_diagnostic(self):
        """测试检测诊断类型"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        texts = [
            "发现一个 error",
            "found a bug in login",
            "这是一个问题",
            "debugging the issue",
            "调试登录流程",
        ]

        for text in texts:
            result = extractor._detect_type_regex(text)
            assert result == EventType.DIAGNOSTIC, f"Failed for: {text}"

    def test_detect_type_research(self):
        """测试检测调研类型"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        texts = [
            "需要 research 一下",
            "调研竞品功能",
            "learn about async",
            "study the architecture",
        ]

        for text in texts:
            result = extractor._detect_type_regex(text)
            assert result == EventType.RESEARCH, f"Failed for: {text}"

    def test_extract_entities_regex(self):
        """测试 Regex 实体提取"""
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        content = "修改了 src/auth.py 中的 def login() 函数"
        entities = extractor._extract_entities_regex(content)

        assert len(entities) >= 1
        names = [e.name for e in entities]
        [e.type for e in entities]

        # 应该找到文件
        assert any("auth.py" in n for n in names)

    def test_extract_files_regex(self):
        """测试文件提取"""
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        content = "编辑了 main.py, config.json 和 styles.css"
        files = extractor._extract_files_regex(content)

        assert len(files) >= 2

    def test_extract_batch(self):
        """测试批量提取"""
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        contents = [
            "决定使用 Redis",
            "修复了登录 bug",
            "研究 async 用法",
        ]

        events = extractor.extract_batch(contents)

        assert len(events) == 3

    def test_long_content_summary(self):
        """测试长内容摘要截断"""
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        # 创建超长内容
        long_content = "这是很长的内容" * 50

        event = extractor.extract(long_content)

        # 摘要应该被截断
        assert len(event.summary) <= 103  # 100 + "..."


class TestBasicExtractorLLM:
    """测试 LLM 提取"""

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_extract_with_llm_success(self, mock_litellm, mock_completion):
        """测试 LLM 提取成功"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor
        from dimcause.extractors.llm_client import LiteLLMClient

        # Mock LLM 返回
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "type": "decision",
                "summary": "选择 PostgreSQL 数据库",
                "entities": [
                    {"name": "PostgreSQL", "type": "library"},
                    {"name": "database.py", "type": "file"},
                ],
                "tags": ["database", "architecture"],
                "files": ["database.py"],
            }
        )
        mock_completion.return_value = mock_response

        client = LiteLLMClient()
        extractor = BasicExtractor(llm_client=client)

        event = extractor.extract("我们决定使用 PostgreSQL 作为数据库")

        assert event is not None
        assert event.type == EventType.DECISION
        assert event.confidence == 0.9  # LLM 置信度

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_extract_with_llm_fallback(self, mock_litellm, mock_completion):
        """测试 LLM 失败后降级到 Regex"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor
        from dimcause.extractors.llm_client import LiteLLMClient

        # Mock LLM 失败
        mock_completion.side_effect = Exception("LLM Error")

        client = LiteLLMClient()
        extractor = BasicExtractor(llm_client=client)

        # 应该降级到 Regex
        event = extractor.extract("我决定使用 FastAPI")

        assert event is not None
        assert event.type == EventType.DECISION
        assert event.confidence == 0.5  # Regex 置信度

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_parse_json_response_clean(self, mock_litellm, mock_completion):
        """测试解析干净的 JSON"""
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        response = '{"type": "decision", "summary": "test"}'
        data = extractor._parse_json_response(response)

        assert data["type"] == "decision"

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_parse_json_response_with_markdown(self, mock_litellm, mock_completion):
        """测试解析带 markdown 的 JSON"""
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        response = """```json
{"type": "code_change", "summary": "test"}
```"""
        data = extractor._parse_json_response(response)

        assert data["type"] == "code_change"

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_parse_json_response_embedded(self, mock_litellm, mock_completion):
        """测试解析嵌入文本中的 JSON"""
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        response = 'Here is the result: {"type": "research", "summary": "test"} end.'
        data = extractor._parse_json_response(response)

        assert data["type"] == "research"

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_create_event_from_data(self, mock_litellm, mock_completion):
        """测试从数据创建 Event"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        data = {
            "type": "decision",
            "summary": "选择 FastAPI",
            "entities": [
                {"name": "FastAPI", "type": "library"},
                {"name": "main.py", "type": "file"},
            ],
            "tags": ["framework"],
            "files": ["main.py"],
        }

        event = extractor._create_event("原始内容", data)

        assert event.type == EventType.DECISION
        assert event.summary == "选择 FastAPI"
        assert len(event.entities) == 2

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_create_event_unknown_type(self, mock_litellm, mock_completion):
        """测试创建未知类型 Event"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor

        extractor = BasicExtractor(llm_client=None)

        data = {"type": "invalid_type", "summary": "测试"}

        event = extractor._create_event("内容", data)

        assert event.type == EventType.UNKNOWN


class TestCreateExtractor:
    """测试工厂函数"""

    def test_create_extractor_without_client(self):
        """测试不带客户端创建"""
        from dimcause.extractors.extractor import create_extractor

        extractor = create_extractor(llm_client=None)

        assert extractor is not None
        assert extractor.llm is None

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_create_extractor_with_client(self, mock_litellm, mock_completion):
        """测试带客户端创建"""
        from dimcause.extractors.extractor import create_extractor
        from dimcause.extractors.llm_client import LiteLLMClient

        client = LiteLLMClient()
        extractor = create_extractor(llm_client=client)

        assert extractor.llm is not None
