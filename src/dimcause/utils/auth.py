"""
Dimcause Agent Authentication - Agent认证机制

Critical P1 Implementation: 防止未授权进程写入MAL数据
"""

import json
import logging
import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentToken:
    """Agent认证Token"""

    agent_id: str  # Agent唯一ID
    token: str  # Token字符串
    created_at: float  # 创建时间
    expires_at: Optional[float] = None  # 过期时间(None=永不过期)
    permissions: List[str] = None  # 权限列表
    metadata: Dict[str, str] = None  # 额外信息(如agent_name)

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = ["read", "write"]
        if self.metadata is None:
            self.metadata = {}

    def is_expired(self) -> bool:
        """检查Token是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        return permission in self.permissions


class AgentRegistry:
    """
    Agent注册中心

    职责:
    1. 生成Agent Token
    2. 验证Token有效性
    3. 管理Agent权限
    4. 持久化Token到文件
    """

    DEFAULT_DIR = ".dimcause"
    LEGACY_DIR = ".mal"
    REGISTRY_FILE = "agents.json"

    @classmethod
    def _resolve_default_registry_file(cls) -> Path:
        """解析默认注册文件路径，并在首次启动时迁移 legacy .mal 路径。"""
        home = Path.home()
        default_path = home / cls.DEFAULT_DIR / cls.REGISTRY_FILE
        legacy_path = home / cls.LEGACY_DIR / cls.REGISTRY_FILE

        if default_path.exists() or not legacy_path.exists():
            return default_path

        default_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            legacy_path.replace(default_path)
            logger.info("Agent registry migrated from %s to %s", legacy_path, default_path)
            return default_path
        except OSError as exc:
            logger.warning(
                "Agent registry migration failed, fallback to legacy path %s: %s",
                legacy_path,
                exc,
            )
            return legacy_path

    def __init__(self, registry_file: Optional[str] = None):
        """
        初始化注册中心

        Args:
            registry_file: Token注册文件路径(默认 ~/.dimcause/agents.json)
        """
        if registry_file is None:
            registry_file = str(self._resolve_default_registry_file())

        self.registry_file = Path(registry_file)
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

        self._tokens: Dict[str, AgentToken] = {}  # token -> AgentToken
        self._agent_ids: Dict[str, str] = {}  # agent_id -> token

        # 加载已有tokens
        self._load_registry()

    def _load_registry(self) -> None:
        """从文件加载Token注册表"""
        if not self.registry_file.exists():
            return

        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for token_data in data.get("tokens", []):
                token_obj = AgentToken(**token_data)
                self._tokens[token_obj.token] = token_obj
                self._agent_ids[token_obj.agent_id] = token_obj.token

            logger.info(f"Loaded {len(self._tokens)} agent tokens from registry")

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to load agent registry: {e}")

    def _save_registry(self) -> None:
        """保存Token注册表到文件"""
        data = {
            "tokens": [asdict(token) for token in self._tokens.values()],
            "updated_at": datetime.now().isoformat(),
        }

        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def generate_token(
        self,
        agent_id: str,
        agent_name: Optional[str] = None,
        ttl_hours: Optional[int] = None,
        permissions: Optional[List[str]] = None,
    ) -> str:
        """
        为Agent生成新Token

        Args:
            agent_id: Agent唯一ID
            agent_name: Agent名称(可选)
            ttl_hours: Token有效期(小时),None=永不过期
            permissions: 权限列表(默认 ["read", "write"])

        Returns:
            生成的Token字符串
        """
        # 生成安全的随机token
        token = self._generate_secure_token()

        # 计算过期时间
        expires_at = None
        if ttl_hours is not None:
            expires_at = time.time() + (ttl_hours * 3600)

        # 创建Token对象
        metadata = {}
        if agent_name:
            metadata["agent_name"] = agent_name

        agent_token = AgentToken(
            agent_id=agent_id,
            token=token,
            created_at=time.time(),
            expires_at=expires_at,
            permissions=permissions or ["read", "write"],
            metadata=metadata,
        )

        # 注册
        self._tokens[token] = agent_token
        self._agent_ids[agent_id] = token

        # 持久化
        self._save_registry()

        logger.info(f"Generated token for agent '{agent_id}'")

        return token

    def _generate_secure_token(self) -> str:
        """
        生成安全的随机Token

        格式: mal_<32字节hex> (类似GitHub PAT)
        """
        random_bytes = secrets.token_bytes(32)
        token_hex = random_bytes.hex()
        return f"mal_{token_hex}"

    def verify_token(self, token: str) -> Optional[AgentToken]:
        """
        验证Token

        Args:
            token: 要验证的Token字符串

        Returns:
            如果有效返回AgentToken对象,否则返回None
        """
        if not token:
            return None

        agent_token = self._tokens.get(token)

        if not agent_token:
            logger.warning(f"Unknown token: {token[:20]}...")
            return None

        # 检查是否过期
        if agent_token.is_expired():
            logger.warning(f"Expired token for agent '{agent_token.agent_id}'")
            return None

        return agent_token

    def revoke_token(self, token: str) -> bool:
        """
        撤销Token

        Args:
            token: 要撤销的Token

        Returns:
            成功返回True
        """
        if token not in self._tokens:
            return False

        agent_token = self._tokens[token]
        agent_id = agent_token.agent_id

        # 删除
        del self._tokens[token]
        if agent_id in self._agent_ids:
            del self._agent_ids[agent_id]

        # 持久化
        self._save_registry()

        logger.info(f"Revoked token for agent '{agent_id}'")

        return True

    def revoke_agent(self, agent_id: str) -> bool:
        """
        撤销Agent的所有Token

        Args:
            agent_id: Agent ID

        Returns:
            成功返回True
        """
        token = self._agent_ids.get(agent_id)
        if not token:
            return False

        return self.revoke_token(token)

    def list_agents(self) -> List[AgentToken]:
        """列出所有注册的Agent"""
        return list(self._tokens.values())

    def cleanup_expired(self) -> int:
        """
        清理过期Token

        Returns:
            清理的数量
        """
        expired_tokens = [
            token for token, agent_token in self._tokens.items() if agent_token.is_expired()
        ]

        for token in expired_tokens:
            self.revoke_token(token)

        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")

        return len(expired_tokens)

    def get_token_info(self, token: str) -> Optional[Dict]:
        """
        获取Token信息(不泄露敏感数据)

        Args:
            token: Token字符串

        Returns:
            Token信息字典
        """
        agent_token = self._tokens.get(token)
        if not agent_token:
            return None

        return {
            "agent_id": agent_token.agent_id,
            "agent_name": agent_token.metadata.get("agent_name", "unknown"),
            "created_at": datetime.fromtimestamp(agent_token.created_at).isoformat(),
            "expires_at": datetime.fromtimestamp(agent_token.expires_at).isoformat()
            if agent_token.expires_at
            else "never",
            "permissions": agent_token.permissions,
            "is_expired": agent_token.is_expired(),
        }


class AuthMiddleware:
    """
    认证中间件

    在daemon的on_new_data中使用,验证来源Agent
    """

    def __init__(self, registry: AgentRegistry, strict_mode: bool = False):
        """
        初始化中间件

        Args:
            registry: Agent注册中心
            strict_mode: 严格模式(True=必须验证,False=验证失败仍允许)
        """
        self.registry = registry
        self.strict_mode = strict_mode

    def authenticate(self, token: Optional[str], required_permission: str = "write") -> bool:
        """
        验证请求

        Args:
            token: Agent提供的Token
            required_permission: 需要的权限

        Returns:
            通过返回True
        """
        if not token:
            if self.strict_mode:
                logger.error("Authentication required but no token provided")
                return False
            else:
                logger.warning("No token provided, allowing in non-strict mode")
                return True

        agent_token = self.registry.verify_token(token)

        if not agent_token:
            if self.strict_mode:
                logger.error("Invalid or expired token")
                return False
            else:
                logger.warning("Invalid token, allowing in non-strict mode")
                return True

        # 检查权限
        if not agent_token.has_permission(required_permission):
            logger.error(f"Agent '{agent_token.agent_id}' lacks permission: {required_permission}")
            return False

        logger.debug(f"Authenticated agent: {agent_token.agent_id}")
        return True


# 全局单例
_registry_instance = None


def get_registry(registry_file: Optional[str] = None) -> AgentRegistry:
    """获取全局Agent注册中心(单例)"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry(registry_file)
    return _registry_instance


# CLI辅助函数
def create_agent_token(
    agent_id: str, agent_name: Optional[str] = None, ttl_hours: Optional[int] = None
) -> str:
    """CLI便捷函数:创建Agent Token"""
    registry = get_registry()
    return registry.generate_token(agent_id, agent_name, ttl_hours)


def verify_agent_token(token: str) -> bool:
    """CLI便捷函数:验证Token"""
    registry = get_registry()
    return registry.verify_token(token) is not None
