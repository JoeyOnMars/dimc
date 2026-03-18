import asyncio
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.progress import Progress

from dimcause.core.models import Event, EventType, SourceType
from dimcause.extractors.llm_client import create_llm_client
from dimcause.storage import MarkdownStore, VectorStore
from dimcause.utils.git import GitRepo

console = Console()


class GitImporter:
    """
    时光机：将历史 Git Commit 转化为 Dimcause 记忆
    """

    def __init__(self, repo_path: str = ".", llm_config: Optional["LLMConfig"] = None):  # noqa: F821
        self.repo = GitRepo(repo_path)
        self.vector_store = VectorStore()
        self.markdown_store = MarkdownStore()

        # 使用传入的 LLM 配置，或从全局 Config 读取，或默认轻量级模型
        if llm_config:
            self.llm = create_llm_client(
                provider=llm_config.provider,
                model=llm_config.model,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
            )
        else:
            # 尝试从环境变量或配置读取
            try:
                from dimcause.utils.config import get_config

                get_config()
                # 假设 config 有 llm_primary 属性（来自 DimcauseConfig）
                # 如果没有，使用默认
                self.llm = create_llm_client(provider="ollama", model="qwen2:7b")
            except Exception:
                # 最后的 fallback
                self.llm = create_llm_client(provider="ollama", model="qwen2:7b")

    async def import_history(self, max_commits: int = 100, analyze: bool = False):
        """导入历史"""
        # commits = self.repo.get_file_history(".", max_count=max_commits)
        # console.print(f"[green]发现了 {len(commits)} 个历史 Commit，准备导入...[/]")

        # Use generator to avoid loading all commits into memory
        from dimcause.extractors.git_history import yield_file_history

        console.print(f"[green]开始导入历史 (Max: {max_commits}, Batch Size: 50)...[/]")

        batch_size = 50
        batch_events = []
        count = 0

        with Progress() as progress:
            task = progress.add_task("[cyan]Importing...", total=max_commits)  # Approximation

            # Stream commits
            for commit in yield_file_history(".", max_count=max_commits, cwd=self.repo.path):
                # 1. 脱敏 Commit Message (符合安全规范 0.2)
                try:
                    from dimcause.utils.security import sanitize

                    sanitized_message, _ = sanitize(commit.message)
                except (ImportError, TypeError, ValueError):
                    # Handle sanitization failure or different signature
                    sanitized_message = commit.message

                # 2. 构造基础事件
                event = Event(
                    id=f"git_{commit.hash}",
                    type=EventType.CODE_CHANGE,
                    timestamp=datetime.strptime(commit.date, "%Y-%m-%d")
                    if isinstance(commit.date, str)
                    else commit.date,
                    summary=sanitized_message.split("\n")[0],
                    content=f"Commit: {commit.hash}\nAuthor: {commit.author}\n\n{sanitized_message}",
                    metadata={
                        "hash": commit.hash,
                        "author": commit.author,
                        "imported_at": datetime.now().isoformat(),
                    },
                    source=SourceType.MANUAL,  # 标记为非实时捕获
                    tags=["git_history", "legacy_import"],
                )

                # 3. 存入 Dimcause (Markdown always per event for safety/atomicity)
                self.markdown_store.save(event)

                # Add to batch
                batch_events.append(event)

                # Flush batch
                if len(batch_events) >= batch_size:
                    self.vector_store.add_batch(batch_events)
                    batch_events = []

                progress.update(task, advance=1)
                count += 1

            # Flush remaining
            if batch_events:
                self.vector_store.add_batch(batch_events)
                batch_events = []

        console.print(f"[bold green]✅ 成功导入 {count} 条历史记录！[/]")
        console.print("现在的 'dimc search' 和 'dimc why' 可以使用这些数据了。")


# 为了 CLI 调用方便的封装函数
def run_import(max_commits: int = 50):
    importer = GitImporter()
    asyncio.run(importer.import_history(max_commits=max_commits))


# 兼容层：从 core/git_importer.py 迁移过来
# 用于 CLI 调用 (dimc daily --import-git)
def import_git_history(
    project_root: str = ".",
    limit: int = 100,
    existing_ids: set = None,
):
    """
    便捷函数: 导入 Git 历史

    用于 CLI 调用:
        from dimcause.importers.git_importer import import_git_history
        events = import_git_history(limit=50)

    Args:
        project_root: 项目根目录
        limit: 最大导入 commit 数
        existing_ids: 已存在的 Event IDs (用于增量导入)

    Returns:
        List[Event]: 转换后的 Event 列表
    """
    from datetime import datetime

    # 同步包装异步方法
    async def _run():
        # 收集 events
        events = []
        count = 0

        from dimcause.extractors.git_history import yield_file_history
        from dimcause.utils.security import sanitize

        for commit in yield_file_history(str(project_root), max_count=limit, cwd=str(project_root)):
            # 脱敏
            try:
                sanitized_message, _ = sanitize(commit.message)
            except Exception:
                sanitized_message = commit.message

            event_id = f"git_{commit.hash}"

            # 增量导入: 跳过已存在的
            if existing_ids and event_id in existing_ids:
                continue

            event = Event(
                id=event_id,
                type=EventType.CODE_CHANGE,
                timestamp=datetime.strptime(commit.date, "%Y-%m-%d")
                if isinstance(commit.date, str)
                else commit.date,
                summary=sanitized_message.split("\n")[0],
                content=f"Commit: {commit.hash}\nAuthor: {commit.author}\n\n{sanitized_message}",
                metadata={
                    "hash": commit.hash,
                    "author": commit.author,
                    "imported_at": datetime.now().isoformat(),
                },
                source=SourceType.MANUAL,
                tags=["git_history", "legacy_import"],
            )
            events.append(event)
            count += 1

        return events

    return asyncio.run(_run())
