"""
Tests for ModelConfig and ModelStack (V5.2)

Covers: MODEL_SELECTION_RULES.md compliance
"""

from dimcause.core.models import (
    DEFAULT_MODEL_CACHE_DIR,
    ModelConfig,
    ModelStack,
    get_model_config,
)


class TestModelStack:
    """Test ModelStack enum."""

    def test_enum_values(self):
        """Verify all three modes exist."""
        assert ModelStack.PERFORMANCE == "performance"
        assert ModelStack.TRUST == "trust"
        assert ModelStack.GEEK == "geek"

    def test_enum_is_string(self):
        """ModelStack should be string-compatible."""
        assert isinstance(ModelStack.PERFORMANCE, str)
        assert ModelStack.TRUST.value == "trust"


class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_default_values(self):
        """Default config should use TRUST mode (changed from PERFORMANCE for offline stability)."""
        config = ModelConfig()
        assert config.stack == ModelStack.TRUST
        assert config.cache_dir == DEFAULT_MODEL_CACHE_DIR
        assert config.embed_model is None  # TODO: Will be filled by ModelFactory
        assert config.rerank_model is None
        assert config.expansion_model is None

    def test_custom_stack(self):
        """Should accept custom stack."""
        config = ModelConfig(stack=ModelStack.TRUST)
        assert config.stack == ModelStack.TRUST

        config = ModelConfig(stack=ModelStack.GEEK)
        assert config.stack == ModelStack.GEEK

    def test_embed_dimension_field(self):
        """Should have embed_dimension field."""
        config = ModelConfig(embed_dimension=1024)
        assert config.embed_dimension == 1024


class TestGetModelConfig:
    """Test get_model_config() function."""

    def test_default_returns_trust(self):
        """Default call should return TRUST mode (changed from PERFORMANCE for offline stability)."""
        config = get_model_config()
        assert config.stack == ModelStack.TRUST

    def test_explicit_stack_override(self):
        """Explicit stack parameter should override default."""
        config = get_model_config(stack=ModelStack.TRUST)
        assert config.stack == ModelStack.TRUST

        config = get_model_config(stack=ModelStack.GEEK)
        assert config.stack == ModelStack.GEEK

    def test_env_var_override(self, monkeypatch):
        """DIMCAUSE_MODEL_STACK env var should override default."""
        monkeypatch.setenv("DIMCAUSE_MODEL_STACK", "trust")
        config = get_model_config()
        assert config.stack == ModelStack.TRUST

        monkeypatch.setenv("DIMCAUSE_MODEL_STACK", "geek")
        config = get_model_config()
        assert config.stack == ModelStack.GEEK

    def test_explicit_overrides_env_var(self, monkeypatch):
        """Explicit stack parameter should NOT be overridden by env var."""
        monkeypatch.setenv("DIMCAUSE_MODEL_STACK", "geek")
        # Explicit parameter takes precedence
        config = get_model_config(stack=ModelStack.TRUST)
        assert config.stack == ModelStack.TRUST

    def test_invalid_env_var_ignored(self, monkeypatch):
        """Invalid DIMCAUSE_MODEL_STACK value should be ignored."""
        monkeypatch.setenv("DIMCAUSE_MODEL_STACK", "invalid_mode")
        config = get_model_config()
        # Should fall back to default (TRUST)
        assert config.stack == ModelStack.TRUST
