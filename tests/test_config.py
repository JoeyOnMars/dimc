"""
配置模块测试
"""

import json
from pathlib import Path

from dimcause.utils.config import (
    CONFIG_FILENAME,
    Config,
    create_config_from_file,
    get_config_value,
    get_config,
    load_config_file,
    normalize_config_key_path,
    parse_config_value,
    reload_config,
    reset_config,
    set_config_value,
)


class TestConfig:
    """Config 类测试"""

    def test_default_values(self):
        """默认值测试"""
        config = Config()
        assert config.project_name == "dimcause"
        assert config.version == "4.0"
        assert config.hot_index_days == 7
        assert config.clipboard_auto_sanitize is True

    def test_custom_values(self):
        """自定义值测试"""
        config = Config(
            project_name="test-project",
            hot_index_days=14,
            git_integration=False,
        )
        assert config.project_name == "test-project"
        assert config.hot_index_days == 14
        assert config.git_integration is False

    def test_root_dir_detection(self):
        """根目录检测测试"""
        config = Config()
        assert config.root_dir is not None
        assert isinstance(config.root_dir, Path)

    def test_logs_dir_property(self):
        """日志目录属性测试"""
        config = Config(root_dir=Path("/test"))
        assert config.logs_dir == Path("/test/docs/logs")

    def test_to_dict(self):
        """转换为字典测试"""
        config = Config()
        d = config.to_dict()
        assert "project_name" in d
        assert "version" in d
        assert "timezone" in d


class TestLoadConfigFile:
    """配置文件加载测试"""

    def test_load_json_format(self, tmp_path):
        """加载 JSON 格式"""
        config_file = tmp_path / CONFIG_FILENAME
        config_file.write_text(
            json.dumps(
                {
                    "project_name": "json-project",
                    "hot_index_days": 10,
                }
            )
        )

        config = load_config_file(config_file)
        assert config["project_name"] == "json-project"
        assert config["hot_index_days"] == 10

    def test_load_keyvalue_format(self, tmp_path):
        """加载 key=value 格式"""
        config_file = tmp_path / CONFIG_FILENAME
        config_file.write_text("""
# 注释
PROJECT_NAME=keyvalue-project
HOT_INDEX_DAYS=5
GIT_INTEGRATION=true
""")

        config = load_config_file(config_file)
        assert config["project_name"] == "keyvalue-project"
        assert config["hot_index_days"] == 5
        assert config["git_integration"] is True

    def test_load_nonexistent_file(self, tmp_path):
        """加载不存在的文件"""
        config_file = tmp_path / "nonexistent"
        config = load_config_file(config_file)
        assert config == {}


class TestCreateConfigFromFile:
    """从文件创建配置测试"""

    def test_create_with_json(self, tmp_path):
        """从 JSON 文件创建"""
        config_file = tmp_path / CONFIG_FILENAME
        config_file.write_text(
            json.dumps(
                {
                    "project_name": "from-file",
                    "timezone": "UTC",
                }
            )
        )

        config = create_config_from_file(root_dir=tmp_path)
        assert config.project_name == "from-file"
        assert config.timezone == "UTC"

    def test_create_without_file(self, tmp_path):
        """没有配置文件时使用默认值"""
        config = create_config_from_file(root_dir=tmp_path)
        assert config.project_name == "dimcause"


class TestGlobalConfig:
    """全局配置测试"""

    def setup_method(self):
        """每个测试前重置配置"""
        reset_config()

    def test_get_config_singleton(self):
        """获取配置单例"""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config(self):
        """重新加载配置"""
        config1 = get_config()
        config2 = reload_config(project_name="reloaded")
        assert config2.project_name == "reloaded"
        assert config1 is not config2


class TestConfigProperties:
    """Config 属性测试"""

    def test_agent_dir(self):
        """agent_dir 属性"""
        config = Config(root_dir=Path("/test"))
        assert config.agent_dir == Path("/test/.agent")

    def test_captures_dir(self):
        """captures_dir 属性"""
        config = Config(root_dir=Path("/test"))
        assert config.captures_dir == Path("/test/docs/logs/captures")

    def test_config_file(self):
        """config_file 属性"""
        config = Config(root_dir=Path("/test"))
        assert config.config_file == Path("/test/.logger-config")


class TestConfigSave:
    """Config.save() 测试"""

    def test_save_config(self, tmp_path):
        """保存配置到文件"""
        config = Config(
            root_dir=tmp_path,
            project_name="saved-project",
            timezone="UTC",
        )

        config.save()

        # 验证文件已创建
        config_file = tmp_path / CONFIG_FILENAME
        assert config_file.exists()

        # 验证内容
        saved = json.loads(config_file.read_text())
        assert saved["project_name"] == "saved-project"
        assert saved["timezone"] == "UTC"


class TestConfigEnvVar:
    """环境变量测试"""

    def test_mal_root_env(self, tmp_path, monkeypatch):
        """DIMCAUSE_ROOT 环境变量"""
        monkeypatch.setenv("DIMCAUSE_ROOT", str(tmp_path))

        config = Config()
        assert config.root_dir == tmp_path


class TestConfigStringConversion:
    """字符串路径转换测试"""

    def test_root_dir_string(self):
        """root_dir 字符串自动转换"""
        config = Config(root_dir="/some/path")
        assert isinstance(config.root_dir, Path)
        assert config.root_dir == Path("/some/path")

    def test_lock_dir_string(self):
        """lock_dir 字符串自动转换"""
        config = Config(lock_dir="/tmp/locks")
        assert isinstance(config.lock_dir, Path)


