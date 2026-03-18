"""
Tests for Agent Authentication - Agent认证测试

验证Token生成、验证、权限控制
"""

import tempfile
import time
from pathlib import Path

import pytest

from dimcause.utils.auth import (
    AgentRegistry,
    AuthMiddleware,
    create_agent_token,
    verify_agent_token,
)


class TestAgentRegistry:
    """测试Agent注册中心"""

    @pytest.fixture
    def temp_registry_file(self):
        """临时注册文件"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            registry_path = f.name
        yield registry_path
        Path(registry_path).unlink(missing_ok=True)

    def test_generate_token(self, temp_registry_file):
        """测试Token生成"""
        registry = AgentRegistry(temp_registry_file)

        token = registry.generate_token(agent_id="test_agent_001", agent_name="Test Agent")

        assert token.startswith("dimc_")
        assert len(token) == 69  # dimc_ + 64 hex chars

    def test_verify_valid_token(self, temp_registry_file):
        """测试验证有效Token"""
        registry = AgentRegistry(temp_registry_file)

        token = registry.generate_token("agent_001")

        agent_token = registry.verify_token(token)

        assert agent_token is not None
        assert agent_token.agent_id == "agent_001"
        assert not agent_token.is_expired()

    def test_verify_invalid_token(self, temp_registry_file):
        """测试验证无效Token"""
        registry = AgentRegistry(temp_registry_file)

        invalid_token = "dimc_invalidtoken123456"
        agent_token = registry.verify_token(invalid_token)

        assert agent_token is None

    def test_token_expiration(self, temp_registry_file):
        """测试Token过期"""
        registry = AgentRegistry(temp_registry_file)

        # 生成1秒后过期的Token
        token = registry.generate_token(
            agent_id="short_lived_agent",
            ttl_hours=1 / 3600,  # 1秒
        )

        # 立即验证,应该有效
        agent_token = registry.verify_token(token)
        assert agent_token is not None

        # 等待2秒
        time.sleep(2)

        # 再次验证,应该过期
        agent_token_expired = registry.verify_token(token)
        assert agent_token_expired is None

    def test_token_permissions(self, temp_registry_file):
        """测试Token权限"""
        registry = AgentRegistry(temp_registry_file)

        # 生成只读Token
        token = registry.generate_token(agent_id="readonly_agent", permissions=["read"])

        agent_token = registry.verify_token(token)

        assert agent_token.has_permission("read")
        assert not agent_token.has_permission("write")

    def test_revoke_token(self, temp_registry_file):
        """测试撤销Token"""
        registry = AgentRegistry(temp_registry_file)

        token = registry.generate_token("agent_to_revoke")

        # 撤销前可以验证
        assert registry.verify_token(token) is not None

        # 撤销
        success = registry.revoke_token(token)
        assert success

        # 撤销后验证失败
        assert registry.verify_token(token) is None

    def test_revoke_agent(self, temp_registry_file):
        """测试撤销Agent的所有Token"""
        registry = AgentRegistry(temp_registry_file)

        agent_id = "agent_multi_token"
        token = registry.generate_token(agent_id)

        # 撤销agent
        success = registry.revoke_agent(agent_id)
        assert success

        # Token应该失效
        assert registry.verify_token(token) is None

    def test_persistence(self, temp_registry_file):
        """测试Token持久化"""
        # 第一个registry实例
        registry1 = AgentRegistry(temp_registry_file)
        token = registry1.generate_token("persistent_agent")

        # 第二个registry实例(重新加载)
        registry2 = AgentRegistry(temp_registry_file)

        # 应该能验证之前生成的token
        agent_token = registry2.verify_token(token)
        assert agent_token is not None
        assert agent_token.agent_id == "persistent_agent"

    def test_list_agents(self, temp_registry_file):
        """测试列出所有Agent"""
        registry = AgentRegistry(temp_registry_file)

        registry.generate_token("agent_001")
        registry.generate_token("agent_002")
        registry.generate_token("agent_003")

        agents = registry.list_agents()

        assert len(agents) == 3
        agent_ids = {a.agent_id for a in agents}
        assert "agent_001" in agent_ids
        assert "agent_002" in agent_ids

    def test_cleanup_expired(self, temp_registry_file):
        """测试清理过期Token"""
        registry = AgentRegistry(temp_registry_file)

        # 生成正常Token和短期Token
        registry.generate_token("normal_agent")
        registry.generate_token("short_agent", ttl_hours=1 / 3600)

        # 等待过期
        time.sleep(2)

        # 清理
        cleaned = registry.cleanup_expired()

        assert cleaned == 1

        # 验证只剩1个
        agents = registry.list_agents()
        assert len(agents) == 1
        assert agents[0].agent_id == "normal_agent"

    def test_get_token_info(self, temp_registry_file):
        """测试获取Token信息"""
        registry = AgentRegistry(temp_registry_file)

        token = registry.generate_token(agent_id="info_agent", agent_name="Information Agent")

        info = registry.get_token_info(token)

        assert info is not None
        assert info["agent_id"] == "info_agent"
        assert info["agent_name"] == "Information Agent"
        assert "created_at" in info
        assert "permissions" in info

    def test_default_registry_path_uses_dimcause(self, tmp_path, monkeypatch):
        """默认注册文件路径应为 ~/.dimcause/agents.json"""
        monkeypatch.setenv("HOME", str(tmp_path))

        registry = AgentRegistry()
        expected = tmp_path / ".dimcause" / "agents.json"

        assert registry.registry_file == expected
        assert expected.parent.exists()

    def test_default_registry_ignores_legacy_oldbrand_dir(self, tmp_path, monkeypatch):
        """存在 legacy 目录下 agents.json 时，默认路径仍应保持 ~/.dimcause/agents.json。"""
        monkeypatch.setenv("HOME", str(tmp_path))

        legacy = tmp_path / ".legacy_dimcause" / "agents.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy_content = '{"tokens": [], "updated_at": "2026-01-01T00:00:00"}'
        legacy.write_text(legacy_content, encoding="utf-8")

        registry = AgentRegistry()
        expected = tmp_path / ".dimcause" / "agents.json"

        assert registry.registry_file == expected
        assert expected.parent.exists()
        assert not expected.exists()
        assert legacy.exists()


class TestAuthMiddleware:
    """测试认证中间件"""

    @pytest.fixture
    def registry(self):
        """测试用registry"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            registry_path = f.name

        registry = AgentRegistry(registry_path)
        yield registry

        Path(registry_path).unlink(missing_ok=True)

    def test_authenticate_with_valid_token(self, registry):
        """测试有效Token认证"""
        middleware = AuthMiddleware(registry, strict_mode=True)

        token = registry.generate_token("valid_agent")

        result = middleware.authenticate(token, required_permission="write")

        assert result is True

    def test_authenticate_with_invalid_token_strict(self, registry):
        """测试无效Token认证(严格模式)"""
        middleware = AuthMiddleware(registry, strict_mode=True)

        result = middleware.authenticate("invalid_token", required_permission="write")

        assert result is False

    def test_authenticate_with_invalid_token_non_strict(self, registry):
        """测试无效Token认证(非严格模式)"""
        middleware = AuthMiddleware(registry, strict_mode=False)

        result = middleware.authenticate("invalid_token", required_permission="write")

        # 非严格模式允许通过
        assert result is True

    def test_authenticate_no_token_strict(self, registry):
        """测试无Token(严格模式)"""
        middleware = AuthMiddleware(registry, strict_mode=True)

        result = middleware.authenticate(None, required_permission="write")

        assert result is False

    def test_authenticate_insufficient_permission(self, registry):
        """测试权限不足"""
        middleware = AuthMiddleware(registry, strict_mode=True)

        token = registry.generate_token("readonly_agent", permissions=["read"])

        result = middleware.authenticate(token, required_permission="write")

        assert result is False


