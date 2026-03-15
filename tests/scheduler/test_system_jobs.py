"""
System Jobs 单元测试

测试 DirectoryImporter 作业的注册和执行：
1. register_importer_job 添加作业到 Orchestrator
2. 作业被触发时能正确调用导入钩子
"""

import os
from unittest.mock import MagicMock, patch

# 设置测试环境变量，防止真实 IO
os.environ["HF_HUB_OFFLINE"] = "1"

from dimcause.scheduler.orchestrator import Orchestrator
from dimcause.scheduler.system_jobs import (
    create_daemon_mode,
    register_importer_job,
)


class TestRegisterImporterJob:
    """测试 register_importer_job 函数"""

    def test_register_importer_job_adds_job(self):
        """测试调用 register_importer_job 后，Orchestrator 中多了一个作业"""
        orch = Orchestrator()

        # 注册作业
        register_importer_job(
            orchestrator=orch,
            target_dir="docs/logs",
            interval=60.0,
        )

        # 验证作业已注册
        assert "directory_importer" in orch._jobs
        assert orch._jobs["directory_importer"].interval == 60.0

    def test_register_importer_job_with_custom_params(self):
        """测试自定义参数"""
        orch = Orchestrator()

        register_importer_job(
            orchestrator=orch,
            target_dir="my/custom/path",
            interval=120.0,
            recursive=False,
            pattern="*.txt",
        )

        job = orch._jobs["directory_importer"]
        assert job.interval == 120.0

    def test_register_multiple_times_uses_same_name(self):
        """测试多次注册使用相同名称（覆盖）"""
        orch = Orchestrator()

        register_importer_job(orch, "dir1", 10.0)
        register_importer_job(orch, "dir2", 20.0)

        # 第二次注册应该覆盖第一次
        assert len(orch._jobs) == 1
        assert orch._jobs["directory_importer"].interval == 20.0


class TestImporterJobExecution:
    """测试导入作业执行"""

    @patch("dimcause.scheduler.system_jobs.DirectoryImporter")
    def test_job_calls_importer(self, mock_importer_class):
        """测试作业被触发时能正确调用 DirectoryImporter"""
        # 设置 mock
        mock_importer = MagicMock()
        mock_importer.import_directory.return_value = 5  # 导入 5 个文件
        mock_importer_class.return_value = mock_importer

        orch = Orchestrator()

        # 注册作业
        register_importer_job(
            orchestrator=orch,
            target_dir="docs/logs",
            interval=0.1,  # 短间隔以便快速测试
        )

        # 手动执行作业函数
        job = orch._jobs["directory_importer"]
        job.func()

        # 验证 DirectoryImporter 被调用
        mock_importer_class.assert_called_once()
        mock_importer.import_directory.assert_called_once_with(
            target_dir="docs/logs",
            recursive=True,
            pattern="*.md",
        )

    @patch("dimcause.scheduler.system_jobs.DirectoryImporter")
    def test_job_exception_isolation(self, mock_importer_class):
        """测试作业异常被正确隔离"""
        mock_importer = MagicMock()
        mock_importer.import_directory.side_effect = RuntimeError("Import failed")
        mock_importer_class.return_value = mock_importer

        orch = Orchestrator()

        register_importer_job(
            orchestrator=orch,
            target_dir="docs/logs",
            interval=0.1,
        )

        job = orch._jobs["directory_importer"]

        # 使用 Orchestrator 的 _execute_job 来执行，以模拟真实行为
        orch._execute_job(job)

        # 验证错误计数增加
        assert job.error_count >= 1


class TestCreateDaemonMode:
    """测试 create_daemon_mode 函数"""

    def test_create_daemon_mode_registers_default_job(self):
        """测试创建守护进程模式时注册默认作业"""
        orch = Orchestrator()

        create_daemon_mode(orch)

        # 验证默认作业已注册
        assert "directory_importer" in orch._jobs

    def test_create_daemon_mode_with_custom_config(self):
        """测试自定义配置"""
        orch = Orchestrator()

        config = {
            "target_dir": "custom/dir",
            "interval": 600,
            "recursive": False,
            "pattern": "*.txt",
        }

        create_daemon_mode(orch, config=config)

        job = orch._jobs["directory_importer"]
        assert job.interval == 600

    def test_create_daemon_mode_overwrites_existing(self):
        """测试自定义配置覆盖默认配置"""
        orch = Orchestrator()

        # 先用默认配置
        create_daemon_mode(orch)

        # 再用自定义配置
        create_daemon_mode(orch, config={"target_dir": "new/dir", "interval": 100})

        # 确认被覆盖
        assert orch._jobs["directory_importer"].interval == 100
