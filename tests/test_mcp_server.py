"""
测试 MCP Server 差异化端点

测试目标:
- get_causal_chain: 因果链追溯
- audit_check: 公理审计检查
- get_graph_context: 图谱概览
"""

from unittest.mock import MagicMock, patch

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


class FakeEntity:
    """模拟 GraphStore.find_related 返回的 Entity"""

    def __init__(self, name: str, type: str, context: str = None):
        self.name = name
        self.type = type
        self.context = context


class FakeValidationResult:
    """模拟 AxiomValidator.validate 返回的 ValidationResult"""

    def __init__(self, axiom_id: str, severity_value: str, message: str, entity_id: str):
        self.axiom_id = axiom_id
        self.severity = MagicMock(value=severity_value)
        self.message = message
        self.entity_id = entity_id
        self.details = {}


# ──────────────────────────────────────────────
# get_causal_chain 测试
# ──────────────────────────────────────────────


class TestGetCausalChain:
    """测试因果链追溯端点"""

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_正常返回关联实体(self, mock_store_fn):
        from dimcause.protocols.mcp_server import get_causal_chain

        mock_store = MagicMock()
        mock_store.find_related.return_value = [
            FakeEntity("evt_001", "decision", "选择 SQLite"),
            FakeEntity("evt_002", "commit"),
        ]
        mock_store_fn.return_value = mock_store

        result = get_causal_chain("evt_root", depth=2)

        assert "因果链追溯" in result
        assert "evt_001" in result
        assert "[decision]" in result
        assert "选择 SQLite" in result
        assert "2 个关联实体" in result
        mock_store.find_related.assert_called_once_with("evt_root", depth=2)

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_空图返回提示(self, mock_store_fn):
        from dimcause.protocols.mcp_server import get_causal_chain

        mock_store = MagicMock()
        mock_store.find_related.return_value = []
        mock_store_fn.return_value = mock_store

        result = get_causal_chain("unknown_id")

        assert "未找到" in result
        assert "unknown_id" in result

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_异常处理(self, mock_store_fn):
        from dimcause.protocols.mcp_server import get_causal_chain

        mock_store_fn.side_effect = RuntimeError("DB 连接失败")

        result = get_causal_chain("evt_xxx")

        assert "因果链追溯失败" in result
        assert "DB 连接失败" in result


# ──────────────────────────────────────────────
# audit_check 测试
# ──────────────────────────────────────────────


class TestAuditCheck:
    """测试公理审计检查端点"""

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_无违规通过(self, mock_store_fn):
        from dimcause.protocols.mcp_server import audit_check

        mock_graph = MagicMock()
        mock_graph.number_of_nodes.return_value = 10
        mock_store = MagicMock()
        mock_store._graph = mock_graph
        mock_store_fn.return_value = mock_store

        with patch("dimcause.protocols.mcp_server.AxiomValidator", create=True):
            # 直接 mock 导入路径
            with patch("dimcause.reasoning.validator.AxiomValidator") as MockVal:
                instance = MockVal.return_value
                instance.validate.return_value = []

                result = audit_check()

                assert "✅" in result
                assert "未发现任何违规项" in result

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_检测到违规(self, mock_store_fn):
        from dimcause.protocols.mcp_server import audit_check

        mock_graph = MagicMock()
        mock_graph.number_of_nodes.return_value = 5
        mock_store = MagicMock()
        mock_store._graph = mock_graph
        mock_store_fn.return_value = mock_store

        violations = [
            FakeValidationResult(
                "commit_must_have_cause", "warning", "Commit abc123 缺少因果关联", "abc123"
            ),
            FakeValidationResult(
                "no_decision_cycle", "error", "检测到 Decision 循环依赖", "dec_001"
            ),
        ]

        with patch("dimcause.reasoning.validator.AxiomValidator") as MockVal:
            instance = MockVal.return_value
            instance.validate.return_value = violations

            result = audit_check()

            assert "2 个违规项" in result
            assert "commit_must_have_cause" in result
            assert "🔴" in result  # error 级别
            assert "🟡" in result  # warning 级别

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_空图提示(self, mock_store_fn):
        from dimcause.protocols.mcp_server import audit_check

        mock_store = MagicMock()
        mock_store._graph = None
        mock_store_fn.return_value = mock_store

        result = audit_check()

        assert "图谱为空" in result


# ──────────────────────────────────────────────
# get_graph_context 测试
# ──────────────────────────────────────────────


class TestGetGraphContext:
    """测试图谱概览端点"""

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_正常返回概览(self, mock_store_fn):
        from dimcause.protocols.mcp_server import get_graph_context

        mock_graph = MagicMock()
        mock_graph.number_of_nodes.return_value = 42
        mock_graph.nodes.return_value = [
            ("n1", {"type": "commit"}),
            ("n2", {"type": "decision"}),
            ("n3", {"type": "commit"}),
        ]
        # mock data=True iteration
        mock_graph.nodes.__call__ = (
            lambda data=False: [
                ("n1", {"type": "commit"}),
                ("n2", {"type": "decision"}),
                ("n3", {"type": "commit"}),
            ]
            if data
            else ["n1", "n2", "n3"]
        )

        mock_store = MagicMock()
        mock_store.stats.return_value = {"nodes": 42, "edges": 15}
        mock_store._graph = mock_graph
        mock_store_fn.return_value = mock_store

        result = get_graph_context()

        assert "因果图谱概览" in result
        assert "42" in result
        assert "15" in result

    @patch("dimcause.protocols.mcp_server._get_graph_store")
    def test_异常处理(self, mock_store_fn):
        from dimcause.protocols.mcp_server import get_graph_context

        mock_store_fn.side_effect = RuntimeError("DB error")

        result = get_graph_context()

        assert "图谱概览获取失败" in result