class TestConvenienceFunctions:
    """测试便捷函数（使用 monkeypatch 隔离，避免污染宿主机 ~/.dimcause/）"""

    @pytest.fixture(autouse=True)
    def isolate_registry(self, tmp_path, monkeypatch):
        """将全局 _registry_instance 重定向到 tmp_path，防止越权写入 ~/.dimcause/"""
        import dimcause.utils.auth as auth_module

        # 重置全局单例
        monkeypatch.setattr(auth_module, "_registry_instance", None)
        # 将默认注册文件路径重定向到 tmp_path
        registry_file = str(tmp_path / "agents.json")
        monkeypatch.setattr(
            auth_module, "get_registry",
            lambda registry_file_arg=None: auth_module.AgentRegistry(
                registry_file_arg or registry_file
            ),
        )

    def test_create_agent_token(self):
        """测试创建Token便捷函数"""
        token = create_agent_token("cli_agent", agent_name="CLI Agent")

        assert token.startswith("dimc_")

    def test_verify_agent_token(self):
        """测试验证Token便捷函数"""
        token = create_agent_token("verify_test_agent")

        is_valid = verify_agent_token(token)

        assert is_valid is True

        # 无效token
        is_invalid = verify_agent_token("dimc_invalidtoken")
        assert is_invalid is False


def test_real_world_daemon_integration():
    """测试真实daemon集成场景"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        registry_path = f.name

    try:
        registry = AgentRegistry(registry_path)
        middleware = AuthMiddleware(registry, strict_mode=False)

        # 场景1: Claude Code Agent注册
        claude_token = registry.generate_token(
            agent_id="claude_code_watcher",
            agent_name="Claude Code Watcher",
            permissions=["read", "write"],
        )

        # 场景2: Cursor Agent注册
        registry.generate_token(agent_id="cursor_watcher", agent_name="Cursor Watcher")

        # 场景3: 未授权Agent尝试写入
        unauthorized_result = middleware.authenticate(
            "unauthorized_token", required_permission="write"
        )
        # 非严格模式允许
        assert unauthorized_result is True

        # 场景4: 授权Agent写入
        authorized_result = middleware.authenticate(claude_token, required_permission="write")
        assert authorized_result is True

        # 场景5: 撤销Claude Agent
        registry.revoke_agent("claude_code_watcher")

        revoked_result = middleware.authenticate(claude_token, required_permission="write")
        # Token已失效,非严格模式仍允许
        assert revoked_result is True

        # 场景6: 严格模式下,应该拒绝
        strict_middleware = AuthMiddleware(registry, strict_mode=True)
        strict_result = strict_middleware.authenticate(claude_token, required_permission="write")
        assert strict_result is False

    finally:
        Path(registry_path).unlink(missing_ok=True)
