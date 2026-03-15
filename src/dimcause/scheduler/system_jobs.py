"""
System Jobs - 系统级后台任务

负责将 DirectoryImporter 等系统组件包装为 Orchestrator 可调度的作业。
"""

import logging
from pathlib import Path
from typing import Optional

from dimcause.importers.dir_importer import DirectoryImporter
from dimcause.scheduler.orchestrator import Orchestrator

# 配置日志
logger = logging.getLogger(__name__)


def register_importer_job(
    orchestrator: Orchestrator,
    target_dir: str,
    interval: float,
    recursive: bool = True,
    pattern: str = "*.md",
) -> None:
    """
    注册 DirectoryImporter 作业到 Orchestrator

    Args:
        orchestrator: Orchestrator 实例
        target_dir: 要扫描的目标目录
        interval: 执行间隔（秒）
        recursive: 是否递归扫描子目录
        pattern: 文件匹配模式
    """
    job_name = "directory_importer"

    def importer_job():
        """实际的导入作业函数"""
        logger.info(f"[{job_name}] Starting directory import: {target_dir}")
        try:
            # 使用当前目录作为 base_dir
            importer = DirectoryImporter(base_dir=Path("."))

            # 执行导入
            count = importer.import_directory(
                target_dir=target_dir,
                recursive=recursive,
                pattern=pattern,
            )

            logger.info(f"[{job_name}] Imported {count} files from {target_dir}")
        except Exception as e:
            # 错误会被 Orchestrator 的异常隔离器捕获
            # 这里额外记录以便调试
            logger.error(f"[{job_name}] Import failed: {e}")
            raise  # 重新抛出，由 Orchestrator 统一处理

    # 注册作业到 Orchestrator
    orchestrator.register_job(
        job_name=job_name,
        interval=interval,
        func=importer_job,
    )

    logger.info(f"Registered {job_name} job: target={target_dir}, interval={interval}s")


def create_daemon_mode(orchestrator: Orchestrator, config: Optional[dict] = None) -> None:
    """
    创建守护进程模式的默认作业配置

    Args:
        orchestrator: Orchestrator 实例
        config: 可选的配置字典，默认使用内配置
    """
    # 默认配置
    default_config = {
        "target_dir": "docs/logs",  # 默认扫描 docs/logs
        "interval": 300,  # 默认 5 分钟
        "recursive": True,
        "pattern": "*.md",
    }

    cfg = config or default_config

    # 注册导入作业
    register_importer_job(
        orchestrator=orchestrator,
        target_dir=cfg["target_dir"],
        interval=cfg["interval"],
        recursive=cfg.get("recursive", True),
        pattern=cfg.get("pattern", "*.md"),
    )

    logger.info("Daemon mode configured with default settings")