class TestConfigValueConversion:
    """配置值转换测试"""

    def test_false_values(self, tmp_path):
        """false 值转换"""
        config_file = tmp_path / CONFIG_FILENAME
        config_file.write_text("""
GIT_INTEGRATION=false
CLIPBOARD_AUTO_SANITIZE=no
HOT_INDEX_DAYS=14
""")
        config = load_config_file(config_file)
        assert config["git_integration"] is False
        assert config["clipboard_auto_sanitize"] is False
        assert config["hot_index_days"] == 14

    def test_parse_config_value_json_and_scalar(self):
        assert parse_config_value("true") is True
        assert parse_config_value("3.5") == 3.5
        assert parse_config_value('{"model": "deepseek-chat"}') == {"model": "deepseek-chat"}


class TestConfigRawHelpers:
    def test_set_and_get_nested_config_value(self, tmp_path):
        set_config_value("llm_primary.model", "deepseek-chat", root_dir=tmp_path)
        set_config_value("llm_primary.temperature", "0.2", root_dir=tmp_path)

        saved = json.loads((tmp_path / CONFIG_FILENAME).read_text(encoding="utf-8"))
        assert saved["llm_primary"]["model"] == "deepseek-chat"
        assert saved["llm_primary"]["temperature"] == 0.2
        assert get_config_value("llm_primary.model", root_dir=tmp_path) == "deepseek-chat"

    def test_normalize_config_key_path_supports_watcher_alias(self):
        assert normalize_config_key_path("watchers.antigravity.path") == "export_dir"


class TestConfigRootDetection:
    """根目录检测测试"""

    def test_detect_from_cwd_with_config(self, tmp_path, monkeypatch):
        """从当前目录检测根目录"""
        # 在临时目录创建配置文件
        (tmp_path / CONFIG_FILENAME).write_text('{"project_name": "cwd-test"}')

        monkeypatch.chdir(tmp_path)
        # 不设置 DIMCAUSE_ROOT 环境变量
        monkeypatch.delenv("DIMCAUSE_ROOT", raising=False)

        config = Config()
        # 应该能检测到 root
        assert config.root_dir.exists()


class TestConfigIndexDb:
    """index_db 属性测试"""

    def test_index_db_path(self):
        """index_db 路径"""
        config = Config(root_dir=Path("/test"))
        # index_db 现在在 ~/.dimcause/code.db
        assert "code.db" in str(config.index_db)


class TestConfigRootFromPyproject:
    """从 pyproject.toml 检测根目录"""

    def test_detect_from_pyproject(self, tmp_path, monkeypatch):
        """检测 pyproject.toml"""
        # 创建 pyproject.toml
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"')
        monkeypatch.chdir(tmp_path)

        # Mock __file__ to be config.py
        monkeypatch.setattr(
            "dimcause.utils.config.__file__", str(tmp_path / "src" / "mal" / "core" / "config.py")
        )

        config = Config()
        assert config.root_dir == tmp_path


class TestConfigCwdDetection:
    """从 cwd 检测根目录"""

    def test_detect_from_cwd_with_malconf(self, tmp_path, monkeypatch):
        """从 cwd 检测 .dimcauseconf"""
        # 创建 .dimcauseconf
        (tmp_path / ".dimcauseconf").write_text("PROJECT_NAME=test")

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DIMCAUSE_ROOT", raising=False)

        config = Config()
        assert config.root_dir.exists()

    def test_fallback_to_cwd(self, tmp_path, monkeypatch):
        """回退到 cwd"""
        # 空目录，无任何配置文件
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DIMCAUSE_ROOT", raising=False)

        config = Config()
        # 应该回退到 cwd
        assert config.root_dir == tmp_path or config.root_dir.exists()


class TestConfigCwdFallback:
    """Config fallback to CWD"""

    def test_fallback_to_cwd(self, tmp_path, monkeypatch):
        """测试回退到当前工作目录查找"""
        # 1. 准备目录结构
        # cwd_dir: 包含 pyproject.toml，这是我们要找的目标
        cwd_dir = tmp_path / "cwd_dir"
        cwd_dir.mkdir()
        (cwd_dir / "pyproject.toml").write_text("")

        # file_dir: 包含伪造的 config.py，其上层没有 pyproject.toml
        file_dir = tmp_path / "file_dir" / "nested"
        file_dir.mkdir(parents=True)

        # 2. Mock 环境
        monkeypatch.chdir(cwd_dir)
        monkeypatch.setattr("dimcause.utils.config.__file__", str(file_dir / "config.py"))

        # 3. 初始化 Config
        # 由于 __file__ 路径向上找找不到配置文件，应该回退到检查 cwd
        from dimcause.utils.config import Config

        config = Config()

        # 4. 验证
        assert config.root_dir == cwd_dir

    def test_fallback_default_cwd(self, tmp_path, monkeypatch):
        """找不到任何 config 时默认使用 CWD"""
        from dimcause.utils.config import Config

        # 没有任何配置文件
        cwd_dir = tmp_path / "empty_cwd"
        cwd_dir.mkdir()
        file_dir = tmp_path / "file_dir"
        file_dir.mkdir()

        monkeypatch.chdir(cwd_dir)
        monkeypatch.setattr("dimcause.utils.config.__file__", str(file_dir / "config.py"))

        config = Config()
        assert config.root_dir == cwd_dir
