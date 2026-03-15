"""
统一配置模块

功能:
1. 从 .logger-config 文件加载配置
2. 支持 JSON 和 key=value 格式
3. 环境变量覆盖
4. 默认值回退
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

# 配置文件名
CONFIG_FILENAME = ".logger-config"
CONFIG_KEY_ALIASES = {
    "watchers.antigravity.path": "export_dir",
    "watchers.cursor.path": "watcher_cursor.path",
    "watchers.claude.path": "watcher_claude.path",
    "watchers.windsurf.path": "watcher_windsurf.path",
    "watchers.continue_dev.path": "watcher_continue_dev.path",
    "watchers.continue.path": "watcher_continue_dev.path",
}


@dataclass
class Config:
    """Dimcause 配置"""

    # 项目信息
    project_name: str = "dimcause"
    version: str = "4.0"

    # 时区
    timezone: str = field(default_factory=lambda: os.environ.get("DIMCAUSE_TZ", "Asia/Shanghai"))

    # 语言 (用于 LLM 输出等)
    language: str = "en"

    # Agent Identity (RFC-002)
    agent_id: str = field(default_factory=lambda: os.environ.get("DIMC_AGENT_ID", "user"))

    # AI 对话导出目录
    export_dir: str = field(
        default_factory=lambda: os.environ.get("DIMCAUSE_EXPORT_DIR", "~/Documents/AG_Exports")
    )

    # 目录配置
    root_dir: Optional[Path] = None  # 自动检测
    logs_dir_name: str = "docs/logs"  # 相对于 root_dir
    lock_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("DIMCAUSE_LOCK_DIR", "/tmp/dimcause-locks"))
    )

    # 自动探测的 Brain 目录
    brain_dir: Optional[Path] = None

    # 外部数据源 (Configurable via external_sources)
    external_sources: List[Path] = field(default_factory=list)

    # Claude Code 项目会话目录 (auto-detected)
    claude_code_sessions_dir: Optional[Path] = None

    # 索引配置
    hot_index_days: int = 7  # 热索引保留天数
    orphan_check_days: int = 7  # orphan job 检测天数

    # 锁配置
    lock_timeout: int = 10  # 锁超时时间 (秒)
    lock_retry_base: float = 0.1  # 锁重试基础时间 (秒)
    lock_max_retries: int = 50  # 最大重试次数

    # 剪贴板监控
    clipboard_interval: float = 2.0  # 检查间隔
    clipboard_min_length: int = 50  # 最小内容长度
    clipboard_auto_sanitize: bool = True  # 自动脱敏

    # Git 集成
    git_integration: bool = True
    git_auto_commit: bool = False

    # 安全
    stale_lock_max_age: int = 3600  # 过期锁最大年龄 (秒)

    def __post_init__(self):
        if self.root_dir is None:
            self.root_dir = self._detect_root_dir()

        # 确保是 Path 对象
        if isinstance(self.root_dir, str):
            self.root_dir = Path(self.root_dir)
        if isinstance(self.lock_dir, str):
            self.lock_dir = Path(self.lock_dir)

        if self.brain_dir is None:
            self.brain_dir = self._detect_brain_dir()

        if self.claude_code_sessions_dir is None:
            self.claude_code_sessions_dir = self._detect_claude_sessions_dir()

    def _detect_claude_sessions_dir(self) -> Optional[Path]:
        """Auto-detect Claude Code sessions directory for current project."""
        # Check environment variable override
        env_override = os.environ.get("DIMCAUSE_CLAUDE_SESSIONS_DIR")
        if env_override:
            p = Path(env_override)
            return p if p.exists() else None

        if self.root_dir is None:
            return None

        # Auto-detect: ~/.claude/projects/{project-slug}/
        from dimcause.extractors.claude_code_parser import find_claude_sessions_dir

        return find_claude_sessions_dir(self.root_dir)

    def _detect_root_dir(self) -> Path:
        """检测项目根目录"""
        # 优先使用环境变量
        env_root = os.environ.get("DIMCAUSE_ROOT")
        if env_root:
            return Path(env_root)

        # 优先从当前工作目录向上查找：CLI 运行时应绑定用户当前项目，而不是 dimcause 包仓库。
        cwd = Path.cwd()
        for _ in range(5):
            if (cwd / CONFIG_FILENAME).exists():
                return cwd
            if (cwd / "pyproject.toml").exists():
                return cwd
            cwd = cwd.parent

        # 作为最后兜底，再从当前文件向上查找（当作为包安装时）
        current = Path(__file__).parent
        for _ in range(5):
            if (current / "pyproject.toml").exists():
                return current
            if (current / CONFIG_FILENAME).exists():
                return current
            current = current.parent

        # 默认使用当前工作目录
        return Path.cwd()

    def _detect_brain_dir(self) -> Optional[Path]:
        """探测当前活跃的 Brain 目录"""
        # 优先使用环境变量
        env_brain = os.environ.get("DIMCAUSE_BRAIN_DIR")
        if env_brain:
            return Path(env_brain)

        # 默认搜索路径
        candidates = [
            Path.home() / ".gemini/antigravity/brain",
            self.root_dir / ".agent/brain" if self.root_dir else None,
        ]

        best_candidate = None
        latest_mtime = 0

        for base in candidates:
            if not base or not base.exists():
                continue

            for d in base.iterdir():
                if d.is_dir() and d.name != ".system_generated" and not d.name.startswith("temp"):
                    # 必须包含 task.md 或 implementation_plan.md 才是有效 Session
                    if not (d / "task.md").exists() and not (d / "implementation_plan.md").exists():
                        continue

                    if d.stat().st_mtime > latest_mtime:
                        latest_mtime = d.stat().st_mtime
                        best_candidate = d

        return best_candidate

    @property
    def logs_dir(self) -> Path:
        return self.root_dir / self.logs_dir_name

    @property
    def agent_dir(self) -> Path:
        return self.root_dir / ".agent"

    @property
    def raw_dir(self) -> Path:
        return self.logs_dir / "raw"

    @property
    def captures_dir(self) -> Path:
        return self.logs_dir / "captures"

    @property
    def export_path(self) -> Path:
        """导出目录的完整路径 (展开 ~)"""
        return Path(self.export_dir).expanduser()

    @property
    def index_db(self) -> Path:
        # Architecture Fix: Separate CodeIndex from logs
        return Path.home() / ".dimcause" / "code.db"

    @property
    def data_dir(self) -> Path:
        """数据目录 (~/.dimcause)"""
        return Path.home() / ".dimcause"

    @property
    def config_file(self) -> Path:
        return self.root_dir / CONFIG_FILENAME

    def to_dict(self) -> dict:
        """转换为字典 (用于保存)"""
        return {
            "project_name": self.project_name,
            "version": self.version,
            "timezone": self.timezone,
            "logs_dir": self.logs_dir_name,
            "git_integration": self.git_integration,
            "git_auto_commit": self.git_auto_commit,
            "clipboard_capture": self.clipboard_auto_sanitize,
            "hot_index_days": self.hot_index_days,
            "agent_id": self.agent_id,
            "export_dir": self.export_dir,
            "brain_dir": str(self.brain_dir) if self.brain_dir else None,
            "external_sources": [str(p) for p in self.external_sources],
        }

    def save(self) -> Path:
        """保存配置到文件"""
        config_file = self.config_file
        config_file.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return config_file


def load_config_file(config_path: Path) -> dict:
    """
    加载配置文件

    支持两种格式:
    1. JSON: {"key": "value", ...}
    2. Key=Value: KEY=value (每行一个)
    """
    if not config_path.exists():
        return {}

    content = config_path.read_text(encoding="utf-8").strip()

    # 尝试 JSON 格式
    if content.startswith("{"):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # 尝试 key=value 格式
    config = {}
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip().lower().replace("-", "_")
            value = value.strip().strip('"').strip("'")

            # 转换特殊值
            if value.lower() in ("true", "yes", "1"):
                value = True
            elif value.lower() in ("false", "no", "0"):
                value = False
            elif value.isdigit():
                value = int(value)

            config[key] = value

            # 特殊处理 external_sources (逗号分隔列表)
            if key == "external_sources" and isinstance(value, str):
                paths = [Path(p.strip()) for p in value.split(",") if p.strip()]
                config[key] = paths

    return config


def create_config_from_file(root_dir: Optional[Path] = None) -> Config:
    """从配置文件创建 Config 实例"""
    # 先创建默认配置获取 root_dir
    temp_config = Config(root_dir=root_dir)
    config_path = temp_config.config_file

    # 加载配置文件
    file_config = load_config_file(config_path)

    # 映射配置文件字段到 Config 字段
    field_mapping = {
        "logs_dir": "logs_dir_name",
        "clipboard_capture": "clipboard_auto_sanitize",
    }

    # 构建配置参数
    kwargs = {"root_dir": temp_config.root_dir}
    valid_fields = set(Config.__dataclass_fields__.keys())

    for key, value in file_config.items():
        # 应用字段映射
        mapped_key = field_mapping.get(key, key)

        # 处理 Watcher 嵌套配置
        if key.startswith("watcher_"):
            # watcher_claude.enabled = true
            # watcher_claude.path = /xxx
            parts = key.split(".")
            if len(parts) == 2:
                watcher_name, field_name = parts
                if watcher_name not in kwargs:
                    # 如果还没有初始化，创建一个默认的（或者根据需要）
                    # 这里稍微复杂，因为 BaseConfig 的字段是 WatcherConfig 对象
                    # 我们先存字典，最后通过 Pydantic 自动转换
                    kwargs[watcher_name] = {}

                # 处理布尔值和数字
                if field_name == "enabled":
                    if isinstance(value, str):
                        value = value.lower() in ("true", "yes", "1")
                elif field_name == "debounce_seconds":
                    value = float(value)

                kwargs[watcher_name][field_name] = value
            continue

            continue

        if mapped_key in valid_fields:
            kwargs[mapped_key] = value

    return Config(**kwargs)


# 全局单例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = create_config_from_file()
    return _config


def reload_config(**kwargs) -> Config:
    """重新加载配置 (用于测试或覆盖)"""
    global _config
    if kwargs:
        _config = Config(**kwargs)
    else:
        _config = create_config_from_file()
    return _config


def reset_config():
    """重置配置 (用于测试)"""
    global _config
    _config = None


def update_config_file(updates: dict, root_dir: Optional[Path] = None) -> Path:
    """Merge updates into the project config file and persist them as JSON."""
    config_path = _resolve_config_path(root_dir=root_dir)
    current = load_config_file(config_path)
    current.update(updates)
    config_path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    reset_config()
    return config_path


def _resolve_config_path(root_dir: Optional[Path] = None) -> Path:
    return Config(root_dir=root_dir).config_file


def load_project_config(root_dir: Optional[Path] = None) -> dict:
    """读取项目原始配置字典（保留未知键），供新功能按需消费。"""
    return load_config_file(_resolve_config_path(root_dir=root_dir))


def normalize_config_key_path(key_path: str) -> str:
    normalized = key_path.strip().lower().replace("-", "_")
    return CONFIG_KEY_ALIASES.get(normalized, normalized)


def parse_config_value(raw_value: str) -> Any:
    value = raw_value.strip()
    lower = value.lower()

    if lower in ("true", "yes", "1"):
        return True
    if lower in ("false", "no", "0"):
        return False
    if lower in ("null", "none"):
        return None

    if value.startswith("{") or value.startswith("[") or value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def set_config_value(key_path: str, raw_value: str, root_dir: Optional[Path] = None) -> Path:
    """按点路径更新项目配置，例如 llm_primary.model 或 watcher_cursor.path。"""
    normalized_key = normalize_config_key_path(key_path)
    parsed_value = parse_config_value(raw_value)
    config_path = _resolve_config_path(root_dir=root_dir)
    current = load_config_file(config_path)

    if "." not in normalized_key:
        current[normalized_key] = parsed_value
    else:
        parts = normalized_key.split(".")
        node = current
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = parsed_value

    config_path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    reset_config()
    return config_path


def get_config_value(key_path: str, root_dir: Optional[Path] = None, default: Any = None) -> Any:
    """从原始项目配置中读取点路径值。"""
    normalized_key = normalize_config_key_path(key_path)
    current = load_project_config(root_dir=root_dir)

    if "." not in normalized_key:
        return current.get(normalized_key, default)

    node: Any = current
    for part in normalized_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def create_default_config(
    target_dir: Path,
    project_name: str,
    timezone: str = "Asia/Shanghai",
    logs_dir: str = "docs/logs",
    git_integration: bool = True,
    auto_commit: bool = False,
) -> Path:
    """创建默认配置文件"""
    config_data = {
        "project_name": project_name,
        "version": "5.2",
        "timezone": timezone,
        "logs_dir": logs_dir,
        "git_integration": git_integration,
        "git_auto_commit": auto_commit,
        "hot_index_days": 7,
        "clipboard_capture": True,
    }

    config_path = target_dir / CONFIG_FILENAME

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

    return config_path
