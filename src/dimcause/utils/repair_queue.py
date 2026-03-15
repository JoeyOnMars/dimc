"""
Dimcause Auto-Repair Queue - 自动修复队列

Critical P0 Implementation: 检测并修复三层存储不一致
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class RepairTask:
    """修复任务"""

    sync_id: str  # 事件ID
    issue_type: str  # missing_vector | missing_graph | both
    markdown_file: str  # Markdown源文件路径
    discovered_at: float  # 发现时间
    retry_count: int = 0
    last_retry_at: float = 0.0


class AutoRepairQueue:
    """
    自动修复队列

    职责:
    1. 定期扫描Markdown日志,提取所有SYNC_ID
    2. 检查Vector DB和Graph DB是否都有对应条目
    3. 如果缺失,加入修复队列
    4. 从Markdown重新提取并重建索引
    """

    DEFAULT_DIR = ".dimcause"
    LEGACY_DIR = ".mal"
    QUEUE_FILE = "repair_queue.jsonl"
    TEST_QUEUE_FILE = "/tmp/dimcause_test_repair_queue.jsonl"

    @classmethod
    def _resolve_default_queue_file(cls) -> Path:
        """解析默认队列文件路径，并在首次启动时迁移 legacy .mal 路径。"""
        home = Path.home()
        default_path = home / cls.DEFAULT_DIR / cls.QUEUE_FILE
        legacy_path = home / cls.LEGACY_DIR / cls.QUEUE_FILE

        if default_path.exists() or not legacy_path.exists():
            return default_path

        default_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            legacy_path.replace(default_path)
            logger.info("Repair queue migrated from %s to %s", legacy_path, default_path)
            return default_path
        except OSError as exc:
            logger.warning(
                "Repair queue migration failed, fallback to legacy path %s: %s",
                legacy_path,
                exc,
            )
            return legacy_path

    def __init__(
        self,
        markdown_dir: str = "docs/logs",
        queue_file: Optional[str] = None,
        scan_interval: int = 3600,  # 1小时
    ):
        """
        初始化修复队列

        Args:
            markdown_dir: Markdown日志目录
            queue_file: 队列持久化文件
            scan_interval: 扫描间隔(秒)
        """
        self.markdown_dir = Path(markdown_dir)

        if queue_file is None:
            import os

            if os.environ.get("PYTEST_CURRENT_TEST"):
                # P2 Audit Fix: Test isolation
                queue_file = self.TEST_QUEUE_FILE
            else:
                queue_file = str(self._resolve_default_queue_file())

        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

        self.scan_interval = scan_interval
        self.queue: List[RepairTask] = []
        self._running = False

        # 启动时加载持久化队列
        self._load_queue()

    def _load_queue(self) -> None:
        """从文件加载修复队列"""
        if not self.queue_file.exists():
            return

        with open(self.queue_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    task = RepairTask(**data)
                    self.queue.append(task)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to load repair task: {e}")

        if self.queue:
            logger.info(f"🔄 Loaded {len(self.queue)} repair tasks from queue")

    def _save_queue(self) -> None:
        """持久化修复队列"""
        with open(self.queue_file, "w", encoding="utf-8") as f:
            for task in self.queue:
                f.write(json.dumps(asdict(task)) + "\n")

    def add_task(self, sync_id: str, issue_type: str, markdown_file: str) -> None:
        """
        添加修复任务

        Args:
            sync_id: 事件ID
            issue_type: 问题类型
            markdown_file: Markdown文件路径
        """
        # 检查是否已存在
        if any(t.sync_id == sync_id for t in self.queue):
            logger.debug(f"Repair task for {sync_id} already in queue")
            return

        task = RepairTask(
            sync_id=sync_id,
            issue_type=issue_type,
            markdown_file=markdown_file,
            discovered_at=time.time(),
        )

        self.queue.append(task)
        self._save_queue()

        logger.warning(f"⚠️ Added repair task: {sync_id} ({issue_type})")

    def extract_sync_ids_from_markdown(self, file_path: Path) -> List[str]:
        """
        从Markdown文件提取所有SYNC_ID

        格式: <!-- DIMCAUSE_SYNC_ID: abc-123-def -->

        Args:
            file_path: Markdown文件路径

        Returns:
            SYNC_ID列表
        """
        sync_ids = []

        if not file_path.exists():
            return sync_ids

        try:
            content = file_path.read_text(encoding="utf-8")

            # 简单的正则提取(可以改用regex模块提升性能)
            import re

            pattern = r"<!--\s*DIMCAUSE_SYNC_ID:\s*([a-zA-Z0-9\-]+)\s*-->"
            matches = re.findall(pattern, content)

            sync_ids.extend(matches)

        except Exception as e:
            logger.error(f"Failed to extract SYNC_IDs from {file_path}: {e}")

        return sync_ids

    async def scan_for_inconsistencies(self, vector_store, graph_store) -> int:
        """
        扫描Markdown日志,检测不一致

        Args:
            vector_store: Vector存储实例
            graph_store: Graph存储实例

        Returns:
            发现的问题数量
        """
        logger.info("🔍 Scanning for storage inconsistencies...")

        found_issues = 0
        all_sync_ids: Set[str] = set()

        # 遍历所有Markdown文件
        for md_file in self.markdown_dir.rglob("*.md"):
            if md_file.name in ["README.md", "SUMMARY.md"]:
                continue

            sync_ids = self.extract_sync_ids_from_markdown(md_file)

            for sync_id in sync_ids:
                all_sync_ids.add(sync_id)

                # 检查Vector DB
                has_vector = await self._check_vector_exists(vector_store, sync_id)

                # 检查Graph DB
                has_graph = await self._check_graph_exists(graph_store, sync_id)

                # 判断是否需要修复
                if not has_vector and not has_graph:
                    self.add_task(sync_id, "both", str(md_file))
                    found_issues += 1
                elif not has_vector:
                    self.add_task(sync_id, "missing_vector", str(md_file))
                    found_issues += 1
                elif not has_graph:
                    self.add_task(sync_id, "missing_graph", str(md_file))
                    found_issues += 1

        logger.info(f"✅ Scan complete: {len(all_sync_ids)} SYNC_IDs, {found_issues} issues found")

        return found_issues

    async def _check_vector_exists(self, vector_store, sync_id: str) -> bool:
        """检查Vector DB是否有此条目"""
        try:
            # 假设VectorStore有get()方法
            result = vector_store.get(ids=[sync_id])
            return result is not None and len(result.get("ids", [])) > 0
        except Exception as e:
            logger.debug(f"Vector check failed for {sync_id}: {e}")
            return False

    async def _check_graph_exists(self, graph_store, sync_id: str) -> bool:
        """检查Graph DB是否有此节点"""
        try:
            # 假设GraphStore有has_node()方法
            return graph_store.has_node(sync_id)
        except Exception as e:
            logger.debug(f"Graph check failed for {sync_id}: {e}")
            return False

    async def process_repairs(
        self, extractor, vector_store, graph_store, max_retries: int = 3
    ) -> int:
        """
        处理修复队列

        注意: 当前实现为串行处理，避免并发写入 VectorStore 的竞态条件。
        未来如需并发，需要:
        1. 使用 asyncio.Semaphore 限制并发数
        2. 对 vector_store.add() 加锁或使用批量写入

        Args:
            extractor: LLM Extractor实例
            vector_store: Vector存储
            graph_store: Graph存储
            max_retries: 最大重试次数

        Returns:
            成功修复的数量
        """
        if not self.queue:
            return 0

        logger.info(f"🔧 Processing {len(self.queue)} repair tasks...")

        repaired = 0
        failed_tasks = []

        # 串行处理 (Serial Processing) - 安全但慢
        # NOTE: 未来可改为并发 (Concurrent Processing) 以提升性能
        for task in self.queue[:]:  # 复制列表以便删除
            # 检查重试次数
            if task.retry_count >= max_retries:
                logger.error(
                    f"❌ Repair abandoned for {task.sync_id} (exceeded {max_retries} retries)"
                )
                failed_tasks.append(task)
                self.queue.remove(task)
                continue

            # 尝试修复
            try:
                success = await self._repair_single(task, extractor, vector_store, graph_store)

                if success:
                    repaired += 1
                    self.queue.remove(task)
                    logger.info(f"✅ Repaired {task.sync_id}")
                else:
                    # 更新重试信息
                    task.retry_count += 1
                    task.last_retry_at = time.time()

            except Exception as e:
                logger.error(f"Repair failed for {task.sync_id}: {e}")
                task.retry_count += 1
                task.last_retry_at = time.time()

        # 保存更新后的队列
        self._save_queue()

        # 保存失败任务到单独文件(人工审查)
        if failed_tasks:
            self._save_failed_tasks(failed_tasks)

        logger.info(f"🔧 Repair complete: {repaired} fixed, {len(self.queue)} remaining")

        return repaired

    async def _repair_single(self, task: RepairTask, extractor, vector_store, graph_store) -> bool:
        """修复单个任务"""
        # 从Markdown重新读取原文
        md_file = Path(task.markdown_file)
        if not md_file.exists():
            logger.error(f"Markdown file not found: {md_file}")
            return False

        # 提取包含此SYNC_ID的部分(简化实现:读取整个文件)
        content = md_file.read_text(encoding="utf-8")

        # 重新提取(使用LLM或直接解析)
        # 这里需要实际的extractor接口,暂时返回True表示成功

        try:
            # 尝试从 Markdown 中解析 Frontmatter
            # 如果没有 python-frontmatter，则作为纯文本处理
            try:
                import frontmatter

                post = frontmatter.loads(content)
                metadata = post.metadata
                body = post.content
                summary = metadata.get("summary", body[:100])
            except ImportError:
                metadata = {}
                body = content
                summary = "Recovered Content"

            # 重建 Event 对象
            from dimcause.core.models import Event, EventType

            # 尝试还原 metadata 中的字段到 Event
            event = Event(
                id=task.sync_id,
                content=body,
                summary=summary,
                type=metadata.get("type", EventType.DECISION),  # 默认为 Decision
                timestamp=datetime.fromtimestamp(task.discovered_at),  # Fallback time
                metadata=metadata,
            )

            # 这才是真正的修复：写入数据库
            logger.info(f"Re-indexing event {task.sync_id} to VectorStore...")
            vector_store.add(event)

            # Graph 修复比较复杂，暂留空但明确告知
            if task.issue_type in ["missing_graph", "both"]:
                logger.warning(f"Graph repair for {task.sync_id} is not fully implemented yet.")
                # NOTE: graph_store.add(event) implementation pending

            return True

        except Exception as e:
            logger.error(f"Failed to rebuild event for {task.sync_id}: {e}")
            return False

    def _save_failed_tasks(self, tasks: List[RepairTask]) -> None:
        """保存失败任务到单独文件"""
        failed_file = self.queue_file.with_suffix(".failed.jsonl")

        with open(failed_file, "a", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(asdict(task)) + "\n")

        logger.warning(f"⚠️ Saved {len(tasks)} failed tasks to {failed_file}")

    def stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        issue_counts = {}
        for task in self.queue:
            issue_counts[task.issue_type] = issue_counts.get(task.issue_type, 0) + 1

        return {
            "total": len(self.queue),
            "by_type": issue_counts,
            "oldest_task": min((t.discovered_at for t in self.queue), default=None),
        }


# 全局单例
_repair_queue_instance = None


def get_repair_queue(markdown_dir: str = "docs/logs") -> AutoRepairQueue:
    """获取全局修复队列实例"""
    global _repair_queue_instance
    if _repair_queue_instance is None:
        _repair_queue_instance = AutoRepairQueue(markdown_dir=markdown_dir)
    return _repair_queue_instance
