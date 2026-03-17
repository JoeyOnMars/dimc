# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""
DIMCAUSE CLI (v0.1.0)
Local-first causal memory engine for AI agents (WAL + 5-Layer Ontology).



Usage:
    dimc up             # Start a new session
    dimc down           # End current session
    dimc job-start      #
    dimc job-end        #
    dimc index          #
    dimc context        #
    dimc capture        #
"""

#   import  httpx/requests
#  localhost  Antigravity Tools
import logging
import os

os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
os.environ["no_proxy"] = "127.0.0.1,localhost,::1"

# Manual .env loading (Zero-dependency)
try:
    from pathlib import Path

    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                # Remove quotes
                if (v.startswith('"') and v.endswith('"')) or (
                    v.startswith("'") and v.endswith("'")
                ):
                    v = v[1:-1]
                # Only set if not already set (allow override by shell)
                if k not in os.environ:
                    os.environ[k] = v
except Exception:
    pass

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from dimcause.cli_export import app as export_app
from dimcause.cli_graph import app as graph_app
from dimcause.utils.config import get_config
from dimcause.utils.state import get_all_recent_sessions, get_logs_dir, get_root_dir, get_today_dir

app = typer.Typer(
    name="dimcause",
    help="The Knowledge OS for Developers / 开发者知识操作系统",
    add_completion=False,
    invoke_without_command=True,
)
app.add_typer(graph_app, name="graph")
app.add_typer(export_app, name="export")

# MCP Sub-command group
mcp_app = typer.Typer(help="MCP Protocol Interface / MCP 协议接口")
app.add_typer(mcp_app, name="mcp")

# Config sub-command group
config_app = typer.Typer(help="Project configuration / 项目配置")
app.add_typer(config_app, name="config")


@mcp_app.command("serve")
def mcp_serve(
    transport: str = typer.Option(
        "stdio", "--transport", "-t", help="传输方式: stdio (默认) 或 http"
    ),
):
    """启动 MCP Server，支持 stdio (Claude Code) 和 http (Cursor/Web) 模式。"""
    try:
        from dimcause.protocols.mcp_server import run

        if transport == "http":
            console.print("[bold blue]启动 MCP Server (HTTP, 端口 14243)...[/]")
        run(transport=transport)
    except ImportError as e:
        console.print(f"[red]MCP Error: {e}[/]")
        console.print("[yellow]Please run: pip install -e '.[mcp]'[/]")
        raise typer.Exit(1) from None


@app.command()
def detect():
    """
    Detect supported IDE / AI tool integrations.
    检测可接入的 IDE / AI 工具。
    """
    from rich.table import Table

    from dimcause.watchers.detector import detect_tools

    detections = detect_tools()

    console.print(Panel.fit("[bold blue]Dimcause Detect[/]", border_style="blue"))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Tool", style="bold")
    table.add_column("Status")
    table.add_column("Support")
    table.add_column("Path", overflow="fold")
    table.add_column("Note", overflow="fold")

    detected_any = False
    for item in detections:
        status_label = "[green]detected[/]" if item.detected else "[dim]not found[/]"
        support_label = "[green]ready[/]" if item.supported else "[yellow]detect-only[/]"
        note = item.note
        if item.supported:
            if item.detected:
                note = f"可启用: dimc config enable {item.key}"
            else:
                note = f"未发现目录；可手动启用: dimc config enable {item.key} --path <path>"
        if item.detected:
            detected_any = True
        table.add_row(item.label, status_label, support_label, item.path, note)

    console.print(table)
    if not detected_any:
        console.print(
            "[yellow]No tool directories detected. You can still enable a tool with an explicit --path.[/]"
        )


@config_app.command("enable")
def config_enable(
    tool: str = typer.Argument(..., help="Tool name / 工具名"),
    path: Optional[str] = typer.Option(None, "--path", help="Override path / 自定义路径"),
):
    """
    Enable a supported tool integration in the project config.
    在项目配置中启用一个支持的工具集成。
    """
    from dimcause.utils.config import update_config_file
    from dimcause.watchers.detector import build_enable_updates, normalize_tool_name

    normalized_tool = normalize_tool_name(tool)

    try:
        updates = build_enable_updates(normalized_tool, path=path)
    except ValueError as exc:
        console.print(f"[red]Config error: {exc}[/]")
        raise typer.Exit(1) from None

    config_path = update_config_file(updates, root_dir=Path.cwd())

    console.print(Panel.fit("[bold green]Config Updated[/]", border_style="green"))
    console.print(f"Tool: [bold]{normalized_tool}[/]")
    console.print(f"Config: [cyan]{config_path}[/]")
    for key, value in updates.items():
        console.print(f"- {key}: {value}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key path / 配置键路径"),
    value: str = typer.Argument(..., help="Config value / 配置值"),
):
    """
    Set a project config value by dotted key path.
    使用点路径写入项目配置。
    """
    from dimcause.utils.config import normalize_config_key_path, set_config_value

    normalized_key = normalize_config_key_path(key)
    config_path = set_config_value(normalized_key, value, root_dir=Path.cwd())

    console.print(Panel.fit("[bold green]Config Updated[/]", border_style="green"))
    console.print(f"Key: [bold]{normalized_key}[/]")
    console.print(f"Value: [cyan]{value}[/]")
    console.print(f"Config: [cyan]{config_path}[/]")


console = Console()
logger = logging.getLogger(__name__)
SEARCH_SOURCE_CHOICES = {"events", "code", "docs"}


def _scheduler_report_path(task_id: str) -> Path:
    import re

    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", task_id.strip()).strip("-") or "task"
    return Path("tmp") / "scheduler" / f"{slug}_pr_ready_check.json"


def _run_scheduler_pr_ready(
    repo_root: Path,
    task_id: str,
    *,
    task_packet: Optional[Path],
    allow: list[str],
    risk: list[str],
    base_ref: str,
    report_file: Optional[Path],
    skip_check: bool,
    allow_dirty: bool,
) -> tuple[str, Path]:
    import subprocess
    import sys

    resolved_report = report_file or _scheduler_report_path(task_id)
    if not resolved_report.is_absolute():
        resolved_report = repo_root / resolved_report
    resolved_report.parent.mkdir(parents=True, exist_ok=True)

    script_path = repo_root / "scripts" / "pr_ready.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--task-id",
        task_id,
        "--base-ref",
        base_ref,
        "--report-file",
        str(resolved_report),
    ]
    if task_packet is not None:
        cmd.extend(["--task-packet", str(task_packet)])
    for item in allow:
        cmd.extend(["--allow", item])
    for item in risk:
        cmd.extend(["--risk", item])
    if skip_check:
        cmd.append("--skip-check")
    if allow_dirty:
        cmd.append("--allow-dirty")

    result = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        console.print(result.stdout.rstrip())
    if result.stderr:
        console.print(result.stderr.rstrip(), style="red")
    if result.returncode != 0:
        raise RuntimeError("PR_READY verification failed")
    return result.stdout.strip(), resolved_report


def _llm_env_key(provider: str) -> Optional[str]:
    return {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }.get(provider)


def _load_project_llm_config(section: str = "llm_primary") -> dict[str, Any]:
    from dimcause.utils.config import get_config_value

    raw = get_config_value(section, root_dir=Path.cwd(), default={})
    return raw if isinstance(raw, dict) else {}


def _apply_llm_overrides(config, section: str = "llm_primary"):
    overrides = _load_project_llm_config(section)
    for field in (
        "provider",
        "model",
        "base_url",
        "api_key",
        "temperature",
        "max_tokens",
        "timeout",
    ):
        if field in overrides:
            setattr(config, field, overrides[field])

    env_key = _llm_env_key(config.provider)
    if not config.api_key and env_key and os.environ.get(env_key):
        config.api_key = os.environ.get(env_key)

    return config


def get_analyst():
    """Lazy load API client and Analyst"""
    from dimcause.brain.analyzer import Analyst
    from dimcause.core.models import LLMConfig
    from dimcause.extractors.llm_client import create_llm_client

    llm_config = _apply_llm_overrides(LLMConfig(provider="deepseek", model="deepseek-chat"))
    if not llm_config.api_key:
        env_key = _llm_env_key(llm_config.provider) or "LLM_API_KEY"
        console.print(f"[red]  {env_key}[/]")
        console.print(f"   export {env_key}='sk-...'")
        raise typer.Exit(1)

    client = create_llm_client(
        provider=llm_config.provider,
        model=llm_config.model,
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
    )
    return Analyst(client)


#
#
MENU_OPTIONS = [
    ("up", "☀️  Start Session", "初始化/恢复工作会话 (dimc up)", "dimc up"),
    ("down", "🌙  End Session", "Git 提交 & 生成小结 (dimc down)", "dimc down --push"),
    ("detect", "🛰️  工具探测", "检测可接入的 IDE / AI 工具", "dimc detect"),
    ("job-start", "✨  开始任务", "创建新的 Agent 任务", "dimc job-start <id>"),
    ("job-end", "🏁  结束任务", "完成当前 Agent 任务", "dimc job-end"),
    ("context", "🧠  查看上下文", "显示当前任务状态", "dimc context"),
    ("scheduler", "📅  调度计划", "查看/管理 Agent 计划", "dimc scheduler plan"),
    ("lint", "🔍  代码检查", "运行本地 Linter", "dimc lint"),
    ("index", "📚  重建索引", "更新知识库 (Logs & Code)", "dimc index --rebuild"),
    ("search", "🔎  语义搜索", "搜索项目记忆", "dimc search <query>"),
    ("trace", "🕸️  追踪变更", "分析文件修改历史", "dimc trace <file>"),
    ("why", "🤔  深度归因", "分析代码变更原因", "dimc why <file>"),
    ("reflect", "💡  Reflect AI", "每日/每周反思 (DeepSeek)", "dimc reflect --week"),
    ("history", "📜  项目历史", "查看 Timeline", "dimc history <file>"),
    ("daemon", "👻  后台进程", "管理守护进程 / IDE 集成", "dimc daemon status"),
    ("scan", "🛡️  敏感扫描", "检查代码库敏感信息", "dimc scan ."),
    ("migrate", "📦  数据迁移", "升级存储 Schema (v1->v2)", "dimc migrate --dry-run"),
    ("audit", "🏥  全面审计", "系统健康检查", "dimc audit"),
    ("capture", "📥  捕获对话", "导入外部 LLM 对话", "dimc capture"),
    ("init", "⚙️  初始化", "重置/初始化配置", "dimc init"),
    ("stats", "📊  统计信息", "查看 Token 使用量", "dimc stats"),
    ("graph", "🕸️  因果图谱", "构建/可视化因果关联", "dimc graph show"),
    ("data-import", "📥  导入数据", "导入外部目录/文档", "dimc data-import <path>"),
]


@app.callback()
def main_callback(ctx: typer.Context):
    """
    Dimcause - Local-first causal memory engine for AI agents


    """
    if ctx.invoked_subcommand is None:
        show_interactive_menu()


def show_interactive_menu():
    """"""
    from rich.prompt import IntPrompt
    from rich.table import Table

    console.print(
        Panel.fit(
            "[bold blue]🚀 Dimcause[/]\n[dim]The Knowledge OS for Developers (Superset).[/]",
            border_style="blue",
        )
    )

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("#", style="dim", width=3)
    table.add_column("", width=2)  # Icon
    table.add_column("命令", width=14)  # Text
    table.add_column("描述", style="dim", width=22)
    table.add_column("用法", style="cyan dim")

    for i, (_cmd, label, desc, usage) in enumerate(MENU_OPTIONS, 1):
        parts = label.split("  ", 1)
        if len(parts) == 2:
            icon, text = parts
        else:
            # Fallback if no double space found
            icon, text = " ", label

        table.add_row(str(i), icon, text, desc, usage)

    table.add_row("0", "", "[dim]退出[/]", "", "")

    console.print(table)
    console.print()

    try:
        choice = IntPrompt.ask("", default=1)
    except KeyboardInterrupt:
        console.print("\n[dim][/]")
        raise typer.Exit(0) from None

    if choice == 0:
        console.print("[dim]![/]")
        raise typer.Exit(0)

    if 1 <= choice <= len(MENU_OPTIONS):
        cmd_name, label, _, _ = MENU_OPTIONS[choice - 1]
        console.print(f"\n[blue]: {label}[/]\n")
        _execute_menu_command(cmd_name)
    else:
        console.print("[red][/]")
        raise typer.Exit(1)


def _execute_menu_command(cmd_name: str):
    """"""

    if cmd_name == "up":
        up()
    elif cmd_name == "down":
        down()
    elif cmd_name == "detect":
        detect()
    elif cmd_name == "job-start":
        job_id = Prompt.ask(" ID", default="new-task")
        job_start(job_id)
    elif cmd_name == "job-end":
        job_end()
    elif cmd_name == "context":
        context()
    elif cmd_name == "scheduler":
        scheduler_plan()
    elif cmd_name == "lint":
        lint_run()
    elif cmd_name == "index":
        index()
    elif cmd_name == "search":
        query = Prompt.ask("")
        search(query)
    elif cmd_name == "trace":
        query = Prompt.ask("//")
        trace(query)
    elif cmd_name == "why":
        target = Prompt.ask("")
        why(target)
    elif cmd_name == "history":
        target = Prompt.ask("")
        history(target)
    elif cmd_name == "daemon":
        daemon(action="status")
    elif cmd_name == "scan":
        scan(".")
    elif cmd_name == "audit":
        audit(fix=Confirm.ask("Auto-fix issues where possible?", default=False))
    elif cmd_name == "capture":
        capture()
    elif cmd_name == "init":
        init()
    elif cmd_name == "stats":
        stats()
    elif cmd_name == "reflect":
        reflect()
    elif cmd_name == "migrate":
        migrate()
    elif cmd_name == "init":
        init()
    elif cmd_name == "graph":
        console.print("[blue]Tip: Graph CLI has subcommands: build, check, show[/]")
        show_interactive_menu()  # Re-show menu or run default?
        # Better: run graph show as default
        from dimcause.cli_graph import show

        show()
    elif cmd_name == "data-import":
        target = Prompt.ask("请输入要导入的目录路径")
        data_import(target)
    else:
        # Check if user made a typo or meant 'search'
        console.print(f"[yellow] {cmd_name} [/]")


# get_root_dir, get_logs_dir, get_today_dir 已从 dimcause.utils.state 导入
# 不再使用基于 __file__ 的路径推算（安装到 .venv 后会指向错误路径）


def get_today_str() -> str:
    """"""
    tz_name = os.environ.get("TZ", "Asia/Shanghai")
    try:
        import pytz

        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%Y-%m-%d")


# get_today_dir 已从 dimcause.utils.state 导入（见文件顶部）


# ===  ===


@app.command()
def version():
    """Show the version and exit."""
    from dimcause import __version__

    console.print(f"Dimcause [bold green]v{__version__}[/]")


@app.command()
def up():
    """
    Start a new session.
    启动新会话。

    Actions:
    - Pull latest code / 拉取最新代码
    - Check pending tasks / 检查待办任务
    - Create session start log / 创建会话启动日志

    Examples:
        dimc up
    """
    from dimcause.utils.state import check_orphan_jobs, check_pending_merge, clear_pending_merge

    console.print(Panel.fit("[bold blue]🚀 Dimcause - 会话启动[/]", border_style="blue"))

    # 1. Check Pending Merges
    pending = check_pending_merge()
    if pending:
        console.print(f"\n[yellow]  : {pending}[/]")
        console.print("   ")
        console.print(f"   : [dim]git merge {pending}[/]")

        if Confirm.ask("?", default=True):
            from dimcause.utils.git import run_git

            code, out, err = run_git("merge", pending)
            if code == 0:
                console.print("[green] [/]")
                clear_pending_merge()
            else:
                console.print(f"[red] : {err}[/]")

    # 2.
    orphans = check_orphan_jobs(days=3)
    if orphans:
        console.print(f"\n[yellow]   {len(orphans)} :[/]")
        for job in orphans[:5]:
            console.print(f"   - {job['id']} ({job['date']})")
        console.print("   [dim] 'dimc job-end' [/]")

    # 3.  (Dogfooding)
    console.print("\n[bold green]  昨日待办 (from Dimcause):[/]")
    tasks = _fetch_tasks(status="pending")
    if tasks:
        for i, t in enumerate(tasks, 1):
            console.print(f"   {i}. {t['summary']}")

        if not Confirm.ask("?", default=True):
            console.print("[dim][/]")
    else:
        console.print("   [dim]Good job![/]")

    # 3.5 Context Recovery (New Implementation)
    from dimcause.utils.state import get_last_session

    last_session = get_last_session()
    if last_session:
        console.print(Panel("[bold cyan]🔄 Context Recovery Prompt[/]", border_style="cyan"))

        # Determine strict status
        if last_session.end_file.exists():
            status_text = (
                f"Resuming from closed session {last_session.seq} ({last_session.date_path.name})"
            )
            source_file = last_session.end_file
        else:
            status_text = (
                f"Resuming from ACTIVE session {last_session.seq} ({last_session.date_path.name})"
            )
            source_file = last_session.start_file

        recovery_msg = f"""# Context Restoration
User is resuming work on Dimcause.
**Last Session**: {last_session.date_path.name}/{last_session.seq}
**Status**: {status_text}
**Reference Log**: {source_file.relative_to(get_root_dir())}

Please check the reference log for [Tasks], [Decisions], and [Code Changes].
"""
        console.print(recovery_msg)
        console.print("[dim](Copy the above block to your next agent session)[/]")
    else:
        console.print("[dim]No previous session found for context recovery.[/]")

    # 4.
    _create_daily_log("start")
    console.print("[green] [/]")

    # 5.
    from dimcause.daemon.process import process_manager

    if not process_manager.is_running():
        console.print("\n[blue] ...[/]")
        try:
            process_manager.start_daemon()
            console.print("[green] Daemon [/]")
        except Exception as e:
            console.print(f"[red] Daemon : {e}[/]")
    else:
        console.print("\n[dim] Daemon [/]")


@app.command()
def down(
    skip_export: bool = typer.Option(
        False, "--skip-export", "-s", help="Skip AI log check (Deprecated, handled by service)"
    ),
    skip_git: bool = typer.Option(False, "--skip-git", "-g", help="Skip Git commit"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Skip comprehensive checks"),
):
    """
    End current session.
    结束当前会话。

    Actions:
    - Collect Session Data (L1) / 采集数据
    - Generate Session End Log (L0) / 生成结束日志
    - Inject Context (L2) / 注入上下文
    - Smart Scan / 智能事件提取
    - Git Commit / 提交代码
    """
    if hasattr(skip_export, "default"):
        skip_export = skip_export.default
    if hasattr(skip_git, "default"):
        skip_git = skip_git.default
    if hasattr(quick, "default"):
        quick = quick.default

    from datetime import datetime

    from dimcause.services.session_end import SessionEndService
    from dimcause.utils.state import resolve_session_path

    console.print(Panel.fit("[bold blue]🌙 Dimcause - Session End[/]", border_style="blue"))

    # 1. Resolve Session ID
    try:
        # Utilize core logic to determine target session
        log_file, seq_id = resolve_session_path("end")
        session_year = log_file.parent.parent.name
        session_date = log_file.parent.name
        session_id = f"{session_year}-{session_date}-{seq_id}"
        today_str = datetime.now().strftime("%Y-%m-%d")

        console.print(f"[dim]Target Session: {session_id}[/]")
    except Exception as e:
        console.print(f"[red]Failed to resolve session: {e}[/]")
        raise typer.Exit(1) from e

    # --- Phase 1: Mark & Pause ---
    end_dt = datetime.now()
    console.print(f"⏱️  Session End Marked at: [bold]{end_dt.strftime('%Y-%m-%d %H:%M:%S')}[/]")

    from dimcause.utils.state import record_session_end_timestamp

    record_session_end_timestamp(session_id, end_dt)

    Prompt.ask("\n[bold yellow]📤 请现在导出对话到 AG_Exports 目录，然后按 Enter 继续...[/]")

    # --- Phase 2: Execute & Extract ---
    service = SessionEndService(console)

    # Pass 'skip_export' intent? Service handles "empty data" check interactively.
    # 'quick' might mean skip verification? For now ignored in Iteration 1.

    success = service.execute(session_id, today_str, end_timestamp=end_dt)

    if not success:
        console.print("[red]Session end process failed.[/]")
        raise typer.Exit(1)

    # 3. Finalize
    if not skip_git:
        service.finalize(session_id)

    console.print("\n[bold green]✅ Session Closed Successfully.[/]")


@app.command("data-import")
def data_import(
    path: Path = typer.Argument(..., help="要导入的目录或文件路径", exists=True),
    recursive: bool = typer.Option(True, "--recursive", "-r", help="是否递归导入子目录"),
):
    """
    Import external data (Markdown, PDF, Docx, etc.) from a local directory or file.
    从本地目录或文件导入外部数据（Markdown, PDF, Docx 等）。

    Examples:
        dimc data-import ./raw_data
        dimc data-import ./docs/spec.pdf
    """
    if hasattr(path, "default"):
        path = path.default
    if hasattr(recursive, "default"):
        recursive = recursive.default
    from dimcause.importers.dir_importer import DirectoryImporter
    from dimcause.storage.markdown_store import MarkdownStore
    from dimcause.storage.vector_store import VectorStore

    console.print(Panel.fit(f"[bold blue]📥 Data Import: {path}[/]", border_style="blue"))

    try:
        # Initialize stores
        md_store = MarkdownStore()
        # Initialize VectorStore (might take a moment to load models)
        console.print("[dim]Loading embedding models...[/]")
        vec_store = VectorStore()

        importer = DirectoryImporter(markdown_store=md_store, vector_store=vec_store)

        console.print(f"[bold]Scanning {path}...[/]")

        if path.is_file():
            # Single file import is not directly exposed but we can simulate or add method
            # DirectoryImporter.import_directory handles directories.
            # Let's check if we can handle single file or strict directory.
            # import_directory iterates path.rglob.
            # If path is a file, we might need a wrapper or just handle it.
            # For now, let's assume directory or handle parent.
            stats = importer.import_directory(
                path.parent if path.is_file() else path, recursive=recursive
            )
            # Wait, import_directory scans the *directory*. If we pass a file's parent, it scans all siblings.
            # Ideally we should enhance DirectoryImporter to handle single file, but based on current API:
            # It iterates path.rglob("*") if directory.
            # Let's stick to directory for now or use a temporary workaround if it's a file.
            pass

        stats = importer.import_directory(path, recursive=recursive)

        # Output stats
        console.print("\n[bold green]✅ Import Completed[/]")
        console.print(f"  Processed: {stats.get('processed', 0)}")
        console.print(f"  Skipped:   {stats.get('skipped', 0)}")
        console.print(f"  Errors:    {stats.get('errors', 0)}")

        if stats.get("errors", 0) > 0:
            console.print("[yellow]Check logs for details on errors.[/]")

    except Exception as e:
        console.print(f"[red]❌ Import Failed: {e}[/]")
        # import traceback
        # traceback.print_exc()


@app.command("job-start")
def job_start(
    job_id: str = typer.Argument(..., help="Unique Job ID / 任务 ID"),
):
    """
    Start a new Agent Job.
    创建新的 Agent 任务。

    [bold cyan]用法: dimc job-start JOB_ID[/]

    Examples:
        dimc job-start "refactor-auth-module"
    """
    if hasattr(job_id, "default"):
        job_id = job_id.default
    from dimcause.utils.state import record_job_start

    #  job_id
    job_id = job_id.lower().replace(" ", "-")

    console.print(f"[blue] : {job_id}[/]")

    _create_job_log(job_id, "start")
    record_job_start(job_id)

    console.print("[green] [/]")
    console.print(f"   [dim]: dimc job-end {job_id}[/]")


@app.command("job-end")
def job_end(
    job_id: str = typer.Argument(None, help="Job ID to end (optional) / 任务 ID (可选)"),
):
    """
    End the current Agent Job.
    完成当前 Agent 任务。

    [bold cyan]用法: dimc job-end [JOB_ID][/]

    Examples:
        dimc job-end
        dimc job-end "refactor-auth-module"
    """
    if hasattr(job_id, "default"):
        job_id = job_id.default
    from dimcause.utils.state import get_active_job, record_job_end

    if job_id is None:
        job_info = get_active_job()
        if not job_info:
            console.print("[red] [/]")
            console.print("   [dim] ID: dimc job-end <job-id>[/]")
            raise typer.Exit(1)
        job_id, job_dir = job_info
    else:
        # Manual job_id provided, treat as new job for today (or could search, but keep simple)
        job_dir = None

    job_id = job_id.lower().replace(" ", "-")

    console.print(f"[green] : {job_id}[/]")

    _create_job_log(job_id, "end", job_dir=job_dir)
    record_job_end()

    console.print("[dim][/]")


@app.command()
def index(
    rebuild: bool = typer.Option(False, "--rebuild", "-r", help="Force full rebuild / 强制重建"),
    parallel: bool = typer.Option(
        False, "--parallel", "-p", help="Enable parallel processing / 并行处理"
    ),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of workers / 线程数"),
    status: bool = typer.Option(False, "--status", "-s", help="Show index stats / 显示索引状态"),
):
    """
    Rebuild or update the knowledge index.
    重建或更新知识索引。

    [bold cyan]用法: dimc index [OPTIONS][/]

    Examples:
        dimc index --rebuild        # Full rebuild
        dimc index --status         # Show index stats
    """
    import os

    from dimcause.core.event_index import EventIndex

    # Fix for interactive menu
    if hasattr(rebuild, "default"):
        rebuild = rebuild.default
    if hasattr(parallel, "default"):
        parallel = parallel.default
    if hasattr(workers, "default"):
        workers = workers.default
    if hasattr(status, "default"):
        status = status.default

    #
    use_event_index = os.getenv("DIMCAUSE_USE_EVENT_INDEX", "true").lower() == "true"

    #
    if status:
        _show_index_status(use_event_index)
        return

    if use_event_index:
        #  EventIndex ()
        event_index = EventIndex()

        if rebuild:
            console.print("[yellow]  EventIndex...[/]")
            stats = _rebuild_event_index(event_index)
        else:
            console.print("[blue]  EventIndex...[/]")
            stats = _sync_event_index(event_index)

        console.print("[green] EventIndex [/]")
        console.print(f"   : {stats.get('added', 0)}")
        console.print(f"   : {stats.get('updated', 0)}")
        console.print(f"   : {stats.get('skipped', 0)}")
        if stats.get("git_commits", 0) > 0:
            console.print(f"   Git Commits: {stats.get('git_commits', 0)}")
    else:
        #  indexer (Fallback)
        from dimcause.core.indexer import rebuild_index, update_index

        if rebuild:
            console.print("[yellow]  ()...[/]")
            stats = rebuild_index()
        else:
            stats = update_index()

        console.print("[green] [/]")
        console.print(f"   : {stats['processed']} | : {stats['skipped']} | : {stats['errors']}")
        console.print(f"   : {stats['hot']} | : {stats['archive']}")

    #
    try:
        if parallel:
            console.print(f"[dim]  (workers={workers})...[/]")
            from dimcause.core.parallel_indexer import update_code_index_parallel

            code_count = update_code_index_parallel(max_workers=workers)
        else:
            console.print("[dim]updating code index...[/]")
            from dimcause.core.code_indexer import update_code_index

            code_count = update_code_index()

        console.print(f"[green] : {code_count} [/]")
    except Exception as e:
        console.print(f"[yellow] : {e}")

    # === 向量同步：将 EventIndex 中的事件写入 VectorStore (语义搜索所需) ===
    if rebuild:
        try:
            from dimcause.core.models import Event
            from dimcause.storage.vector_store import VectorStore

            console.print("[blue]  向量索引 (Embedding)...[/]")
            vs = VectorStore()

            # 从 EventIndex 读取所有事件
            conn = event_index._get_conn()
            try:
                cursor = conn.execute("SELECT id, type, timestamp, summary, json_cache FROM events")
                rows = cursor.fetchall()
            finally:
                conn.close()

            if rows:
                embedded_count = 0
                batch_size = 50
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    for row in batch:
                        try:
                            # 尝试从 json_cache 恢复完整 Event
                            if row[4]:
                                event = Event.model_validate_json(row[4])
                            else:
                                event = Event(
                                    id=row[0],
                                    type=row[1],
                                    timestamp=row[2],
                                    summary=row[3],
                                    content=row[3],
                                )
                            vs.add(event)
                            embedded_count += 1
                        except Exception:
                            pass  # 跳过无法解析的事件

                    # 每批次后释放模型，减少持续内存占用
                    console.print(
                        f"[dim]  已嵌入 {min(i + batch_size, len(rows))}/{len(rows)} 事件[/]"
                    )

                # 全部完成后释放 Embedding 模型
                vs.release_model()
                console.print(f"[green]  向量索引：{embedded_count} 个事件已嵌入[/]")
            else:
                console.print("[yellow]  EventIndex 为空，跳过向量索引[/]")
        except Exception as e:
            console.print(f"[yellow] 向量索引失败: {e}[/]")
            import traceback

            traceback.print_exc()


def _sync_event_index(event_index) -> dict:
    """EventIndex"""
    import time
    from pathlib import Path

    start_time = time.time()

    #  indexer
    scan_paths = []

    # 1. ~/.dimcause/events/ -
    events_dir = Path.home() / ".dimcause" / "events"
    if events_dir.exists():
        scan_paths.append(str(events_dir))

    # 2. docs/logs/ -
    logs_dir = Path.cwd() / "docs" / "logs"
    if logs_dir.exists():
        scan_paths.append(str(logs_dir))

    if not scan_paths:
        console.print("[yellow] [/]")
        return {"scanned": 0, "updated": 0, "removed": 0}

    try:
        #
        stats = event_index.sync(scan_paths)
        elapsed = time.time() - start_time
        console.print(f"[dim]: {elapsed:.2f}s[/]")
        console.print(f"[dim]: {', '.join(scan_paths)}[/]")
        return stats
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        import traceback

        traceback.print_exc()
        return {"scanned": 0, "updated": 0, "removed": 0}


def _rebuild_event_index(event_index) -> dict:
    """EventIndex"""
    import time
    from pathlib import Path

    start_time = time.time()

    #
    conn = event_index._get_conn()
    try:
        conn.execute("DELETE FROM events")
        conn.commit()
        console.print("[dim][/]")
    finally:
        conn.close()

    #  _sync_event_index
    scan_paths = []

    # 1. ~/.dimcause/events/ -
    events_dir = Path.home() / ".dimcause" / "events"
    if events_dir.exists():
        scan_paths.append(str(events_dir))

    # 2. docs/logs/ -
    logs_dir = Path.cwd() / "docs" / "logs"
    if logs_dir.exists():
        scan_paths.append(str(logs_dir))

    stats = {"scanned": 0, "updated": 0, "removed": 0, "git_commits": 0}

    if not scan_paths:
        console.print("[yellow] [/]")
    else:
        try:
            #
            sync_stats = event_index.sync(scan_paths)
            stats.update(sync_stats)
            console.print(f"[dim]: {', '.join(scan_paths)}[/]")
        except Exception as e:
            console.print(f"[red] : {e}[/]")
            import traceback

            traceback.print_exc()

    # === H2 :  Git Commits ===
    try:
        from dimcause.importers.git_importer import import_git_history

        console.print("[blue]  Git ...[/]")

        #  git_  event IDs
        existing_git_ids = set()
        conn = event_index._get_conn()
        try:
            cursor = conn.execute("SELECT id FROM events WHERE id LIKE 'git_%'")
            existing_git_ids = {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

        #  Git Commits ( 200 )
        git_events = import_git_history(
            project_root=Path.cwd(),
            limit=200,
            existing_ids=existing_git_ids,
        )

        #  ( SQL add() )
        if git_events:
            import time as time_module

            conn = event_index._get_conn()
            try:
                for event in git_events:
                    tags_str = ",".join(event.tags)
                    json_cache = event.model_dump_json()
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO events (
                            id, type, source, timestamp, date, summary, tags,
                            markdown_path, mtime, job_id, status,
                            schema_version, json_cache, cache_updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            event.id,
                            getattr(event.type, "value", str(event.type)),
                            getattr(event.source, "value", str(event.source)),
                            event.timestamp.isoformat(),
                            event.timestamp.strftime("%Y-%m-%d"),
                            event.summary,
                            tags_str,
                            f"git://{event.metadata.get('git_hash', event.id)}",  #
                            time_module.time(),
                            "",
                            "active",
                            1,
                            json_cache,
                            time_module.time(),
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

        stats["git_commits"] = len(git_events)
        console.print(f"[green]  {len(git_events)}  Git Commits[/]")

    except ImportError as e:
        console.print(f"[yellow] Git : {e}[/]")
    except Exception as e:
        console.print(f"[yellow] Git : {e}[/]")
        import traceback

        traceback.print_exc()

    elapsed = time.time() - start_time
    console.print(f"[dim]: {elapsed:.2f}s[/]")
    return stats


def _show_index_status(use_event_index: bool):
    """"""

    console.print(Panel.fit("[bold blue] [/]", border_style="blue"))

    if use_event_index:
        from dimcause.core.event_index import EventIndex

        event_index = EventIndex()
        db_path = event_index.db_path

        #
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            console.print(f": {db_path}")
            console.print(f": {size_mb:.2f} MB")

            #
            conn = event_index._get_conn()
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM events")
                total = cursor.fetchone()[0]
                console.print(f": {total}")

                #
                cursor = conn.execute("SELECT type, COUNT(*) FROM events GROUP BY type")
                console.print("\n:")
                for row in cursor:
                    console.print(f"  {row[0]}: {row[1]}")
            finally:
                conn.close()
        else:
            console.print("[yellow] [/]")
            console.print("[dim] `mal index` [/]")
    else:
        console.print("[dim] indexer[/]")
        console.print("[dim] DIMCAUSE_USE_EVENT_INDEX=true [/]")


@app.command()
def context():
    """
    View current context and task status.
    查看当前任务上下文状态。

    [bold cyan]用法: dimc context[/]

    Examples:
        dimc context
    """
    from dimcause.core.context import load_context

    ctx = load_context()

    console.print(Panel.fit("[bold blue]📋 当前上下文状态[/]", border_style="blue"))

    if ctx.pending_merge:
        console.print(f"\n[yellow]⚠️ 待合并分支: {ctx.pending_merge}[/]")

    if ctx.orphan_jobs:
        console.print(f"\n[yellow]⚠️ 未闭合任务: {', '.join(ctx.orphan_jobs)}[/]")

    if ctx.recent_entries:
        console.print(f"\n[blue]📊 近期任务记录 ({len(ctx.recent_entries)} 条):[/]")
        for entry in ctx.recent_entries[:5]:
            icon = "✅" if entry.status == "done" else "🔄"
            console.print(f"   {icon} [{entry.date}] {entry.job}")
            if entry.summary:
                console.print(f"      📝 {entry.summary[:60]}...")
    else:
        console.print("\n[dim]暂无任务记录[/]")

    if ctx.todos:
        console.print(f"\n[green]📝 待办事项 ({len(ctx.todos)} 条):[/]")
        for i, todo in enumerate(ctx.todos[:5], 1):
            console.print(f"   {i}. {todo[:80]}")
    else:
        console.print("\n[dim]✅ 无遗留待办事项[/]")


@app.command()
def reflect(
    date: str = typer.Option("today", help="Date to reflect on (YYYY-MM-DD or 'today') / 日期"),
    output: str = typer.Option(None, help="Output file path / 输出文件路径"),
):
    """
    (AI Powered) Reflect on daily/weekly progress.
    (AI 驱动) 反思每日/每周进度。

    [bold cyan]用法: dimc reflect [OPTIONS][/]

    Examples:
        dimc reflect                # Reflect on today
        dimc reflect --date 2023-10-27
    """
    from datetime import datetime

    from rich.markdown import Markdown

    # Fix for interactive menu: Unwrap typer defaults if function called directly
    if hasattr(date, "default"):
        date = date.default
    if hasattr(output, "default"):
        output = output.default

    console.print(f"[blue] AI Reflecting on {date}...[/]")

    target_date = get_today_str() if date == "today" else date
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        year = dt.strftime("%Y")
        day = dt.strftime("%m-%d")
        folder = get_logs_dir() / year / day
    except ValueError:
        console.print("[red]  YYYY-MM-DD[/]")
        return

    if not folder.exists():
        console.print(f"[yellow] : {folder}[/]")
        return

    logs_text = ""
    for f in sorted(folder.glob("*.md")):
        logs_text += f"\n\n--- {f.name} ---\n\n" + f.read_text(encoding="utf-8", errors="replace")

    if not logs_text.strip():
        console.print("[yellow] [/]")
        return

    try:
        analyst = get_analyst()
        with console.status("[bold green] DeepSeek Reflecting...[/]"):
            report = analyst.reflect_on_logs(logs_text)

        console.print(
            Panel(Markdown(report), title=f"Daily Reflection: {target_date}", border_style="green")
        )

        if output:
            Path(output).write_text(report, encoding="utf-8")
            console.print(f"[green] : {output}[/]")

    except Exception as e:
        console.print(f"[red] : {e}[/]")


@app.command(name="add")
def add(
    content: str = typer.Argument(..., help="Event content / 事件内容"),
    type: str = typer.Option(
        "decision",
        "--type",
        "-t",
        help="Event type / 事件类型 (decision, git_commit, failed_attempt, etc.)",
    ),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags / 标签"),
    status: str = typer.Option(
        None, "--status", "-s", help="Task status / 状态: pending, done, in_progress"
    ),
    analyze: bool = typer.Option(
        False, "--analyze", "--auto-tag", help="Analyze with AI / AI 分析"
    ),
    summary: str = typer.Option(None, "--summary", help="Event summary / 摘要"),
    metadata_json: str = typer.Option(None, "--metadata", help="Extra metadata in JSON / 元数据"),
):
    """
    Add a new event to the causal graph.
    添加新事件到因果图谱。

    [bold cyan]用法: dimc add CONTENT [OPTIONS][/]

    Examples:
        dimc add "Refactored login logic" --type decision --tags auth,refactor
        dimc add "Database connection failed" --type failed_attempt --analyze
    """
    if hasattr(content, "default"):
        content = content.default
    if hasattr(type, "default"):
        type = type.default
    if hasattr(tags, "default"):
        tags = tags.default
    if hasattr(status, "default"):
        status = status.default
    if hasattr(analyze, "default"):
        analyze = analyze.default
    if hasattr(summary, "default"):
        summary = summary.default
    if hasattr(metadata_json, "default"):
        metadata_json = metadata_json.default
    import json
    import os
    import time
    from datetime import datetime

    from dimcause.core.event_index import EventIndex
    from dimcause.core.models import Event, EventType, SourceType
    from dimcause.storage import MarkdownStore, VectorStore

    # Auto-generate ID and timestamp
    timestamp = datetime.now()
    evt_id = f"manual_{int(time.time())}"

    # Fix: Ensure summary exists
    if not summary:
        summary = content[:50].replace("\n", " ")

    console.print(Panel.fit("[bold blue]  MAL[/]", border_style="blue"))

    ai_summary = None

    # === AI Analysis ===
    if analyze:
        try:
            with console.status("[bold green] DeepSeek Analyzing...[/]"):
                analyst = get_analyst()
                suggestion = analyst.analyze_input(content)

            console.print("\n[bold cyan] AI Suggestion:[/]")
            console.print(f"   Type:    {suggestion['type']}")
            console.print(f"   Tags:    {suggestion['tags']}")
            console.print(f"   Summary: {suggestion['summary']}")

            if Confirm.ask("?", default=True):
                suggested_type = suggestion["type"]
                # Map suggested type string to valid Option value if possible, or keep as is
                # But EventType(type) expects valid enum value.
                # Let's trust AI returns valid type string or fallback later.
                type = suggested_type

                # Merge tags from CLI and AI
                suggestion_tags = suggestion["tags"]
                cli_tags = [t.strip() for t in tags.split(",") if t.strip()]
                all_tags = list(set(cli_tags + suggestion_tags))
                tags = ",".join(all_tags)
                ai_summary = suggestion["summary"]
                summary = ai_summary  # Use AI summary

        except Exception as e:
            console.print(f"[yellow] AI : {e}[/]")

    try:
        # Determine Final Type
        final_type = EventType.DECISION
        if type in EventType._value2member_map_:
            final_type = EventType(type)

        # Parse Metadata
        metadata = {"added_via": "mal add", "type_hint": type}
        if status:
            metadata["status"] = status

        if metadata_json:
            try:
                cli_meta = json.loads(metadata_json)
                metadata.update(cli_meta)
            except json.JSONDecodeError:
                console.print("[yellow] Metadata JSON , [/]")

        # Create Event
        evt = Event(
            id=evt_id,
            timestamp=timestamp,
            content=content,
            summary=summary,
            type=final_type,
            source=SourceType.MANUAL,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            status=status or "active",
            metadata=metadata,
        )

        # 1. Save to Markdown
        store = MarkdownStore()
        path = store.save(evt)

        # 2. Update EventIndex (core)
        index = EventIndex()
        index.add(evt, str(path))

        # 3. Update VectorStore (legacy/optional)
        try:
            data_dir = os.path.expanduser("~/.dimcause")
            vector_store = VectorStore(persist_dir=f"{data_dir}/chroma")
            vector_store.add(evt)
        except Exception:
            # VectorStore might fail if not configured, treat as non-fatal?
            # Or just log it.
            # console.print(f"[yellow] Vector Store : {e}[/]")
            pass

        console.print(
            f"[green]Logged {evt.id} ({getattr(evt.type, 'value', str(evt.type))}) -> {path}[/]"
        )
        console.print(f"[dim]: {evt.summary}[/]")

    except Exception as e:
        import traceback

        traceback.print_exc()
        console.print(f"[red]Error logging: {e}[/]")
        raise typer.Exit(1) from None


@app.command()
def tasks(
    status: str = typer.Option(
        "pending", "--status", "-s", help="Filter by status (pending, done, all) / 状态过滤"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max tasks to show / 显示数量"),
):
    """
    List pending tasks.
    列出待办任务。

    [bold cyan]用法: dimc tasks [OPTIONS][/]

    Examples:
        dimc tasks
        dimc tasks --status done --limit 5
    """
    if hasattr(status, "default"):
        status = status.default

    tasks = _fetch_tasks(status=None if status == "all" else status)

    console.print(Panel.fit(f"[bold blue]  ({status})[/]", border_style="blue"))

    if not tasks:
        console.print("[dim] 'mal add --type task --status pending' [/]")
        return

    for t in tasks:
        icon = "" if t.get("status") == "done" else ""
        console.print(f"{icon} [bold]{t['summary']}[/] [dim]({t['id']})[/]")
        console.print(f"   [dim]{t['timestamp']}[/]")


def _fetch_tasks(status=None):
    """Helper: Fetch tasks from storage ( EventIndex)"""
    import os

    #
    use_event_index = os.getenv("DIMCAUSE_USE_EVENT_INDEX", "true").lower() == "true"

    if use_event_index:
        return _fetch_tasks_via_event_index(status)
    else:
        return _fetch_tasks_legacy(status)


def _fetch_tasks_via_event_index(status=None):
    """EventIndex  ()"""
    from dimcause.core.event_index import EventIndex

    try:
        event_index = EventIndex()

        #
        results = event_index.query(
            type="task",
            status=status,
            limit=1000,  #  1000
        )

        tasks = []
        for row in results:
            tasks.append(
                {
                    "id": row["id"],
                    "summary": row.get("summary", "Unnamed task"),
                    "status": row.get("status", "active"),
                    "timestamp": row.get("timestamp", ""),
                    "date": row.get("date", ""),
                    "job_id": row.get("job_id", ""),
                }
            )

        return tasks

    except Exception as e:
        console.print(f"[yellow] EventIndex : {e}[/]")
        console.print("[dim]:  `mal index update` [/]")
        return []


def _fetch_tasks_legacy(status=None):
    """indexer  (Fallback)"""
    from dimcause.core.indexer import query_index

    try:
        results = query_index(
            days=365,  #
            type="task",
            status=status,
        )

        tasks = []
        for row in results:
            #  path  id (SQLite  id )
            raw_path = row.get("path", "")
            task_id = raw_path.split("/")[-1].replace(".md", "") if raw_path else "unknown"

            tasks.append(
                {
                    "id": task_id,
                    "summary": row.get("description", "")[:50] or "Unnamed task",
                    "status": row.get("status", "pending"),
                    "timestamp": row.get("date", ""),
                }
            )

        return sorted(tasks, key=lambda x: x.get("timestamp", ""), reverse=True)

    except Exception as e:
        # Fallback:
        console.print(f"[yellow] : {e}[/]")
        console.print("[dim]:  `mal index update` [/]")
        return []


@app.command()
def sanitize(
    file: str = typer.Argument(..., help="File to sanitize / 文件路径"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show changes without modifying / 仅显示变更"
    ),
    save: bool = typer.Option(True, "--save/--no-save", help="Save changes to file /保存更改"),
):
    """
    Remove sensitive info (secrets) from a file.
    移除文件中的敏感信息 (密钥/Token)。

    [bold cyan]用法: dimc sanitize FILE [OPTIONS][/]

    Examples:
        dimc sanitize config.py --dry-run
        dimc sanitize .env
    """
    if hasattr(file, "default"):
        file = file.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    if hasattr(save, "default"):
        save = save.default
    from pathlib import Path

    from dimcause.utils.security import sanitize_file

    target = Path(file)

    if target.is_file():
        result = sanitize_file(str(target), dry_run=dry_run)
        _print_sanitize_result(result, dry_run)
    elif target.is_dir():
        #
        total_matches = 0
        for filepath in target.rglob("*"):
            if filepath.is_file() and filepath.suffix in [
                ".md",
                ".py",
                ".txt",
                ".json",
                ".yaml",
                ".yml",
                ".env",
            ]:
                result = sanitize_file(str(filepath), dry_run=dry_run)
                if result.get("matches", 0) > 0:
                    _print_sanitize_result(result, dry_run)
                    total_matches += result["matches"]

        if total_matches == 0:
            console.print("[green] [/]")
        else:
            console.print(f"\n[yellow] {total_matches} [/]")
            if dry_run:
                console.print("[dim] --apply [/]")
    else:
        console.print(f"[red] : {file}[/]")
        raise typer.Exit(1)


@app.command()
def scan(
    path: str = typer.Argument(".", help="Directory or file to scan / 扫描路径"),
    smell: bool = typer.Option(False, "--smell", "-s", help="Detect code smells (Python AST)"),
    circular: bool = typer.Option(False, "--circular", "-c", help="Detect circular dependencies"),
    arch_rules: str = typer.Option(
        None, "--arch-rules", help="Path to architecture rules YAML file"
    ),
    trace: bool = typer.Option(
        False, "--trace", "-t", help="Check document-code traceability (untraced code audit)"
    ),
    since: str = typer.Option("HEAD~10", "--since", help="Git commit range for trace check"),
):
    """
    Scan directory for sensitive information or code smells.
    扫描目录中的敏感信息或代码反模式。

    [bold cyan]用法: dimc scan [PATH] [--smell] [--circular] [--arch-rules=RULES.YAML] [--trace][/]

    Examples:
        dimc scan .
        dimc scan src/
        dimc scan src/ --smell
        dimc scan src/ --circular
        dimc scan src/ --arch-rules=dimc-arch.yaml
        dimc scan src/ --trace --since=HEAD~5
    """
    if hasattr(path, "default"):
        path = path.default
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        console.print(f"[red]Error: {path}[/]")
        raise typer.Exit(1)

    # Code Smell 模式
    if smell:
        from dimcause.utils.code_smell import CodeSmellDetector

        console.print(Panel.fit("[bold yellow]Code Smell Detection[/]", border_style="yellow"))

        detector = CodeSmellDetector()

        if target.is_file():
            issues = detector.detect_file(target)
        else:
            issues = detector.detect_directory(target)

        if not issues:
            console.print("\n[green]✓ No code smells detected[/]")
            return

        # 按文件分组输出
        from collections import defaultdict

        by_file = defaultdict(list)
        for issue in issues:
            by_file[issue.file_path].append(issue)

        total = len(issues)
        console.print(f"\n[yellow]⚠️  Code Smells: {total}[/]")

        for file_path, file_issues in by_file.items():
            rel_path = Path(file_path).relative_to(target) if target.is_dir() else file_path
            console.print(f"\n[cyan]{rel_path}[/]")
            for issue in file_issues:
                severity_color = (
                    "red"
                    if issue.severity == "P0"
                    else "yellow"
                    if issue.severity == "P1"
                    else "dim"
                )
                console.print(
                    f"  [{severity_color}]{issue.severity}[/{severity_color}] {issue.rule_id} (line {issue.line_number})"
                )
                if issue.message:
                    console.print(f"    {issue.message}")

        return

    # Circular Dependency Detection
    if circular:
        from dimcause.analyzers import CircularDepDetector
        from dimcause.extractors.ast_analyzer import build_code_dependency_graph

        console.print(
            Panel.fit("[bold magenta]Circular Dependency Detection[/]", border_style="magenta")
        )

        all_deps = []
        py_files = (
            list(target.rglob("*.py"))
            if target.is_dir()
            else ([target] if target.suffix == ".py" else [])
        )

        for py_file in py_files:
            try:
                code = py_file.read_text(encoding="utf-8")
                result = build_code_dependency_graph(str(py_file), code, "python")
                all_deps.extend(result.get("dependencies", []))
            except Exception as e:
                logger.warning(f"Failed to analyze {py_file}: {e}")

        detector = CircularDepDetector()
        for source, dep_target, dep_type in all_deps:
            if dep_type == "imports":
                detector.add_dependency(source, dep_target)

        circular_deps = detector.detect()

        if not circular_deps:
            console.print("\n[green]✓ No circular dependencies detected[/]")
            return

        console.print(f"\n[red]⚠️  Circular Dependencies: {len(circular_deps)}[/]")
        for dep in circular_deps:
            console.print(f"  [red]{dep}[/]")
        return

    # Architecture Validation
    if arch_rules:
        from dimcause.analyzers import ArchitectureValidator
        from dimcause.extractors.ast_analyzer import build_code_dependency_graph

        console.print(Panel.fit("[bold cyan]Architecture Validation[/]", border_style="cyan"))

        validator = ArchitectureValidator(arch_rules)

        all_deps = []
        py_files = (
            list(target.rglob("*.py"))
            if target.is_dir()
            else ([target] if target.suffix == ".py" else [])
        )

        for py_file in py_files:
            try:
                code = py_file.read_text(encoding="utf-8")
                result = build_code_dependency_graph(str(py_file), code, "python")
                all_deps.extend(result.get("dependencies", []))
            except Exception as e:
                logger.warning(f"Failed to analyze {py_file}: {e}")

        violations = validator.validate(all_deps)

        if not violations:
            console.print("\n[green]✓ Architecture constraints satisfied[/]")
            return

        console.print(f"\n[red]⚠️  Architecture Violations: {len(violations)}[/]")
        for v in violations:
            console.print(f"  [red]{v.message}[/]")
        return

    # Document Trace Check
    if trace:
        from dimcause.audit.checks.trace import DocumentTraceChecker

        console.print(Panel.fit("[bold green]Document Traceability Check[/]", border_style="green"))

        checker = DocumentTraceChecker()

        issues = checker.check_untraced_code(str(target), since=since)

        if not issues:
            console.print("\n[green]✓ All code changes are traced with decisions[/]")
            return

        console.print(f"\n[yellow]⚠️  Untraced Code: {len(issues)}[/]")
        console.print("\n[yellow]These code changes have no corresponding Decision/Timeline:[/]")

        for issue in issues:
            console.print(
                f"  [red]{issue.symbol.file_path}[/red]:{issue.symbol.line_start} {issue.symbol.symbol_name} ({issue.symbol.symbol_type})"
            )
            console.print(f"    {issue.message}")

        console.print(
            f"\n[dim]Trace coverage: {checker.get_trace_coverage_report(issues)['coverage']}[/dim]"
        )
        return

    # 默认：敏感信息检测模式
    from dimcause.utils.security import detect_sensitive

    console.print(Panel.fit("[bold blue]Sensitive Info Detection[/]", border_style="blue"))

    total_files = 0
    total_matches = 0

    patterns_to_scan = ["*.md", "*.py", "*.txt", "*.json", "*.yaml", "*.yml", "*.env", "*.sh"]

    for pattern in patterns_to_scan:
        for filepath in target.rglob(pattern):
            if filepath.is_file() and ".git" not in str(filepath):
                total_files += 1
                try:
                    content = filepath.read_text(encoding="utf-8")
                    matches = detect_sensitive(content)
                    if matches:
                        console.print(f"\n[yellow] {filepath.relative_to(target)}[/]")
                        for m in matches:
                            preview = (
                                m.original[:30] + "..." if len(m.original) > 30 else m.original
                            )
                            console.print(f"   - {m.pattern_name}: [dim]{preview}[/]")
                        total_matches += len(matches)
                except Exception:
                    pass

    console.print(f"\n: {total_files} ")

    if total_matches > 0:
        console.print(f"[yellow] {total_matches} [/]")
        console.print("[dim] 'dimc sanitize <path> --apply' [/]")
    else:
        console.print("[green] [/]")


def _display_trace_results(query: str, results: dict):
    """trace  ()"""
    console.print(Panel.fit(f"[bold blue] : {query}[/]", border_style="blue"))

    if results["definitions"]:
        console.print(f"\n[bold green] Definitions ({len(results['definitions'])}):[/]")
        for d in results["definitions"]:
            path = d.get("file_path", "unknown")
            name = d.get("name", "unknown")
            dtype = d.get("type", "unknown")
            loc = f"{path}:{d.get('line_start', '?')}"
            console.print(f"    [bold]{name}[/] ({dtype})")
            console.print(f"     [dim]{loc}[/]")

    if results["references"]:
        console.print(f"\n[bold yellow] References ({len(results['references'])}):[/]")
        by_file = {}
        for ref in results["references"]:
            f = ref["source_file"]
            if f not in by_file:
                by_file[f] = []
            by_file[f].append(ref)
        for f, refs in by_file.items():
            console.print(f"    [bold]{f}[/]")
            unique_refs = {(r["module_name"], r.get("line_number", "?")): r for r in refs}.values()
            for r in unique_refs:
                mod = r["module_name"]
                line = r.get("line_number", "?")
                console.print(f"       imports [cyan]{mod}[/] at line {line}")


def _print_sanitize_result(result: dict, dry_run: bool):
    """"""
    if result.get("error"):
        console.print(f"[red] {result['error']}[/]")
        return

    if result["matches"] == 0:
        return

    filepath = result["file"]
    console.print(f"\n[yellow] {filepath}[/]")
    console.print(f"    {result['matches']} :")
    for detail in result["details"]:
        console.print(f"   - {detail['type']}: [dim]{detail['preview']}[/]")

    if not dry_run and result.get("sanitized"):
        console.print("   [green] [/]")


# ===  ===


def _create_daily_log(log_type: str):
    """
    创建每日日志 (支持 Hex 序列与 YAML 头)
    """
    from dimcause.utils.state import get_root_dir, resolve_session_path

    try:
        # Resolve path based on Architecture V6.0 (Session-Centric)
        log_file, seq_id = resolve_session_path(log_type)
    except Exception as e:
        console.print(f"[red]Failed to resolve log path: {e}[/]")
        return None

    if log_file.exists() and log_file.stat().st_size > 0:
        console.print(f"[yellow]Log already exists: {log_file.relative_to(get_root_dir())}[/]")
        return log_file

    # Ensure parent dir exists (e.g. 2026/02-14)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Calculate session ID: YYYY-MM-DD-SEQ
    # Note: We use the directory's date, not strictly "today" if it's a cross-midnight session
    session_date = log_file.parent.name  # 02-14
    session_year = log_file.parent.parent.name  # 2026
    full_date = f"{session_year}-{session_date}"
    session_id = f"{full_date}-{seq_id}"

    template = _get_daily_template(log_type, full_date, session_id)
    log_file.write_text(template, encoding="utf-8")
    console.print(f"[green]Created {log_type} log: {log_file.relative_to(get_root_dir())}[/]")
    return log_file


def _create_job_log(job_id: str, log_type: str, job_dir: Optional[Path] = None):
    """Job"""
    if job_dir:
        # Use existing directory (cross-day support)
        pass
    else:
        today_dir = get_today_dir()
        job_dir = today_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = "job-start.md" if log_type == "start" else "job-end.md"
    log_file = job_dir / filename
    if log_file.exists() and log_type == "start":
        console.print(f"[yellow]: {job_id}[/]")
        return

    date_str = get_today_str()
    template = _get_job_template(log_type, job_id, date_str)
    log_file.write_text(template, encoding="utf-8")


def _extract_carryover_from_last_session() -> dict:
    """
    从上一个 session 的 end.md 中提取遗留任务和明日开工指南。
    返回 dict: { 'goals': str, 'tasks': str, 'notes': str }
    """
    from dimcause.utils.state import get_all_recent_sessions

    result = {"goals": "", "tasks": "", "notes": ""}

    try:
        # 遍历所有近期 session，找到最近一个有 end.md 的已关闭 session
        # （跳过刚创建的当前 session，因为它的 end.md 还不存在）
        all_sessions = get_all_recent_sessions(lookback_days=7)
        last = None
        for s in all_sessions:
            if s.end_file.exists():
                last = s
                break

        if not last:
            return result

        content = last.end_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # 提取各段落
        sections = {}
        current_section = None
        current_lines = []

        for line in lines:
            # 检测二级标题
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = current_lines
                current_section = line.strip()
                current_lines = []
            elif current_section:
                current_lines.append(line)

        # 最后一个 section
        if current_section:
            sections[current_section] = current_lines

        # 提取遗留问题 → 今日目标
        for key, val in sections.items():
            if "遗留问题" in key or "Legacy" in key:
                goal_lines = [
                    line for line in val if line.strip() and not line.strip().startswith("---")
                ]
                if goal_lines:
                    result["goals"] = "\n".join(
                        f"> {line.strip()}" for line in goal_lines[:5] if line.strip()
                    )
                break

        # 提取明日开工指南 → 任务分解（仅提取 ### 优先级 子段）
        for key, val in sections.items():
            if "明日开工" in key or "开工指南" in key:
                task_items = []
                in_priority_section = False
                for line in val:
                    stripped = line.strip()
                    # 遇到 ### 子标题时检查是否是优先级段
                    if stripped.startswith("### "):
                        if "优先级" in stripped or "Priority" in stripped:
                            in_priority_section = True
                        else:
                            in_priority_section = False
                        continue
                    # 跳过代码块 (```)
                    if stripped.startswith("```"):
                        in_priority_section = False
                        continue
                    # 只在优先级段或顶层提取
                    if not in_priority_section and stripped.startswith(
                        ("1.", "2.", "3.", "4.", "5.")
                    ):
                        # 过滤掉纯文件路径行 (如 "1. docs/logs/..." 或 "1. src/...")
                        task_text = (
                            stripped.split(".", 1)[1].strip() if "." in stripped else stripped
                        )
                        if task_text.startswith(("docs/", "src/", ".agent/", "tests/")):
                            continue
                        task_items.append(f"- [ ] {task_text}")
                    elif in_priority_section and stripped.startswith(
                        ("1.", "2.", "3.", "4.", "5.")
                    ):
                        task_text = (
                            stripped.split(".", 1)[1].strip() if "." in stripped else stripped
                        )
                        task_items.append(f"- [ ] {task_text}")
                    elif stripped.startswith("- ") or stripped.startswith("* "):
                        task_text = stripped[2:]
                        if task_text.startswith(("docs/", "src/", ".agent/", "tests/")):
                            continue
                        task_items.append(f"- [ ] {task_text}")
                if task_items:
                    result["tasks"] = "\n".join(task_items)
                break

        # 提取任务状态表中未完成项 → 追加到任务分解
        for key, val in sections.items():
            if "任务状态" in key or "Task Status" in key:
                extra_tasks = []
                for line in val:
                    # 寻找标记为 ❌ 或 📝 的未完成任务行
                    if "❌" in line or "📝" in line:
                        # 解析 markdown 表格行: | 任务 | 描述 | 状态 | 下一步 |
                        parts = [p.strip() for p in line.split("|") if p.strip()]
                        if len(parts) >= 2:
                            task_name = parts[0]
                            task_desc = parts[1] if len(parts) > 1 else ""
                            extra_tasks.append(f"- [ ] {task_name}: {task_desc}")
                if extra_tasks:
                    if result["tasks"]:
                        result["tasks"] += "\n" + "\n".join(extra_tasks)
                    else:
                        result["tasks"] = "\n".join(extra_tasks)
                break

        # 主管备注: 上一 session 的代码断点
        for key, val in sections.items():
            if "代码现状" in key or "Code Status" in key:
                note_lines = [
                    line
                    for line in val
                    if line.strip() and line.strip().startswith(("####", "**需要"))
                ]
                if note_lines:
                    result["notes"] = "\n".join(f"- {line.strip()}" for line in note_lines[:3])
                break

    except Exception as e:
        # 静默失败，不影响 start.md 生成
        console.print(f"[dim]上下文提取失败 (非阻塞): {e}[/]")

    return result


def _get_daily_template(log_type: str, date_str: str, session_id: str) -> str:
    """
    获取日志模板 (YAML Frontmatter + ISO Time)
    """
    from datetime import datetime

    iso_time = datetime.now().astimezone().isoformat()

    if log_type == "start":
        # 3. Context Restoration (RFC-002)

        recent_sessions = get_all_recent_sessions(lookback_days=3)
        context_lines = []

        # Filter out current session if it somehow appears (unlikely in start)
        for s in recent_sessions:
            # Skip if it's the session we are creating (check date/seq if possible, but session_id format differs)
            # session_id is YYYY-MM-DD-SEQ
            if f"{s.date_path.parent.name}-{s.date_path.name}-{s.seq}" == session_id:
                continue

            status_icon = "🟢" if "Active" in s.summary else "🔴"
            context_lines.append(
                f"  - {status_icon} **{s.date_path.name} {s.seq}** (Agent: {s.agent}): {s.summary}"
            )

        context_str = (
            "\n".join(context_lines[0:5]) if context_lines else "  - No recent sessions found."
        )

        # 4. 从上一 session 提取遗留任务
        carryover = _extract_carryover_from_last_session()
        goals_str = carryover["goals"] if carryover["goals"] else "> (无遗留目标，请手动填写)"
        tasks_str = carryover["tasks"] if carryover["tasks"] else "- [ ] (请填写今日任务)"
        notes_str = carryover["notes"] if carryover["notes"] else "- (无自动备注)"

        return f'''---
id: "{session_id}"
type: session-start
created_at: "{iso_time}"
date: "{date_str}"
agent: "{get_config().agent_id}"
status: active
supervisor_status: "Planning"
---

# ☀️ 会话开始: {date_str} (会话 {session_id.split("-")[-1]})

## 🧠 上下文 (Context)
- **Recent Sessions**:
{context_str}

## 🎯 今日目标 (从上一 Session 遗留问题自动恢复)
{goals_str}

## 📋 任务分解 (从上一 Session 明日开工指南自动恢复)
{tasks_str}

## 📝 主管备注 (自动提取的代码断点)
{notes_str}
'''
    else:
        # Session End
        return f'''---
id: "{session_id}"
type: session-end
created_at: "{iso_time}"
date: "{date_str}"
status: done
description: "会话总结"
tags: []
---

# 🌙 会话结束: {date_str} (会话 {session_id.split("-")[-1]})

## 📅 今日成果 (Achievements)

### 1.
-

## 📋 任务状态 (Task Status)

| 任务 ID | 描述 | 状态 | 下一步 |
|:---|:---|:---|:---|
| | | | |

## ⭐ 代码现状 (Code Status)

## ✅ 验收标准 (Acceptance Criteria)

## 🧱 遗留问题 (Legacy Issues)

## 🚀 明日开工指南 (Next Session Guide)

### 优先级
1.
2.
3.

'''


def _get_job_template(log_type: str, job_id: str, date_str: str) -> str:
    if log_type == "start":
        return f'''---
type: job-start
job_id: "{job_id}"
date: "{date_str}"
status: active
---

#  Job: {job_id}

## Goal
>

## Approach
-

## Notes
-
'''
    else:
        return f'''---
type: job-end
job_id: "{job_id}"
date: "{date_str}"
status: done
description: ""
tags: []
---

#  Job Complete: {job_id}

## Summary
>

## Completed
-

## []
-

## Next Steps
-
'''


@app.command()
def init(
    path: str = typer.Argument(None, help="Project path / 项目路径 (Default: current dir)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force overwrite / 强制覆盖"),
):
    """
    Initialize Dimcause configuration.
    初始化 Dimcause 配置。

    [bold cyan]用法: dimc init [PATH] [OPTIONS][/]

    Examples:
        dimc init
        dimc init --force
    """
    from rich.prompt import Confirm

    # Fix for interactive menu
    if hasattr(path, "default"):
        path = path.default
    if hasattr(force, "default"):
        force = force.default

    target = Path(path).resolve()
    config_file = target / ".logger-config"

    console.print(
        Panel.fit("[bold blue]⚙️ Dimcause Initialization / 初始化[/]", border_style="blue")
    )

    #
    if config_file.exists() and not force:
        console.print(f"[yellow] : {target}[/]")
        if not Confirm.ask("?", default=False):
            raise typer.Exit(0)

    console.print(f"\n[blue]: {target}[/]\n")

    #
    project_name = Prompt.ask("", default=target.name)
    timezone = Prompt.ask("", default="Asia/Shanghai")

    #
    logs_location = Prompt.ask(
        "", choices=["docs/logs", "logs", ".dimcause/logs"], default="docs/logs"
    )

    #  Git
    enable_git = Confirm.ask(" Git ?", default=True)

    #
    enable_clipboard = Confirm.ask("?", default=True)

    #
    config = {
        "project_name": project_name,
        "timezone": timezone,
        "logs_dir": logs_location,
        "git_integration": enable_git,
        "clipboard_capture": enable_clipboard,
        "version": "4.0",
    }

    import json

    config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    #
    logs_dir = target / logs_location
    logs_dir.mkdir(parents=True, exist_ok=True)

    #  .agent
    agent_dir = target / ".agent"
    agent_dir.mkdir(exist_ok=True)
    (agent_dir / "workflows").mkdir(exist_ok=True)

    #  INDEX.md
    index_file = logs_dir / "INDEX.md"
    if not index_file.exists():
        index_file.write_text(
            """#  Active Context (Last 7 Days)
> High-resolution index for immediate context.

| Date | Job | Status | Summary | Tags |
|------|-----|--------|---------|------|

---
*For older history, see [INDEX_ARCHIVE.md](INDEX_ARCHIVE.md)*
""",
            encoding="utf-8",
        )

    console.print("\n[green] ![/]")
    console.print(f"   : {config_file.relative_to(target)}")
    console.print(f"   : {logs_location}/")
    console.print("   : .agent/workflows/")
    console.print("\n[dim]:[/]")
    console.print("   1.  [bold]dimc up[/] ")
    console.print("   2.  [bold]dimc capture[/] ")
    # === Zero-Config Enhancement: Auto-generate .env ===
    env_file = target / ".env"
    if not env_file.exists():
        console.print("\n[dim]Creating .env template for API keys...[/]")
        env_content = """# DIMCAUSE Configuration (Zero-Config)
# Uncomment and fill in the keys you need.

# --- LLM Providers (Pick one or more) ---
# DEEPSEEK_API_KEY=<你的本地密钥>
# OPENAI_API_KEY=<你的本地密钥>
# ANTHROPIC_API_KEY=<你的本地密钥>

# --- Optional Settings ---
# DIMCAUSE_TZ=Asia/Shanghai
# DIMCAUSE_ROOT=.
"""
        env_file.write_text(env_content, encoding="utf-8")
        console.print("[green]Created .env file. Please edit it to add your API keys.[/]")

    console.print(f"\n[bold green]Initialized Dimcause project in {target}[/]")
    console.print("[dim]Run 'dimc up' to begin.[/]")


@app.command()
def stats(
    days: int = typer.Option(7, "--days", "-d", help="Days to analyze / 分析天数"),
    model: str = typer.Option(None, "--model", "-m", help="Filter by model / 模型过滤"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show details / 显示详情"),
):
    """
    Show token usage statistics.
    显示 Token 使用统计。

    [bold cyan]用法: dimc stats [OPTIONS][/]

    Examples:
        dimc stats
        dimc stats --days 30
    """
    if hasattr(days, "default"):
        days = days.default
    if hasattr(verbose, "default"):
        verbose = verbose.default
    if hasattr(model, "default"):
        model = model.default
    from dimcause.core.stats import get_stats, get_token_stats

    console.print(Panel.fit("[bold blue] [/]", border_style="blue"))

    #
    try:
        basic_stats = get_stats()

        console.print("\n[bold] [/]")
        console.print(f"   : {basic_stats.get('total_logs', 0)}")
        console.print(f"   : {basic_stats.get('active_days', 0)}")
        console.print(f"   : {basic_stats.get('completed_jobs', 0)}")

        if basic_stats.get("recent_activity"):
            console.print("\n[bold] [/]")
            for item in basic_stats["recent_activity"][:5]:
                console.print(f"   - {item}")
    except Exception as e:
        console.print(f"[yellow] : {e}[/]")

    # Token
    try:
        token_stats = get_token_stats()

        console.print("\n[bold] Token [/]")
        console.print(f"   : {token_stats.get('today', 0):,} tokens")
        console.print(f"   : {token_stats.get('week', 0):,} tokens")
        console.print(f"   : {token_stats.get('month', 0):,} tokens")

        if token_stats.get("by_model"):
            console.print("\n[bold] [/]")
            for model, count in token_stats["by_model"].items():
                console.print(f"   {model}: {count:,} tokens")
    except Exception:
        console.print("\n[dim]Token  ()[/]")

    console.print("\n[dim]: Token [/]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query / 搜索关键词"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results / 最大结果数"),
    model: str = typer.Option(None, "--model", "-m", help="Filter by model / 模型过滤"),
    source: str = typer.Option(
        None,
        "--source",
        "-s",
        help="UNIX source filter: events, code, docs / UNIX 源过滤",
    ),
):
    """
    Search usage history.
    搜索使用记录。

    [bold cyan]用法: dimc search QUERY [OPTIONS][/]

    Examples:
        dimc search "refactor"
        dimc search "error" --limit 20
    """
    if hasattr(query, "default"):
        query = query.default
    if hasattr(limit, "default"):
        limit = limit.default
    if hasattr(model, "default"):
        model = model.default
    if hasattr(source, "default"):
        source = source.default

    source = _normalize_search_source(source)

    results = _do_search(query, mode="hybrid", top_k=limit, use_reranker=False, source=source)

    if not results:
        return

    # Interactive Loop
    while True:
        choice = typer.prompt(
            "\n[?] Enter # to view, 't #' to trace, 'o #' to open, or 'q' to quit",
            default="q",
            show_default=False,
        )

        if choice.lower() == "q":
            break

        try:
            cmd = choice.split()
            idx = int(cmd[-1])
            if idx < 1 or idx > len(results):
                console.print(f"[red]Invalid index: {idx}[/]")
                continue

            event = results[idx - 1]

            if choice.startswith("t "):
                # Trace
                trace_target = _search_result_trace_target(event)
                console.print(f"\n[blue]Tracing {trace_target}...[/]")
                trace(query=trace_target, limit=50)
            elif choice.startswith("o "):
                # Open
                target_path = _search_result_open_path(event)
                if not target_path:
                    console.print("[yellow]This result does not have an openable path.[/]")
                    continue
                console.print(f"\n[blue]Opening {target_path}...[/]")
                typer.launch(target_path)
            else:
                # View (Default)
                _view_search_result(event)

        except (ValueError, IndexError):
            console.print("[red]Invalid input. Use '1', 't 1', 'o 1', or 'q'[/]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")


def _do_search(
    query: str,
    mode: str = "hybrid",
    top_k: int = 10,
    use_reranker: bool = False,
    source: Optional[str] = None,
):
    """"""
    from rich.table import Table

    mode_label = _search_mode_label(mode, source)
    console.print(Panel.fit(f"[bold blue] : {query}[/]", border_style="blue"))
    rerank_hint = " | Reranker: 启用" if use_reranker else ""
    console.print(f"[dim]: {mode_label} | Top-K: {top_k}{rerank_hint}[/]\n")

    try:
        from dimcause.search import SearchEngine, build_search_result_view
        from dimcause.storage import MarkdownStore, VectorStore

        data_dir = os.path.expanduser("~/.dimcause")
        markdown_store = MarkdownStore(base_dir=f"{data_dir}/events")
        # 使用 SQLite-vec (默认 ~/.dimcause/index.db)，不再用旧 ChromaDB 路径
        vector_store = VectorStore()

        engine = SearchEngine(markdown_store=markdown_store, vector_store=vector_store)

        results = _execute_search_request(
            engine=engine,
            query=query,
            mode=mode,
            top_k=top_k,
            use_reranker=use_reranker,
            source=source,
        )

        if not results:
            console.print("[yellow][/]")

            # Smart fallback: try code tracing
            console.print(f"\n[blue] : dimc trace '{query}' ...[/]")
            try:
                from dimcause.core.code_indexer import trace_code

                code_results = trace_code(query)
                if code_results["definitions"] or code_results["references"]:
                    _display_trace_results(query, code_results)
                    return []
            except Exception:
                pass

            console.print("[dim]:  'dimc index'  'dimc daemon start'[/]")
            return []

        #
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", width=3)
        table.add_column("", width=10)
        table.add_column("", width=8)
        table.add_column("", width=28)
        table.add_column("", width=38)
        table.add_column("", width=12)

        for i, event in enumerate(results, 1):
            result_view = build_search_result_view(event)
            event_type = getattr(event.type, "value", str(event.type))
            source_label = result_view.source_label
            location_label = _truncate_search_cell(result_view.location_label, 28)
            summary = _truncate_search_cell(result_view.summary_label, 38)
            timestamp = (
                event.timestamp.strftime("%Y-%m-%d")
                if hasattr(event.timestamp, "strftime")
                else str(event.timestamp)[:10]
            )
            table.add_row(str(i), event_type, source_label, location_label, summary, timestamp)

        console.print(table)
        console.print(f"\n[dim] {len(results)} [/]")

        return results

    except ImportError as e:
        console.print(f"[red] : {e}[/]")
        console.print("[dim]: pip install chromadb[/]")
        return []
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        return []


def _search_result_open_path(event) -> Optional[str]:
    from dimcause.search import build_search_result_view

    return build_search_result_view(event).open_path


def _search_result_trace_target(event) -> str:
    from dimcause.search import build_search_result_view

    return build_search_result_view(event).trace_target


def _search_result_source_label(event) -> str:
    from dimcause.search import build_search_result_view

    return build_search_result_view(event).source_label


def _search_result_location_label(event) -> str:
    from dimcause.search import build_search_result_view

    return build_search_result_view(event).location_label


def _search_result_summary_label(event) -> str:
    from dimcause.search import build_search_result_view

    return build_search_result_view(event).summary_label


def _truncate_search_cell(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: max(width - 3, 0)] + "..."


def _normalize_search_source(source: Optional[str]) -> Optional[str]:
    if source is None:
        return None

    normalized = source.strip().lower()
    if not normalized:
        return None
    if normalized not in SEARCH_SOURCE_CHOICES:
        choices = ", ".join(sorted(SEARCH_SOURCE_CHOICES))
        console.print(f"[red]Invalid --source: {source}. Expected one of: {choices}[/]")
        raise typer.Exit(1)
    return normalized


def _search_mode_label(mode: str, source: Optional[str]) -> str:
    if source:
        return f"unix[{source}]"
    return mode


def _execute_search_request(
    engine, query: str, mode: str, top_k: int, use_reranker: bool, source: Optional[str]
):
    if source:
        return engine._unix_search(query, top_k, sources=(source,))
    return engine.search(query=query, mode=mode, top_k=top_k, use_reranker=use_reranker)


def _is_synthetic_search_result(event) -> bool:
    from dimcause.search import build_search_result_view

    return build_search_result_view(event).synthetic


def _view_search_result(event) -> None:
    from dimcause.search import build_search_result_view

    result_view = build_search_result_view(event)
    if not _is_synthetic_search_result(event):
        console.print(f"\n[blue]Viewing {event.id}...[/]")
        view(event_id=event.id)
        return

    body = [
        f"[bold]Source:[/] {result_view.source_label}",
        f"[bold]Path:[/] {result_view.open_path or '(unknown)'}",
    ]
    if result_view.line_no:
        body.append(f"[bold]Line:[/] {result_view.line_no}")
    body.extend(
        [
            "",
            "[bold]Summary:[/]",
            result_view.summary_label or "(No summary)",
        ]
    )
    if getattr(event, "content", None):
        body.extend(["", "[bold]Snippet:[/]", event.content])

    console.print(Panel("\n".join(body), title=event.id, border_style="blue"))


@app.command()
def daemon(
    action: str = typer.Argument("status", help=": start, stop, status"),
    background: bool = typer.Option(True, "--background/--foreground", "-b/-f", help=""),
):
    """
    Manage the Dimcause IDE Daemon.
    管理 Dimcause IDE 守护进程。

    Examples:
        dimc daemon start
        dimc daemon status
        dimc daemon stop
    """
    if hasattr(action, "default"):
        action = action.default

    from dimcause.daemon.process import process_manager

    # Fix for interactive menu
    if hasattr(background, "default"):
        background = background.default

    console.print(Panel.fit("[bold blue] Dimcause Daemon - IDE [/]", border_style="blue"))

    if action == "start":
        if background:
            process_manager.start_daemon()
        else:
            #
            try:
                from dimcause.daemon.manager import create_daemon

                console.print("[yellow]  Daemon (Foreground)...[/]")
                console.print("[dim] Ctrl+C [/]\n")
                d = create_daemon()
                d.run()
            except Exception as e:
                console.print(f"[red] Daemon : {e}[/]")
                raise typer.Exit(1) from None

    elif action == "stop":
        process_manager.stop_daemon()

    elif action == "status":
        is_running = process_manager.is_running()
        pid = process_manager.get_pid()

        status_msg = f"[green]Running (PID: {pid})[/]" if is_running else "[red]Stopped[/]"
        console.print(f"\n[bold]Status:[/] {status_msg}")

        if is_running:
            console.print("[dim]Use 'dimc daemon stop' to stop service[/]")
        else:
            console.print("[dim]Use 'dimc daemon start' to start service[/]")

    else:
        # _run_once() is local, we need to invoke it inside
        # But wait, imports are inside function.
        # Moving imports to top level makes testing easier.
        pass


# Import at module level for easier mocking?
# Or just keep it local but understand patch target.
# If `from dimcause.audit.engine import AuditEngine` is inside `audit()`, patching `mal.audit.engine.AuditEngine` works IF it's not already imported.
# But `mal.cli` might have been imported before testing?
# Let's import at top of file (or lazily but globally).


@app.command()
def audit(
    path: str = typer.Argument(".", help="Path to audit / 审计路径"),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues / 自动修复"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch mode / 监听模式"),
    security_strict: bool = typer.Option(
        False, "--strict", help="Strict security mode / 严格安全模式"
    ),
    timeline: bool = typer.Option(
        False, "--timeline", help="Check timeline integrity / 检查时间线"
    ),
):
    """
    Audit code quality and security.
    审计代码质量和安全性。

    [bold cyan]用法: dimc audit [PATH] [OPTIONS][/]

    Examples:
        dimc audit .
        dimc audit src/ --fix
    """
    if hasattr(path, "default"):
        path = path.default
    if hasattr(fix, "default"):
        fix = fix.default
    if hasattr(watch, "default"):
        watch = watch.default
    if hasattr(security_strict, "default"):
        security_strict = security_strict.default
    if hasattr(timeline, "default"):
        timeline = timeline.default
    import time

    from dimcause.audit.mode import STANDARD_MODE, STRICT_MODE
    from dimcause.audit.runner import run_audit

    # Determine target files
    target_files = [Path(f) for f in [path]] if path else [Path(".")]

    # Determine Mode
    mode = STRICT_MODE if security_strict else STANDARD_MODE

    title_suffix = " (Strict Mode)" if security_strict else " (Experience Mode)"
    console.print(
        Panel.fit(f"[bold blue] Dimcause Audit Gate{title_suffix}[/]", border_style="blue")
    )

    def _run_once():
        # Execute via Runner
        result = run_audit(files=target_files, mode=mode, fix=fix, include_timeline=timeline)

        has_failure = not result.success
        print()  # Separator

        # Render Results (using raw results for now to maintain Rich formatting)
        for res in result.raw_results:
            # Determine icon and style
            if res.success:
                style = "green"
                icon = ""
            else:
                if res.is_blocking:
                    style = "red"
                    icon = ""
                else:
                    style = "yellow"
                    icon = " "

            console.print(f"[{style}]{icon} {res.check_name.upper()}: {res.message}[/]")

            # Show Details
            if not res.success or res.details:
                limit = 10
                # Timeline special handling (or just rely on details)
                if res.check_name == "timeline_integrity":
                    limit = 20

                if res.details:
                    for line in res.details[:limit]:
                        console.print(f"   [dim]{line}[/]")
                    if len(res.details) > limit:
                        console.print(f"   [dim]... and {len(res.details) - limit} more[/]")

        if has_failure:
            console.print(f"\n[red] Audit Failed (Exit Code: {result.exit_code})[/]")
            if not watch:
                raise typer.Exit(result.exit_code)
        else:
            console.print("\n[green] All Blocking Checks Passed[/]")

    if watch:
        console.print("[yellow] Watching for file changes...[/]")
        try:
            while True:
                _run_once()
                time.sleep(2)
                console.clear()
        except KeyboardInterrupt:
            console.print("[dim]Stopped watching[/]")
    else:
        _run_once()


@app.command()
def capture(
    mode: str = typer.Argument("clipboard", help="Capture mode / 模式: clipboard, export"),
    watch_dir: str = typer.Option(
        None, "--dir", "-d", help="Export directory (for export mode) / 导出目录"
    ),
):
    """
    Capture context from clipboard or external exports.
    从剪贴板或外部导出目录捕获上下文。

    [bold cyan]用法: dimc capture [MODE] [OPTIONS][/]

    Examples:
        dimc capture clipboard      # Monitor clipboard for code/text
        dimc capture export         # Monitor export directory for AI logs
    """

    # Fix for interactive menu
    if hasattr(mode, "default"):
        mode = mode.default
    if hasattr(watch_dir, "default"):
        watch_dir = watch_dir.default

    # 从 Config 获取默认导出目录
    if watch_dir is None:
        from dimcause.utils.config import get_config

        watch_dir = get_config().export_dir

    if mode == "clipboard":
        console.print("[yellow]Clipboard monitoring is not yet implemented.[/]")
        console.print("[dim]Use 'dimc capture export' to monitor export directory instead.[/]")
        raise typer.Exit(0)

    elif mode == "export":
        from dimcause.watchers.export_watcher import ExportWatcher

        console.print(Panel.fit("[bold blue] Antigravity [/]", border_style="blue"))
        console.print(f"[dim]: {watch_dir}[/]")
        console.print("[dim] Antigravity    Export [/]")
        console.print("[dim]Dimcause [/]\\n")

        watcher = ExportWatcher(watch_dir)
        try:
            watcher.start()
        except KeyboardInterrupt:
            console.print("\\n[yellow][/]")

    else:
        console.print(f"[red] : {mode}[/]")
        console.print("[dim]: clipboard, export[/]")
        raise typer.Exit(1) from None


# ===  (Phase 2 Feature) ===

template_app = typer.Typer(
    help="Manage file templates / 管理文件模板",
    short_help="Manage file templates",
)
app.add_typer(template_app, name="template")


@template_app.command("list")
def template_list():
    """
    List available templates.
    列出可用模板。

    [bold cyan]用法: dimc template list[/]

    Examples:
        dimc template list
    """
    from rich.table import Table

    from dimcause.core.templates import get_template_manager

    tm = get_template_manager()
    templates = tm.list_templates()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("", style="green")
    table.add_column("", style="dim")

    for name in templates:
        is_builtin = name in [
            "session-start",
            "session-end",
            "job-start",
            "job-end",
            "bug-report",
            "decision-log",
        ]
        kind = "" if is_builtin else ""
        table.add_row(name, kind)

    console.print(Panel.fit(f"[blue] {len(templates)} [/]", border_style="blue"))
    console.print(table)


@template_app.command("show")
def template_show(
    name: str = typer.Argument(..., help="Template name / 模板名称"),
):
    """
    Show template content.
    显示模板内容。

    [bold cyan]用法: dimc template show NAME[/]

    Examples:
        dimc template show bug_report
    """
    from rich.syntax import Syntax

    from dimcause.core.templates import get_template_manager

    tm = get_template_manager()
    try:
        content = tm.get_template(name)
        if not content:
            console.print(f"[red] : {name}[/]")
            raise typer.Exit(1)

        console.print(f"\n[bold green] : {name}[/]\n")
        console.print(Syntax(content, "markdown", theme="monokai", line_numbers=True))
    except Exception as e:
        console.print(f"[red] : {e}[/]")


@template_app.command("use")
def template_use(
    name: str = typer.Argument(..., help="Template name / 模板名称"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file / 输出文件"),
    print_stdout: bool = typer.Option(
        False, "--print", "-p", help="Print to stdout / 打印到标准输出"
    ),
):
    """
    Use a template to create a file.
    使用模板创建文件。

    [bold cyan]用法: dimc template use NAME [OPTIONS][/]

    Examples:
        dimc template use bug_report -o issue.md
    """
    if hasattr(name, "default"):
        name = name.default
    if hasattr(output, "default"):
        output = output.default
    if hasattr(print_stdout, "default"):
        print_stdout = print_stdout.default
    from dimcause.core.templates import get_template_manager

    tm = get_template_manager()

    try:
        content = tm.render(name)

        if output:
            if output.exists():
                if not Confirm.ask(f"Overwrite {output}?", default=False):
                    console.print("[yellow]Cancelled[/]")
                    raise typer.Exit(0)

            output.write_text(content, encoding="utf-8")
            console.print(f"[green]Created: {output}[/]")

        elif print_stdout:
            print(content)

        else:
            # Interactive mode
            console.print(Panel(content, title=f"Template: {name}", border_style="green"))

            if Confirm.ask("Save this content?", default=True):
                save_path = typer.prompt("Save to file", default=f"{name}.md")
                Path(save_path).write_text(content, encoding="utf-8")
                console.print(f"[green]Saved to: {save_path}[/]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1) from None


@app.command()
def history(
    target: str = typer.Argument(".", help="Target file/directory / 目标文件或目录"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max items / 最大条目数"),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Interactive mode / 交互模式"
    ),
    type: str = typer.Option(
        None, "--type", "-t", help="Filter by type / 过滤类型 (decision, git_commit)"
    ),
):
    """
    View file history (Git + Events).
    查看文件历史 (Git + 事件)。

    [bold cyan]用法: dimc history [TARGET] [OPTIONS][/]

    Examples:
        dimc history src/main.py
        dimc history . --limit 20
    """
    if hasattr(target, "default"):
        target = target.default
    if hasattr(limit, "default"):
        limit = limit.default
    if hasattr(type, "default"):
        type = type.default
    if hasattr(interactive, "default"):
        interactive = interactive.default

    from rich.table import Table

    from dimcause.core.event_index import EventIndex
    from dimcause.core.history import get_file_history

    # 1.  EventIndex
    try:
        index = EventIndex()
    except Exception:
        index = None

    # 2.
    cwd = Path.cwd()
    commits = get_file_history(target, limit=limit, event_index=index, cwd=cwd, type_filter=type)

    if not commits:
        console.print(f"[yellow]No history found for {target}[/]")
        return

    # Define icons
    ICONS = {
        "git_commit": "",
        "decision": "",
        "failed_attempt": "",
        "abandoned_idea": "",
        "ai_conversation": "",
        "reasoning": "",
        "convention": "",
        "code_change": "",
        "diagnostic": "",
        "research": "",
        "discussion": "",
        "task": "",
        "resource": "",
        "unknown": "",
    }

    # 3.
    if not limit:
        limit = 20  # Safety check

    from rich.prompt import IntPrompt

    # Interactive Loop (or run once)
    while True:
        if type:
            # Re-title if filtered
            pass

        rows = []
        for i, c in enumerate(commits, 1):
            evt_type = getattr(c, "type", "git_commit")
            icon = ICONS.get(evt_type, "")

            # Format date: MMDD or YYYYMMDD
            d_str = c.date
            try:
                # Try simple format
                if "T" in d_str:
                    d_str = d_str.split("T")[0]
            except Exception:
                pass

            summary = c.message.split("\n")[0]
            rows.append((str(i), d_str, icon, evt_type, c.author, summary, c.hash))

        # Build Table
        table = Table(show_header=True, header_style="bold magenta", box=None, expand=True)
        if hasattr(typer, "Option"):  # Check context
            pass

        if type:  # Check if interactive is requested?
            # Wait, I missed adding 'interactive' arg in previous step?
            # No, I tried but it might have failed. Let's assume passed in kwargs?
            # Actually I need to add 'interactive' param to function signature first!
            # But I can't change signature here easily.
            # Let's fix the broken code first to restore functionality, then add interactive.
            pass

        if interactive:
            table.add_column("#", style="dim", width=4)

        table.add_column("Time", style="dim", width=10, no_wrap=True)
        table.add_column("", width=2)
        table.add_column("Type", width=12)
        table.add_column("Author", style="cyan", width=10)
        table.add_column("Summary", ratio=1)
        if not interactive:
            table.add_column("ID", style="dim", width=8, overflow="ellipsis", no_wrap=True)

        for r in rows:
            # r: (i, date, icon, type, author, summary, hash)
            if interactive:
                table.add_row(r[0], r[1], r[2], r[3], r[4], r[5])
            else:
                table.add_row(r[1], r[2], r[3], r[4], r[5], r[6])

        console.print(f"\n[bold]History for {target}[/] ({len(commits)} events)")
        console.print(table)

        if not interactive:
            break

        console.print("[dim] (0 )[/]")
        choice = IntPrompt.ask("Select", default=0)
        if choice == 0:
            break

        if 1 <= choice <= len(commits):
            selected = commits[choice - 1]
            _show_history_detail(selected)
            typer.pause(info="...")
        else:
            console.print("[red][/]")
            typer.pause()


def _show_history_detail(commit):
    pass
    from rich.markdown import Markdown

    from dimcause.utils.git import run_git

    console.clear()
    console.print(
        Panel.fit(
            f"[bold]{commit.message}[/]",
            title=f"{commit.type} : {commit.hash[:8]}",
            border_style="blue",
        )
    )

    if commit.type == "git_commit":
        # Show Git Diff/Stat
        code, out, err = run_git("show", "--stat", "--patch", "--color=always", commit.hash)
        if code == 0:
            # Use pager for long output? For now just print
            # If output is too long, maybe truncate or use pydoc
            if len(out.splitlines()) > 30:
                import pydoc

                pydoc.pager(out)
            else:
                console.print(out)
        else:
            console.print(f"[red]Git Error: {err}[/]")
    else:
        # Show Event Content
        # Adaptor: commit object might have metadata or context
        if hasattr(commit, "metadata") and commit.metadata:
            # Try to construct path or content
            meta = commit.metadata
            if "markdown_path" in meta:  # Common field
                path = Path(meta["markdown_path"])
                if path.exists():
                    console.print(Markdown(path.read_text()))
                    return

            # Fallback: Print Metadata JSON
            import json

            console.print(json.dumps(meta, indent=2, ensure_ascii=False))
        else:
            console.print("[dim]No detailed content available[/]")


@app.command()
def why(
    target: str = typer.Argument(..., help="Target file/directory / 目标文件或目录"),
    max_commits: int = typer.Option(
        5, "--max-commits", "-n", help="Max commits to analyze / 分析提交数"
    ),
    time_window: int = typer.Option(7, "--window", "-w", help="Time window (days) / 时间窗口(天)"),
    explain: bool = typer.Option(
        True, "--explain/--no-explain", "-e/-E", help="Enable AI explanation / 启用 AI 解释"
    ),
    llm_provider: str = typer.Option(
        None, "--llm-provider", help="LLM Provider / LLM 提供商 (override config)"
    ),
    llm_model: str = typer.Option(
        None, "--llm-model", help="LLM Model / 模型名称 (override config)"
    ),
    lang: str = typer.Option("zh-CN", help="Output language / 输出语言 (default: zh-CN)"),
):
    """
    Explain why code is the way it is.
    解释代码为何如此 (基于历史和 AI 分析)。

    [bold cyan]用法: dimc why TARGET [OPTIONS][/]

    Examples:
        dimc why src/main.py
        dimc why src/auth/ --max-commits 10
    """
    if hasattr(target, "default"):
        target = target.default
    if hasattr(max_commits, "default"):
        max_commits = max_commits.default
    if hasattr(time_window, "default"):
        time_window = time_window.default
    if hasattr(explain, "default"):
        explain = explain.default
    if hasattr(llm_provider, "default"):
        llm_provider = llm_provider.default
    if hasattr(llm_model, "default"):
        llm_model = llm_model.default
    if hasattr(lang, "default"):
        lang = lang.default
    from pathlib import Path

    from dimcause.brain.decision_analyzer import DecisionAnalyzer
    from dimcause.core.code_indexer import trace_code

    # New Core Components
    from dimcause.core.history import get_file_history
    from dimcause.core.models import LLMConfig
    from dimcause.extractors.llm_client import LiteLLMClient

    # Resolve language
    target_lang = lang or "zh-CN"

    console.print(
        Panel(f" : [bold]{target}[/]", title="Dimcause Why (Real LLM)", border_style="blue")
    )

    # Step 1: Resolve target
    file_path = None
    is_directory = False
    directory_files = []

    if Path(target).exists():
        target_path = Path(target).absolute()
        try:
            # Use relative path for better matching in EventIndex/Git
            file_path = str(target_path.relative_to(Path.cwd()))
        except ValueError:
            file_path = str(target_path)

        if target_path.is_dir():
            is_directory = True
            # Collect files in directory (exclude hidden files and common non-code files)
            for f in target_path.rglob("*"):
                if f.is_file() and not any(
                    part.startswith(".") for part in f.parts[len(target_path.parts) :]
                ):
                    if f.suffix in [
                        ".py",
                        ".md",
                        ".mdc",
                        ".yaml",
                        ".yml",
                        ".json",
                        ".toml",
                        ".txt",
                        ".sh",
                        ".zsh",
                    ]:
                        directory_files.append(str(f))
            directory_files = sorted(directory_files)[
                :10
            ]  # Limit to 10 files to avoid overwhelming LLM
            console.print(f"[dim] Target resolved as directory: {file_path}[/]")
            console.print(f"[dim]  Found {len(directory_files)} files to analyze[/]")
        else:
            console.print(f"[dim] Target resolved as file: {file_path}[/]")
    else:
        try:
            trace_results = trace_code(target)
            if trace_results.get("definitions"):
                file_path = trace_results["definitions"][0]["file_path"]
                console.print(f"[dim] Target resolved via trace: {file_path}[/]")
        except Exception:
            pass

    if not file_path:
        console.print(f"[red] : {target}[/]")
        console.print("[dim]: [/]")
        raise typer.Exit(1) from None

    # Step 2: Get History with Context (EventIndex)
    console.print("\n[bold] Step 1: ...[/]")

    event_index = None
    if os.getenv("DIMCAUSE_USE_EVENT_INDEX", "true").lower() == "true":
        try:
            from dimcause.core.event_index import EventIndex

            event_index = EventIndex()
        except Exception:
            pass

    # Handle directory vs file
    all_commits = []
    file_commit_map = {}  # Track which files contributed which commits

    if is_directory and directory_files:
        console.print(f"[dim]Analyzing {len(directory_files)} files in directory...[/]")
        for f in directory_files:
            file_commits = get_file_history(
                f,
                limit=max_commits,
                cwd=Path.cwd(),
                event_index=event_index,
                time_window_days=time_window,
                use_causal_chain=True,
            )
            if file_commits:
                file_commit_map[f] = file_commits
                for c in file_commits:
                    # Avoid duplicates (same commit might touch multiple files)
                    if not any(existing.hash == c.hash for existing in all_commits):
                        all_commits.append(c)
        # Sort by date descending
        all_commits.sort(key=lambda c: c.date, reverse=True)
        commits = all_commits[:max_commits]

        # Show file breakdown
        console.print("\n[bold] :[/]")
        for f, fc in file_commit_map.items():
            rel_path = os.path.relpath(f, file_path)
            console.print(f"   {rel_path}: {len(fc)} commits")
    else:
        # Single file mode (original behavior)
        commits = get_file_history(
            file_path,
            limit=max_commits,
            cwd=Path.cwd(),
            event_index=event_index,
            time_window_days=time_window,
            use_causal_chain=True,
        )

    if not commits:
        console.print(f"[yellow]  {target}  Git [/]")
        raise typer.Exit(1)

    # Display History & Context
    # Display History & Context (Structured)
    console.print("\n[bold][/]")

    def _render_why_meta(commit_obj) -> None:
        meta = getattr(commit_obj, "metadata", {}) or {}

        def _render_object_projection() -> None:
            projection = meta.get("object_projection")
            if not isinstance(projection, dict):
                return

            material = projection.get("material")
            claims = projection.get("claims")
            if not isinstance(material, dict):
                return

            material_label = (
                material.get("title")
                or material.get("source_ref")
                or material.get("id")
                or "未命名材料"
            )

            first_claim = None
            if isinstance(claims, list) and claims:
                first_claim = claims[0]

            claim_statement = None
            if isinstance(first_claim, dict):
                claim_statement = first_claim.get("statement")

            console.print("   对象证据区:")
            console.print(f"     - Material: {material_label}")
            if claim_statement:
                console.print(f"     - Claim: {claim_statement}")

        if "reason" in meta:
            console.print(f"   : {meta['reason']}")
        if "solution" in meta:
            console.print(f"   : {meta['solution']}")
        if "impact" in meta:
            console.print(f"   : {meta['impact']}")
        if "what_tried" in meta:
            console.print(f"   : {meta['what_tried']}")
        if "why_failed" in meta:
            console.print(f"   : {meta['why_failed']}")
        if "error_message" in meta:
            console.print(f"   : {meta['error_message']}")
        if "duration_minutes" in meta:
            console.print(f"   : {meta['duration_minutes']} ")
        if "led_to_decision" in meta:
            console.print(f"   : {meta['led_to_decision']}")
        if "alternatives" in meta:
            console.print(f"   : {meta['alternatives']}")
        if "criteria" in meta:
            console.print(f"   : {meta['criteria']}")
        if "conclusion" in meta:
            console.print(f"   : {meta['conclusion']}")

        if not meta or all(
            key not in meta
            for key in (
                "reason",
                "solution",
                "impact",
                "what_tried",
                "why_failed",
                "error_message",
                "duration_minutes",
                "led_to_decision",
                "alternatives",
                "criteria",
                "conclusion",
            )
        ):
            console.print(f"   : {commit_obj.author}")

        _render_object_projection()

    # Group events by type
    causal_evidence = []
    decisions = []
    failed_attempts = []
    reasonings = []
    ai_conversations = []
    git_commits = []
    others = []

    for c in commits:
        evt_type = getattr(c, "type", "git_commit")
        if getattr(c, "from_causal_chain", False) and evt_type != "git_commit":
            causal_evidence.append(c)
            continue
        if evt_type == "decision":
            decisions.append(c)
        elif evt_type == "failed_attempt":
            failed_attempts.append(c)
        elif evt_type == "reasoning":
            reasonings.append(c)
        elif evt_type == "ai_conversation":
            ai_conversations.append(c)
        elif evt_type == "git_commit":
            git_commits.append(c)
        else:
            others.append(c)

    if causal_evidence:
        console.print("[bold]## 因果链证据 (Causal Chain)[/]")
        for ev in causal_evidence:
            evt_type = getattr(ev, "type", "event")
            console.print(f"\n[magenta]{ev.date}[/]  [bold][{evt_type}] {ev.message}[/]")
            _render_why_meta(ev)
        console.print("\n[bold][/]")

    # --- Section: Decisions ---
    if decisions:
        console.print("[bold]##   ( EventIndex)[/]")
        for d in decisions:
            console.print(f"\n[green]{d.date}[/]  [bold]: {d.message}[/]")
            _render_why_meta(d)
        console.print("\n[bold][/]")

    # --- Section: Failed Attempts ---
    if failed_attempts:
        console.print("[bold]##   ( EventIndex)[/]")
        for f in failed_attempts:
            console.print(f"\n[red]{f.date}[/]  [bold]: {f.message}[/]")
            _render_why_meta(f)
        console.print("\n[bold][/]")

    # --- Section: Reasoning ---
    if reasonings:
        console.print("[bold]##   ( EventIndex)[/]")
        for r in reasonings:
            console.print(f"\n[cyan]{r.date}[/]  [bold]: {r.message}[/]")
            _render_why_meta(r)

        console.print("\n[bold][/]")

    # --- Section: AI Conversations ---
    if ai_conversations:
        console.print("[bold]##   ( EventIndex)[/]")
        for a in ai_conversations:
            console.print(f"\n[blue]{a.date}[/]  [bold]AI : {a.message}[/]")
        console.print("\n[bold][/]")

    # --- Section: Others (e.g. code_change, tasks) ---
    if others:
        console.print("[bold]##  [/]")
        for o in others:
            etype = getattr(o, "type", "event")
            console.print(f"\n{o.date} [{etype}] {o.message}")
        console.print("\n[bold][/]")

    # --- Section: Git Commits ---
    console.print("[bold]##   (Git Commits)[/]")

    # Define Icons (Shared/Local) - reusing ICONS from history or timeline
    # Ideally should be global, but defining locally for safety/speed
    ICONS = {
        "git_commit": "",
        "decision": "",
        "failed_attempt": "",
        "abandoned_idea": "",
        "ai_conversation": "",
        "reasoning": "",
        "convention": "",
        "code_change": "",
        "diagnostic": "",
        "research": "",
        "discussion": "",
        "task": "",
        "resource": "",
        "unknown": "",
    }

    for commit in git_commits[:max_commits]:
        # Reuse existing display logic for git commits but without non-git types
        evt_type = getattr(commit, "type", "git_commit")
        icon = ICONS.get(evt_type, "")
        console.print(
            f"  {icon} [cyan]{commit.hash[:8]}[/] [green]{commit.date}[/] [bold]{commit.message}[/]"
        )
        console.print(f"    Author: {commit.author}")

    console.print("\n[bold][/]")

    # Step 3: LLM Explanation
    if explain:
        console.print("\n[bold]##  AI  ()[/]")

        try:
            # Init LLM
            llm_overrides = _load_project_llm_config("llm_primary")
            llm_config = _apply_llm_overrides(LLMConfig())
            if llm_provider:
                llm_config.provider = llm_provider
            if llm_model:
                llm_config.model = llm_model

            if (
                not llm_overrides
                and not llm_provider
                and not llm_model
                and not llm_config.api_key
                and os.environ.get("DEEPSEEK_API_KEY")
            ):
                llm_config.provider = "deepseek"
                llm_config.model = "deepseek-chat"
                llm_config.api_key = os.environ.get("DEEPSEEK_API_KEY")

            env_key = _llm_env_key(llm_config.provider)
            if not llm_config.api_key and env_key and os.environ.get(env_key):
                llm_config.api_key = os.environ.get(env_key)
                console.print(f"[dim]Using {llm_config.provider} API...[/]")

            client = LiteLLMClient(llm_config)
            analyzer = DecisionAnalyzer(client)

            # For directory mode, provide richer context to the analyzer
            analysis_path = file_path
            if is_directory and directory_files:
                # Create a summary of the directory structure for the LLM
                dir_context = f"{file_path} (directory with {len(directory_files)} files: {', '.join([os.path.basename(f) for f in directory_files[:5]])}{'...' if len(directory_files) > 5 else ''})"
                analysis_path = dir_context

            with console.status("[bold green]Generating Code Story...[/]"):
                story = analyzer.analyze_evolution(analysis_path, commits, lang=target_lang)

            console.print(Panel(Markdown(story), title=" Code Story", border_style="green"))
            _display_cost_summary()

        except Exception as e:
            console.print(f"[red] : {e}[/]")

    console.print("\n[green] [/]")


# [REMOVED] Legacy history command (duplicate)


@app.command()
def timeline(
    day: str = typer.Option("today", help="Date to view (YYYY-MM-DD or 'today') / 日期"),
    time_range: str = typer.Option(
        None, "--range", help="Time range (e.g. '2023-01-01T10:00..2023-01-02T18:00') / 时间范围"
    ),
    limit: int = typer.Option(
        None, "--limit", "-n", help="Show last N events (List Mode) / 显示最近 N 条"
    ),
    event_type: str = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by event type (comma-separated) / 过滤类型",
    ),
):
    """
    View project timeline.
    查看项目时间线。

    [bold cyan]用法: dimc timeline [OPTIONS][/]

    Examples:
        dimc timeline
        dimc timeline --day 2023-10-01
        dimc timeline --range "2023-10-01..2023-10-05"
    """
    if hasattr(day, "default"):
        day = day.default
    if hasattr(time_range, "default"):
        time_range = time_range.default
    if hasattr(limit, "default"):
        limit = limit.default
    if hasattr(event_type, "default"):
        event_type = event_type.default
    from datetime import datetime

    from dimcause.core.timeline import TimelineService

    service = TimelineService()

    if limit:
        # Recent Mode (List)
        events = service.get_recent_events(limit, event_type=event_type)
        event_views = service.build_event_views(events)
        type_filter_str = f" (Type: {event_type})" if event_type else ""
        console.print(
            Panel.fit(
                f"[blue] Timeline: Last {limit} Events{type_filter_str}[/]", border_style="blue"
            )
        )

        last_context_key = None
        for view in event_views:
            evt = view.event
            ts = datetime.fromisoformat(evt["timestamp"]).strftime("%m-%d %H:%M")
            # Map type to icon
            # Reuse ICONS logic from why command or simplified here?
            # Why command defines ICONS locally. Timeline Range mode hardcodes emojis.
            # Let's map dynamically using same set if possible, or expanded hardcode.
            type_icons = {
                "decision": "",
                "git_commit": "",
                "commit": "",  # Legacy
                "code_change": "",
                "failed_attempt": "",
                "reasoning": "",
                "ai_conversation": "",
            }
            emoji = type_icons.get(evt["type"], "")  # Default memo

            summary = evt.get("summary", "")[:60].replace("\n", " ")
            if view.context_key != "ungrouped" and view.context_key != last_context_key:
                console.print(f"\n[bold cyan]{view.context_label}[/]")
                last_context_key = view.context_key
            console.print(
                f"[dim]{ts}[/] {emoji} [bold]{evt['type']}[/] {summary} [dim]({evt['id']})[/]"
            )

    elif time_range:
        # Range Mode
        try:
            start_str, end_str = time_range.split("..")
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
        except Exception:
            console.print("[red] :  ISO  'START..END'[/]")
            raise typer.Exit(1) from None

        events = service.get_events_in_range(start, end, event_type=event_type)
        event_views = service.build_event_views(events)
        type_filter_str = f" (Type: {event_type})" if event_type else ""
        console.print(
            Panel.fit(f"[blue] Timeline: {start} -> {end}{type_filter_str}[/]", border_style="blue")
        )

        last_context_key = None
        for view in event_views:
            evt = view.event
            ts = datetime.fromisoformat(evt["timestamp"]).strftime("%m-%d %H:%M")
            emoji = ""
            if evt["type"] == "decision":
                emoji = ""
            elif evt["type"] == "commit":
                emoji = ""

            summary = evt.get("summary", "")[:60].replace("\n", " ")
            if view.context_key != "ungrouped" and view.context_key != last_context_key:
                console.print(f"\n[bold cyan]{view.context_label}[/]")
                last_context_key = view.context_key
            console.print(
                f"[dim]{ts}[/] {emoji} [bold]{evt['type']}[/] {summary} [dim]({evt['id']})[/]"
            )

    else:
        # Daily Mode
        target_str = get_today_str() if day == "today" else day
        try:
            target_date = datetime.strptime(target_str, "%Y-%m-%d").date()
        except ValueError:
            console.print("[red]  YYYY-MM-DD[/]")
            raise typer.Exit(1) from None

        stats = service.get_daily_stats(target_date)

        console.print(Panel.fit(f"[blue] Daily Stats: {stats.date_str}[/]", border_style="blue"))
        console.print(f"[bold]Total Events:[/] {stats.total_events}")

        if stats.by_session:
            console.print("\n[bold]Active Sessions:[/]")
            for session_id, count in sorted(
                stats.by_session.items(), key=lambda item: item[1], reverse=True
            )[:5]:
                console.print(f"  - {session_id}: {count}")

        if stats.by_job:
            console.print("\n[bold]Active Jobs:[/]")
            for job_id, count in sorted(
                stats.by_job.items(), key=lambda item: item[1], reverse=True
            )[:5]:
                console.print(f"  - {job_id}: {count}")

        # Visualization (ASCII Chart)
        if stats.by_hour:
            console.print("\n[bold]Activity by Hour:[/]")
            max_val = max(stats.by_hour.values())
            for h in range(0, 24):
                count = stats.by_hour.get(h, 0)
                bar = "" * int((count / max_val) * 20) if max_val > 0 else ""
                if count > 0:
                    console.print(f"  {h:02d}:00 | {bar} ({count})")

        if stats.gaps:
            console.print("\n[yellow] Detected Gaps (>4h):[/]")
            for gap in stats.gaps:
                console.print(f"  - {gap.start_str} -> {gap.end_str} ({gap.duration_hours:.1f}h)")


@app.command()
def view(
    event_id: str = typer.Option(None, "--event", "-e", help="Event ID to view / 事件 ID"),
    time_range: str = typer.Option(
        None,
        "--range",
        "-r",
        help="Time range / 时间范围 (e.g. '2023-01-01T10:00..2023-01-02T18:00')",
    ),
    summary_only: bool = typer.Option(
        False, "--summary-only", "-s", help="Only show summaries in range view / 仅显示摘要"
    ),
):
    """
    View details of a specific event or range.
    查看特定事件或时间范围的详情。

    [bold cyan]用法: dimc view [OPTIONS][/]

    Examples:
        dimc view --event evt_20231001_xxxx
        dimc view --range "2023-10-01T10:00..2023-10-01T12:00"
    """
    if hasattr(event_id, "default"):
        event_id = event_id.default
    if hasattr(time_range, "default"):
        time_range = time_range.default
    if hasattr(summary_only, "default"):
        summary_only = summary_only.default
    from datetime import datetime

    from dimcause.core.event_index import EventIndex
    from dimcause.core.timeline import TimelineService

    if not event_id and not time_range:
        console.print("[red]  --event <ID>  --range <RANGE>[/]")
        raise typer.Exit(1)

    index = EventIndex()

    # === Mode 1: Range View ===
    if time_range:
        try:
            start_str, end_str = time_range.split("..")
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
        except Exception:
            console.print("[red] :  ISO  'START..END'[/]")
            raise typer.Exit(1) from None

        service = TimelineService(index)
        events = service.get_events_in_range(start, end)

        console.print(Panel.fit(f"[blue] View Range: {start} -> {end}[/]", border_style="blue"))

        if not events:
            console.print("[yellow]No events found in this range.[/]")
            return

        for i, evt in enumerate(events, 1):
            ts = datetime.fromisoformat(evt["timestamp"]).strftime("%m-%d %H:%M")
            console.print(f"[bold cyan][{i}][/] [dim]{ts}[/] [bold]{evt['type']}[/] {evt['id']}")
            console.print(f"    [dim]Summary:[/] {evt.get('summary', '')}")

            if not summary_only:
                # Load full content for range view? Blueprint says "Default show summaries... --summary-only implies only summary"
                # Actually Blueprint says: "Default show summary (timestamp + type + short content). --summary-only checks only summary."
                # But also "content preview".
                # Let's show a bit more content if not summary-only.
                full_evt = index.load_event(evt["id"])
                if full_evt and full_evt.content:
                    preview = full_evt.content[:200].replace("\n", " ")
                    console.print(f"    [dim]Content:[/] {preview}...")

            console.print("")  # Spacing
        return

    # === Mode 2: Single Event View (Context) ===
    # 支持部分 ID 匹配 (至少 4 字符)
    evt = index.get_by_id(event_id)
    if not evt and len(event_id) >= 4:
        # 尝试模糊匹配: 查询所有事件，找到以 event_id 开头的
        all_events = index.query(limit=1000)
        matches = [e for e in all_events if e["id"].startswith(event_id)]
        if len(matches) == 1:
            event_id = matches[0]["id"]
            evt = matches[0]
            console.print(f"[dim]自动匹配到: {event_id}[/]")
        elif len(matches) > 1:
            console.print(f"[yellow]找到 {len(matches)} 个匹配的事件:[/]")
            for m in matches[:5]:
                console.print(f"  - {m['id']}")
            if len(matches) > 5:
                console.print(f"  ... 还有 {len(matches) - 5} 个")
            console.print("[yellow]请提供更精确的 ID[/]")
            raise typer.Exit(1)
    if not evt:
        console.print(f"[red] Event not found: {event_id}[/]")
        raise typer.Exit(1)

    # Fetch Context
    neighbors = index.get_neighbors(event_id, n=3)

    # 1. Show Previous
    if neighbors["prev"]:
        console.print("[dim]--- Previous Events ---[/]")
        for n in neighbors["prev"]:
            ts = datetime.fromisoformat(n["timestamp"]).strftime("%H:%M")
            console.print(f"[dim]{ts} {n['type']} {n.get('summary', '')[:50]} ({n['id']})[/]")
        console.print("")

    # 2. Show Current
    console.print(Panel.fit(f"[blue] Event: {evt['id']}[/]", border_style="blue"))
    console.print(f"[bold]Type:[/] {evt['type']}")
    console.print(f"[bold]Time:[/] {evt['timestamp']}")
    console.print(f"[bold]Path:[/] {evt['markdown_path']}")
    console.print("\n[bold]Summary:[_]")
    console.print(evt.get("summary", "(No summary)"))

    full_event = index.load_event(event_id)
    if full_event and full_event.content:
        console.print("\n[bold]Content Preview:[/]")
        from rich.markdown import Markdown

        try:
            md = Markdown(full_event.content)
            console.print(Panel(md, border_style="dim", padding=(1, 2)))
        except Exception:
            # 降级到纯文本
            console.print(Panel(full_event.content, border_style="dim", padding=(1, 2)))
    else:
        console.print("[yellow]  ()[/]")

    # 3. Show Next
    if neighbors["next"]:
        console.print("")
        console.print("[dim]--- Next Events ---[/]")
        for n in neighbors["next"]:
            ts = datetime.fromisoformat(n["timestamp"]).strftime("%H:%M")
            console.print(f"[dim]{ts} {n['type']} {n.get('summary', '')[:50]} ({n['id']})[/]")

    console.print("\n" + "─" * 60 + "\n")

    console.print("[green]✓ 详细查看完成[/]")
    console.print("[dim]提示: 使用 --range 可查看时间范围内的所有事件[/]")


@app.command()
def decision(
    decision_id: str = typer.Argument(
        ..., help="Decision event ID (supports partial match) / 决策 ID"
    ),
):
    """
    View details of a decision event.
    查看单个决策事件的详细信息，包括关联代码和时间上下文。

    [bold cyan]用法: dimc decision DECISION_ID[/]

    Examples:
        dimc decision evt_ai_20260214230639_19d3ecb3  # Full ID
        dimc decision evt_ai_2026  # Partial ID (Auto-match)
    """
    if hasattr(decision_id, "default"):
        decision_id = decision_id.default

    from datetime import datetime

    from dimcause.core.event_index import EventIndex

    index = EventIndex()

    # 1. 尝试精确匹配
    evt = index.get_by_id(decision_id)

    # 2. 尝试部分 ID 匹配（至少 4 字符）
    if not evt and len(decision_id) >= 4:
        all_events = index.query(type="decision", limit=1000)
        matches = [e for e in all_events if e["id"].startswith(decision_id)]

        if len(matches) == 1:
            decision_id = matches[0]["id"]
            evt = matches[0]
            console.print(f"[dim]✓ 自动匹配到: {decision_id}[/]\n")
        elif len(matches) > 1:
            console.print(f"[yellow]⚠ 找到 {len(matches)} 个匹配的决策事件:[/]\n")
            for m in matches[:10]:
                ts = datetime.fromisoformat(m["timestamp"]).strftime("%m-%d %H:%M")
                summary = m.get("summary", "N/A")[:60].replace("\n", " ")
                console.print(f"  • [cyan]{m['id']}[/]")
                console.print(f"    [dim]{ts} - {summary}[/]\n")
            if len(matches) > 10:
                console.print(f"  [dim]... 还有 {len(matches) - 10} 个结果[/]\n")
            console.print("[yellow]请提供更精确的 ID 前缀[/]")
            raise typer.Exit(1)
        elif len(matches) == 0:
            # 尝试在所有事件中搜索（可能类型标记错误）
            all_types = index.query(limit=1000)
            any_matches = [e for e in all_types if e["id"].startswith(decision_id)]
            if any_matches:
                console.print("[yellow]⚠ 未找到类型为 'decision' 的事件，但找到其他类型:[/]\n")
                for m in any_matches[:5]:
                    console.print(f"  • {m['id']} (类型: {m['type']})")
                console.print(f"\n[yellow]请使用 'dimc view --event {decision_id}' 查看[/]")
                raise typer.Exit(1)

    # 3. 验证事件类型
    if evt and evt.get("type") != "decision":
        console.print(f"[yellow]⚠ 该事件不是决策类型 (当前类型: {evt['type']})[/]")
        console.print(f"[yellow]请使用 'dimc view --event {decision_id}' 查看完整详情[/]")
        raise typer.Exit(1)

    # 4. 未找到任何匹配
    if not evt:
        console.print(f"[red]✗ 未找到决策事件: {decision_id}[/]")
        console.print("\n[dim]提示:[/]")
        console.print("  • 使用 'dimc decisions' 查看所有决策")
        console.print("  • 使用 'dimc timeline --type decision' 查看决策时间线")
        raise typer.Exit(1)

    # === 显示决策详情 ===
    ts = datetime.fromisoformat(evt["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")

    console.print(Panel.fit("[bold cyan]📋 Decision Event[/]", border_style="cyan"))

    console.print(f"[bold]ID:[/] {evt['id']}")
    console.print(f"[bold]时间:[/] {ts}")
    console.print(f"[bold]摘要:[/] {evt.get('summary', 'N/A')}")

    # 加载完整内容
    full_evt = index.load_event(evt["id"])
    if full_evt and full_evt.content:
        console.print("\n[bold]决策内容:[/]")
        from rich.markdown import Markdown

        try:
            md = Markdown(full_evt.content)
            console.print(Panel(md, border_style="dim", padding=(1, 2)))
        except Exception:
            # 降级到纯文本
            console.print(Panel(full_evt.content, border_style="dim", padding=(1, 2)))
    else:
        console.print("\n[dim]暂无详细内容[/]")

    # === 显示时间上下文（前后事件） ===
    try:
        neighbors = index.get_neighbors(evt["id"], n=3)

        if neighbors.get("prev"):
            console.print("\n[bold]⏮ 之前的事件:[/]")
            for n in neighbors["prev"]:
                ts_n = datetime.fromisoformat(n["timestamp"]).strftime("%m-%d %H:%M")
                typ = n["type"]
                summ = n.get("summary", "")[:50].replace("\n", " ")
                console.print(f"  [dim]{ts_n}[/] [{typ}] {summ}")

        if neighbors.get("next"):
            console.print("\n[bold]⏭ 之后的事件:[/]")
            for n in neighbors["next"]:
                ts_n = datetime.fromisoformat(n["timestamp"]).strftime("%m-%d %H:%M")
                typ = n["type"]
                summ = n.get("summary", "")[:50].replace("\n", " ")
                console.print(f"  [dim]{ts_n}[/] [{typ}] {summ}")
    except Exception as e:
        console.print(f"\n[yellow]⚠ 无法加载上下文: {e}[/]")

    # === 提示关联代码查看 ===
    console.print("\n[dim italic]💡 提示:[/]")
    console.print("[dim italic]  • 使用 'dimc trace <symbol>' 可查看相关代码定义[/]")
    console.print(
        "[dim italic]  • 使用 'dimc timeline --range \"TIME..TIME\"' 可查看时间范围内的所有事件[/]"
    )


@app.command()
def decisions(
    since: str = typer.Option(
        None, "--since", help="Show decisions since date (YYYY-MM-DD) / 起始日期"
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", help="Maximum number of decisions to show / 最大数量"
    ),
    search: str = typer.Option(
        None, "--search", "-s", help="Search in decision summary/content / 搜索内容"
    ),
):
    """
    List all decision events.
    列出所有决策事件。

    [bold cyan]用法: dimc decisions [OPTIONS][/]

    Examples:
        dimc decisions
        dimc decisions --since 2026-02-01
        dimc decisions --search "architecture"
    """
    if hasattr(since, "default"):
        since = since.default
    if hasattr(limit, "default"):
        limit = limit.default
    if hasattr(search, "default"):
        search = search.default

    from datetime import datetime

    from dimcause.core.event_index import EventIndex

    index = EventIndex()

    # 查询决策事件
    try:
        events = index.query(type="decision", date_from=since, limit=limit * 2 if search else limit)
    except Exception as e:
        console.print(f"[red]✗ 查询失败: {e}[/]")
        raise typer.Exit(1) from e

    # 应用搜索过滤
    if search:
        search_lower = search.lower()
        filtered = []
        for evt in events:
            summary = evt.get("summary", "").lower()
            # 尝试加载完整内容进行搜索
            full_evt = index.load_event(evt["id"])
            content = full_evt.content.lower() if full_evt and full_evt.content else ""

            if search_lower in summary or search_lower in content:
                filtered.append(evt)
                if len(filtered) >= limit:
                    break
        events = filtered

    # 显示结果
    if not events:
        console.print("[yellow]⚠ 未找到符合条件的决策事件[/]")
        console.print("\n[dim]提示:[/]")
        if since:
            console.print(f"  • 尝试扩大时间范围（当前: since {since}）")
        if search:
            console.print(f'  • 尝试更宽泛的搜索词（当前: "{search}"）')
        console.print("  • 使用 'dimc timeline --type decision' 查看完整时间线")
        return

    # 显示标题
    filter_parts = []
    if since:
        filter_parts.append(f"Since: {since}")
    if search:
        filter_parts.append(f'Search: "{search}"')
    filter_str = f" ({', '.join(filter_parts)})" if filter_parts else ""

    console.print(Panel.fit(f"[blue]📋 Decisions List{filter_str}[/]", border_style="blue"))
    console.print(f"[dim]共找到 {len(events)} 条决策事件[/]\n")

    # 列出决策（带分组）
    last_date = None
    for i, evt in enumerate(events, 1):
        ts_obj = datetime.fromisoformat(evt["timestamp"])
        current_date = ts_obj.strftime("%Y-%m-%d")

        # 日期分组
        if current_date != last_date:
            if i > 1:
                console.print("")  # 分组间隔
            console.print(f"[bold cyan]▼ {current_date}[/]")
            last_date = current_date

        ts = ts_obj.strftime("%H:%M:%S")
        summary = evt.get("summary", "N/A")[:80].replace("\n", " ")

        console.print(f"  [bold]{i}.[/] [dim]{ts}[/] {summary}")
        console.print(f"     [dim]ID: {evt['id']}[/]")

    # 底部提示
    console.print("\n[dim italic]💡 提示:[/]")
    console.print("[dim italic]  • 使用 'dimc decision <ID>' 查看决策详情[/]")
    if len(events) >= limit:
        console.print(f"[dim italic]  • 结果已达到上限 ({limit} 条)，使用 --limit 增加显示数量[/]")


# === Agent ===

agent_app = typer.Typer(help="Agent Token Management / Agent Token 管理")
app.add_typer(agent_app, name="agent")


@agent_app.command("create")
def agent_create(
    agent_id: str = typer.Argument(..., help="Agent ID (e.g. claude_code_watcher) / Agent ID"),
    name: str = typer.Option(None, "--name", "-n", help="Agent Name / Agent 名称"),
    ttl_hours: int = typer.Option(
        None, "--ttl", "-t", help="Token Validity (hours) / 有效期 (小时)"
    ),
):
    """
    Create a new agent token.
    创建新的 Agent Token。

    [bold cyan]用法: dimc agent create AGENT_ID [OPTIONS][/]

    Examples:
        dimc agent create claude_code_watcher --ttl 24
    """
    if hasattr(agent_id, "default"):
        agent_id = agent_id.default
    if hasattr(name, "default"):
        name = name.default
    if hasattr(ttl_hours, "default"):
        ttl_hours = ttl_hours.default
    from dimcause.utils.auth import create_agent_token

    console.print("[blue] Agent Token...[/]")

    token = create_agent_token(agent_id, agent_name=name, ttl_hours=ttl_hours)

    console.print("[green] Token[/]")
    console.print(f"\n[bold]Agent ID:[/] {agent_id}")
    if name:
        console.print(f"[bold]Name:[/] {name}")
    console.print(f"[bold]Token:[/] [yellow]{token}[/]")

    if ttl_hours:
        console.print(f"[bold]:[/] {ttl_hours} ")
    else:
        console.print("[bold]:[/] ")

    console.print("\n[dim] Token,[/]")
    console.print(f"[dim]: export DIMCAUSE_AGENT_TOKEN={token}[/]")


@agent_app.command("list")
def agent_list():
    """
    List all registered agents.
    列出所有注册的 Agent。

    Examples:
        dimc agent list
    """
    from rich.table import Table

    from dimcause.utils.auth import get_registry

    registry = get_registry()
    agents = registry.list_agents()

    if not agents:
        console.print("[yellow]Agent[/]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Agent ID", style="green")
    table.add_column("Name", style="blue")
    table.add_column("Created", style="dim")
    table.add_column("Expires", style="yellow")
    table.add_column("Permissions")
    table.add_column("Status")

    for agent in agents:
        from datetime import datetime

        created = datetime.fromtimestamp(agent.created_at).strftime("%Y-%m-%d %H:%M")

        if agent.expires_at:
            expires = datetime.fromtimestamp(agent.expires_at).strftime("%Y-%m-%d %H:%M")
        else:
            expires = "Never"

        perms = ",".join(agent.permissions)

        status = " Expired" if agent.is_expired() else " Active"
        status_style = "red" if agent.is_expired() else "green"

        agent_name = agent.metadata.get("agent_name", "-")

        table.add_row(
            agent.agent_id, agent_name, created, expires, perms, f"[{status_style}]{status}[/]"
        )

    console.print(table)
    console.print(f"\n[dim] {len(agents)} Agent[/]")


@agent_app.command("revoke")
def agent_revoke(
    agent_id: str = typer.Argument(..., help="Agent ID"),
):
    """
    Revoke an agent token.
    撤销 Agent Token。

    Examples:
        dimc agent revoke claude_code_watcher
    """
    if hasattr(agent_id, "default"):
        agent_id = agent_id.default
    from dimcause.utils.auth import get_registry

    registry = get_registry()

    success = registry.revoke_agent(agent_id)

    if success:
        console.print(f"[green] Agent: {agent_id}[/]")
    else:
        console.print(f"[red] Agent: {agent_id}[/]")
        raise typer.Exit(1)


@agent_app.command("cleanup")
def agent_cleanup():
    """
    Cleanup expired agent tokens.
    清理过期的 Agent Token。

    Examples:
        dimc agent cleanup
    """
    from dimcause.utils.auth import get_registry

    registry = get_registry()

    console.print("[blue] Token...[/]")

    cleaned = registry.cleanup_expired()

    if cleaned > 0:
        console.print(f"[green]  {cleaned} Token[/]")
    else:
        console.print("[dim]Token[/]")


@agent_app.command("info")
def agent_info(
    token: str = typer.Argument(..., help="Token"),
):
    """
    Get information about an agent token.
    获取 Agent Token 的信息。

    Examples:
        dimc agent info <token>
    """
    if hasattr(token, "default"):
        token = token.default
    from rich.table import Table

    from dimcause.utils.auth import get_registry

    registry = get_registry()

    info = registry.get_token_info(token)

    if not info:
        console.print("[red] Token[/]")
        raise typer.Exit(1)

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Agent ID", info["agent_id"])
    table.add_row("Agent Name", info["agent_name"])
    table.add_row("Created At", info["created_at"])
    table.add_row("Expires At", info["expires_at"])
    table.add_row("Permissions", ", ".join(info["permissions"]))

    status = " Expired" if info["is_expired"] else " Active"
    status_color = "red" if info["is_expired"] else "green"
    table.add_row("Status", f"[{status_color}]{status}[/]")

    console.print(table)


def _display_cost_summary():
    pass
    try:
        from dimcause.utils.cost_tracker import get_tracker

        stats = get_tracker().get_session_stats()

        cost = stats["total_cost_usd"]
        input_tok = stats["input_tokens"]
        output_tok = stats["output_tokens"]

        if cost > 0:
            console.print(
                Panel.fit(
                    f"[bold green] Session Cost: ${cost:.6f}[/]\n"
                    f"[dim]Input Tokens: {input_tok:,}[/]\n"
                    f"[dim]Output Tokens: {output_tok:,}[/]",
                    title="LLM Usage Stats",
                    border_style="green",
                )
            )
    except ImportError:
        pass
    except Exception as e:
        console.print(f"[dim]Cost stats unavailable: {e}[/]")


@app.command("ingest")
def ingest_data(
    source: str = typer.Argument("git", help="Source type / 来源: git, or path"),
    limit: int = typer.Option(50, "--limit", "-n", help="Limit ingestion items / 限制数量"),
):
    """
    Ingest data from Git or directories.
    从 Git 或目录摄取数据。

    [bold cyan]用法: dimc ingest [SOURCE] [OPTIONS][/]

    Examples:
        dimc ingest git
        dimc ingest ./data
    """
    if hasattr(source, "default"):
        source = source.default
    if hasattr(limit, "default"):
        limit = limit.default
    import os

    if source == "git":
        from dimcause.importers.git_importer import run_import

        console.print(Panel(f"  Git  ( {limit} commits)...", border_style="yellow"))
        try:
            run_import(max_commits=limit)
            _display_cost_summary()
        except Exception as e:
            console.print(f"[red] : {e}[/]")
    elif os.path.isdir(source):
        from dimcause.importers.dir_importer import run_dir_import

        console.print(Panel(f" : {source}", border_style="yellow"))
        try:
            run_dir_import(source)
            _display_cost_summary()
        except Exception as e:
            console.print(f"[red] : {e}[/]")
    else:
        console.print(f"[red]: {source}[/]")
        console.print("[dim]: dimc ingest git  dimc ingest <path-to-folder>[/]")


@app.command("migrate")
def migrate(
    path: str = typer.Argument(None, help="Target path / 目标路径 (defaults to cwd)"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Dry run mode / 试运行模式"),
    backup: bool = typer.Option(
        True, "--backup/--no-backup", help="Backup before migration / 迁移前备份"
    ),
):
    """
    Migrate data or schema.
    迁移数据或架构。

    [bold cyan]用法: dimc migrate [PATH] [OPTIONS][/]

    Examples:
        dimc migrate v4
        dimc migrate ./old_data
    """
    if hasattr(path, "default"):
        path = path.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    if hasattr(backup, "default"):
        backup = backup.default

    from dimcause.core.migrate import migrate_directory, migrate_file

    target_path = Path(path) if path else Path.cwd()

    # Phase 3.1 Migration: Graph Store
    if path == "v4":
        console.print(
            Panel(
                "正在迁移索引至 Graph Store (SQLite)", title="Schema 迁移 v4", border_style="blue"
            )
        )
        if dry_run:
            console.print("[yellow]v4 迁移暂不支持 Dry run (这是安全的幂等 SQL 操作)。[/yellow]")
            # 未来可以包裹在事务中并回滚

        from dimcause.core.event_index import EventIndex

        try:
            idx = EventIndex()
            stats = idx.migrate_v4()
            console.print(f"[green]迁移 V4 完成:[/green] {stats}")
            return
        except Exception as e:
            console.print(f"[red]迁移 V4 失败:[/red] {e}")
            raise typer.Exit(1) from None  # noqa: B904

    console.print(
        Panel(
            f"Running Migration [bold]{'DRY RUN' if dry_run else 'REAL RUN'}[/bold]",
            title="Schema Migration",
        )
    )
    console.print(f"Target: {target_path}")
    console.print(f"Backup: {backup}")
    console.print()

    if target_path.is_file():
        #
        if migrate_file(target_path, dry_run=dry_run, backup=backup):
            if dry_run:
                console.print("[yellow]Would migrate:[/yellow] 1 file")
                console.print("Files Scanned: 1")
                console.print("Needs Migration: 1")
            else:
                console.print("[green]Migrated:[/green] 1 file")
        else:
            console.print("[dim]No migration needed or skipped.[/dim]")

    elif target_path.is_dir():
        #
        stats = migrate_directory(target_path, dry_run=dry_run, backup=backup)

        #
        from rich.table import Table

        t = Table(show_header=False, box=None)
        t.add_row("Files Scanned", str(stats["scanned"]))
        t.add_row("Needs Migration", f"[yellow]{stats['needs_migration']}[/yellow]")
        if not dry_run:
            t.add_row("Migrated", f"[green]{stats['migrated']}[/green]")
        t.add_row("Skipped", f"[dim]{stats['skipped']}[/dim]")
        console.print(t)

        if stats["errors"]:
            console.print(f"\n[red]Errors ({len(stats['errors'])}):[/red]")
            for err in stats["errors"]:
                console.print(f"  - {err['file']}: {err['error']}")
    else:
        console.print(f"[red]Error: Path not found: {target_path}[/red]")
        raise typer.Exit(1)


# === Scheduler Commands (Orchestrator V0.9) ===

scheduler_app = typer.Typer(
    help="Task Scheduler (Orchestrator) / 任务调度器",
    short_help="",
)
app.add_typer(scheduler_app, name="scheduler")


@scheduler_app.command("plan")
def scheduler_plan(
    scope: str = typer.Option("current", "--scope", "-s", help=": current, legacy, all"),
    priority: str = typer.Option(None, "--priority", "-p", help=": P0, P1, P2"),
):
    """
    Plan tasks (Scheduler).
    规划任务 (调度器)。

    [bold cyan]用法: dimc scheduler plan [OPTIONS][/]

    Examples:
        dimc scheduler plan
    """
    if hasattr(scope, "default"):
        scope = scope.default
    if hasattr(priority, "default"):
        priority = priority.default

    from dimcause.scheduler.orchestrator import Orchestrator

    console.print(Panel.fit("[bold blue] Dimcause Scheduler - Plan[/]", border_style="blue"))

    try:
        orchestrator = Orchestrator()
        plan_output = orchestrator.plan()
        console.print(Markdown(plan_output))
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("intake")
def scheduler_intake(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    title: str = typer.Option(..., "--title", "-t", help="Task title / 任务标题"),
    goal: str = typer.Option(..., "--goal", "-g", help="High-level goal / 高层目标"),
    priority: str = typer.Option("P2", "--priority", "-p", help="Priority / 优先级"),
    related_file: list[str] = typer.Option(
        [],
        "--related-file",
        help="Related file path / 相关文件路径",
    ),
    deliverable: list[str] = typer.Option(
        [],
        "--deliverable",
        help="Delivery item / 交付物",
    ),
    acceptance: list[str] = typer.Option(
        [],
        "--acceptance",
        help="Acceptance criterion / 验收标准",
    ),
    step: list[str] = typer.Option(
        [],
        "--step",
        help="Suggested step / Step 规划",
    ),
    out_of_scope: list[str] = typer.Option(
        [],
        "--out-of-scope",
        help="Out-of-scope item / 非目标",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing task card / 覆盖已有任务卡",
    ),
):
    """
    Materialize a local scheduler task card from a high-level goal.
    将高层目标物化为本地 scheduler 任务卡。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(title, "default"):
        title = title.default
    if hasattr(goal, "default"):
        goal = goal.default
    if hasattr(priority, "default"):
        priority = priority.default
    if hasattr(overwrite, "default"):
        overwrite = overwrite.default

    task = task.strip()
    title = title.strip()
    goal = goal.strip()

    console.print(Panel.fit("[bold blue] Dimcause Scheduler - Intake[/]", border_style="blue"))

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        card_path = orchestrator.materialize_agent_task_card(
            task,
            title=title,
            goal=goal,
            priority=priority,
            related_files=related_file,
            deliverables=deliverable,
            acceptance_criteria=acceptance,
            steps=step,
            out_of_scope=out_of_scope,
            overwrite=overwrite,
        )
        console.print("\n[green]Task card created.[/]")
        console.print(f"  task: {task}")
        console.print(f"  file: {card_path}")
        console.print("\n[bold]Next:[/]")
        console.print(f"  1. dimc scheduler run '{task}' --yes")
        console.print(f"  2. dimc scheduler complete '{task}'")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


def _render_scheduler_closeout_summary(summary: dict) -> None:
    console.print("\n[bold]任务摘要:[/]")
    console.print(f"  task: {summary.get('task_id')}")
    console.print(f"  title: {summary.get('title')}")
    console.print(f"  task_class: {summary.get('task_class')}")
    console.print(f"  cli_hint: {summary.get('cli_hint')}")
    console.print(f"  runtime_status: {summary.get('runtime_status')}")
    console.print(f"  branch: {summary.get('branch') or '-'}")
    console.print(f"  base_ref: {summary.get('base_ref')}")
    console.print(f"  current_branch: {summary.get('current_branch')}")
    console.print(f"  pr_ready_present: {'yes' if summary.get('pr_ready_present') else 'no'}")
    console.print(f"  report_exists: {'yes' if summary.get('report_exists') else 'no'}")
    console.print(f"  closeout_policy: {summary.get('closeout_policy')}")
    ahead_behind = summary.get("ahead_behind")
    if isinstance(ahead_behind, dict):
        console.print(
            "  ahead_behind: base_only={base_only}, branch_only={branch_only}".format(
                base_only=ahead_behind.get("base_only", "-"),
                branch_only=ahead_behind.get("branch_only", "-"),
            )
        )
    console.print(f"  eligible: {'yes' if summary.get('eligible') else 'no'}")
    blocking = summary.get("blocking_reasons")
    if isinstance(blocking, list) and blocking:
        console.print("\n[bold yellow]阻断项:[/]")
        for item in blocking:
            console.print(f"  - {item}")


@scheduler_app.command("kickoff")
def scheduler_kickoff(
    goal: str = typer.Option(..., "--goal", help="High-level goal / 高层目标"),
    title: Optional[str] = typer.Option(None, "--title", help="Optional title / 可选标题"),
    task: Optional[str] = typer.Option(None, "--task", help="Optional task id / 可选任务 ID"),
    priority: str = typer.Option("P2", "--priority", help="Priority / 优先级"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without launch / 仅预览"),
    auto_approve: bool = typer.Option(False, "--yes", "-y", help="Skip confirm / 跳过确认"),
    launch: Optional[str] = typer.Option(
        None,
        "--launch",
        help="Launch command executed via the session launch.sh / 通过 session launch.sh 执行的启动命令",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Overwrite existing task card / 覆盖已有任务卡"
    ),
):
    """
    Materialize and immediately launch a scheduler task from a high-level goal.
    从高层目标直接物化任务卡并启动调度任务。
    """
    if hasattr(goal, "default"):
        goal = goal.default
    if hasattr(title, "default"):
        title = title.default
    if hasattr(task, "default"):
        task = task.default
    if hasattr(priority, "default"):
        priority = priority.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    if hasattr(auto_approve, "default"):
        auto_approve = auto_approve.default
    if hasattr(launch, "default"):
        launch = launch.default
    if hasattr(overwrite, "default"):
        overwrite = overwrite.default

    console.print(Panel.fit("[bold blue] Dimcause Scheduler - Kickoff[/]", border_style="blue"))

    try:
        from dimcause.scheduler.orchestrator import Orchestrator
        from dimcause.scheduler.runner import TaskRunner

        orchestrator = Orchestrator()
        payload = orchestrator.materialize_goal_task_card(
            goal=goal,
            title=title,
            task_id=task,
            priority=priority,
            overwrite=overwrite,
        )
        task_id = str(payload["task_id"])
        console.print("\n[green]High-level goal materialized.[/]")
        console.print(f"  task: {task_id}")
        console.print(f"  title: {payload['title']}")
        console.print(f"  class: {payload['task_class']}")
        console.print(f"  cli_hint: {payload['cli_hint']}")
        console.print(f"  file: {payload['card_path']}")

        runner = TaskRunner(orchestrator)
        runner.run_task(
            task_id,
            dry_run=dry_run,
            auto_approve=auto_approve,
            launch=launch,
        )
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("status")
def scheduler_status():
    """
    Show scheduler status.
    显示调度器状态。

    Examples:
        dimc scheduler status
    """
    from dimcause.scheduler.orchestrator import Orchestrator, TaskStatus

    console.print(Panel.fit("[bold blue] Dimcause Scheduler - Status[/]", border_style="blue"))

    try:
        orchestrator = Orchestrator()
        orchestrator.load_state()
        tasks = orchestrator.discover_tasks()
        next_task = orchestrator.get_next_task()
        active_job = orchestrator.get_active_job()
        runtime_state = orchestrator.load_runtime_state()
        runtime_tasks = runtime_state.get("tasks", {}) if isinstance(runtime_state, dict) else {}

        #
        in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
        planned = sum(1 for t in tasks if t.status == TaskStatus.PLANNED)
        blocked = sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)

        console.print("\n[bold]:[/]")
        console.print(f"   : {in_progress}")
        console.print(f"   : {planned}")
        console.print(f"   : {blocked}")

        if active_job:
            job_id, job_dir = active_job
            console.print("\n[bold yellow] Active Job:[/]")
            console.print(f"  ID: {job_id}")
            console.print(f"  : {job_dir}")
            matched_runtime = None
            matched_task_id = None
            if isinstance(runtime_tasks, dict):
                for runtime_task_id, runtime in runtime_tasks.items():
                    if not isinstance(runtime, dict):
                        continue
                    if runtime.get("job_id") == job_id and runtime.get("status") == "running":
                        matched_task_id = runtime_task_id
                        matched_runtime = runtime
                        break
            if matched_runtime and matched_task_id:
                console.print("  Task: {}".format(matched_task_id))
                if matched_runtime.get("branch"):
                    console.print(f"  Branch: {matched_runtime['branch']}")
                if matched_runtime.get("worktree"):
                    console.print(f"  Worktree: {matched_runtime['worktree']}")
                if matched_runtime.get("session_dir"):
                    console.print(f"  Session: {matched_runtime['session_dir']}")
                if matched_runtime.get("session_launch_script"):
                    console.print(f"  Launch: {matched_runtime['session_launch_script']}")
                if matched_runtime.get("session_launch_command"):
                    console.print(f"  Launch Command: {matched_runtime['session_launch_command']}")
                if matched_runtime.get("session_launch_pid") is not None:
                    console.print(f"  Launch PID: {matched_runtime['session_launch_pid']}")
                if matched_runtime.get("session_launch_log"):
                    console.print(f"  Launch Log: {matched_runtime['session_launch_log']}")

        if next_task:
            console.print("\n[bold green] :[/]")
            console.print(f"  ID: {next_task.id}")
            console.print(f"  : {next_task.name}")
            if next_task.cli and next_task.cli != "-":
                console.print(f"  CLI: {next_task.cli}")
            console.print(f"  : {getattr(next_task.status, 'value', str(next_task.status))}")
            console.print(f"  : {next_task.priority.name}")
        else:
            console.print("\n[green] [/]")

    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("summary")
def scheduler_summary(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    base_ref: str = typer.Option(
        "main",
        "--base-ref",
        help="Base ref used for closeout eligibility / 收口资格检查基线",
    ),
    allow_implementation: bool = typer.Option(
        False,
        "--allow-implementation",
        help="Allow implementation tasks to pass low-risk eligibility / 允许实现类任务通过低风险门槛",
    ),
):
    """
    Summarize scheduler runtime, evidence and closeout eligibility for a task.
    汇总任务运行态、证据与收口资格。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(base_ref, "default"):
        base_ref = base_ref.default
    if hasattr(allow_implementation, "default"):
        allow_implementation = allow_implementation.default

    task = task.strip()
    console.print(
        Panel.fit(
            f"[bold blue] Dimcause Scheduler - Summary: {task}[/]",
            border_style="blue",
        )
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        summary = orchestrator.summarize_task_closeout(
            task,
            base_ref=base_ref,
            allow_implementation=allow_implementation,
        )
        _render_scheduler_closeout_summary(summary)
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("inspect")
def scheduler_inspect(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
):
    """
    Inspect runtime state and durable artifacts for a scheduler task.
    检查指定调度任务的 runtime 状态和证据文件。
    """
    if hasattr(task, "default"):
        task = task.default

    task = task.strip()
    console.print(
        Panel.fit(
            f"[bold blue] Dimcause Scheduler - Inspect Task: {task}[/]",
            border_style="blue",
        )
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        inspection = orchestrator.inspect_task_runtime(task)
        runtime = inspection.get("runtime", {})
        artifacts = inspection.get("artifacts", [])
        launch_running = inspection.get("launch_running", False)

        if not isinstance(runtime, dict):
            raise RuntimeError(f"Malformed runtime state for task: {task}")

        console.print("\n[bold]Runtime:[/]")
        for label, key in (
            ("status", "status"),
            ("job_id", "job_id"),
            ("branch", "branch"),
            ("worktree", "worktree"),
            ("started_at", "started_at"),
            ("updated_at", "updated_at"),
            ("completed_at", "completed_at"),
            ("failed_at", "failed_at"),
            ("failure_reason", "failure_reason"),
            ("cleanup_status", "cleanup_status"),
            ("cleanup_reason", "cleanup_reason"),
            ("cleanup_at", "cleanup_at"),
        ):
            value = runtime.get(key)
            if value not in (None, ""):
                console.print(f"  {label}: {value}")

        if runtime.get("session_launch_command") or runtime.get("session_launch_pid") is not None:
            console.print("\n[bold]Launch:[/]")
            if runtime.get("session_launch_command"):
                console.print(f"  command: {runtime['session_launch_command']}")
            if runtime.get("session_launch_pid") is not None:
                console.print(f"  pid: {runtime['session_launch_pid']}")
            console.print(f"  running: {'yes' if launch_running else 'no'}")
            if runtime.get("session_launch_log"):
                console.print(f"  log: {runtime['session_launch_log']}")

        if isinstance(artifacts, list) and artifacts:
            console.print("\n[bold]Artifacts:[/]")
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                name = artifact.get("name", "artifact")
                path = artifact.get("path", "-")
                exists = "yes" if artifact.get("exists") else "no"
                console.print(f"  {name}: {path} (exists: {exists})")

    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("run")
def scheduler_run(
    task: str = typer.Argument(..., help=" ID (: H2, D1)"),
    dry_run: bool = typer.Option(False, "--dry-run", help=" Prompt "),
    auto_approve: bool = typer.Option(False, "--yes", "-y", help=""),
    launch: Optional[str] = typer.Option(
        None,
        "--launch",
        help="Launch command executed via the session launch.sh / 通过 session launch.sh 执行的启动命令",
    ),
):
    """
    Run a specific task.
    运行特定任务。

    [bold cyan]用法: dimc scheduler run TASK_ID [OPTIONS][/]

    Examples:
        dimc scheduler run H2
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    if hasattr(auto_approve, "default"):
        auto_approve = auto_approve.default
    if hasattr(launch, "default"):
        launch = launch.default
    from dimcause.scheduler.orchestrator import Orchestrator
    from dimcause.scheduler.runner import TaskRunner

    try:
        orchestrator = Orchestrator()
        runner = TaskRunner(orchestrator)
        console.print(
            Panel.fit(f"[bold blue] Dimcause Scheduler - Run Task: {task}[/]", border_style="blue")
        )
        runner.run_task(task, dry_run=dry_run, auto_approve=auto_approve, launch=launch)

    except Exception as e:
        console.print(f"[red] : {e}[/]")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1) from None


@scheduler_app.command("codex-run")
def scheduler_codex_run(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview Codex launch command without executing / 仅预览 Codex 启动命令",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirm when bootstrap is needed / 需要补建 runtime 时跳过确认",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Codex model override / Codex 模型覆盖",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="Codex profile override / Codex profile 覆盖",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Forward --json to codex exec / 向 codex exec 透传 --json",
    ),
):
    """
    Launch Codex CLI for an existing scheduler task/session bundle.
    基于现有 scheduler 任务卡和 session bundle 启动 Codex CLI。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    if hasattr(auto_approve, "default"):
        auto_approve = auto_approve.default
    if hasattr(model, "default"):
        model = model.default
    if hasattr(profile, "default"):
        profile = profile.default
    if hasattr(json_output, "default"):
        json_output = json_output.default

    task = task.strip()
    console.print(
        Panel.fit(
            f"[bold blue] Dimcause Scheduler - Codex Run: {task}[/]",
            border_style="blue",
        )
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator
        from dimcause.scheduler.runner import TaskRunner

        orchestrator = Orchestrator()
        runner = TaskRunner(orchestrator)
        result = runner.run_codex_task(
            task,
            auto_approve=auto_approve,
            dry_run=dry_run,
            model=model,
            profile=profile,
            json_output=json_output,
        )
        if dry_run:
            console.print("[yellow]Codex 启动命令预览：[/]")
            console.print(f"  task: {result.get('task_id')}")
            console.print(f"  command: {result.get('command')}")
            console.print(f"  worktree: {result.get('worktree')}")
            console.print(f"  session_dir: {result.get('session_dir')}")
            console.print(f"  output_file: {result.get('output_file')}")
            return

        console.print("[green]Codex CLI 已启动。[/]")
        console.print(f"  task: {task}")
        console.print(f"  status: {result.get('status')}")
        console.print(f"  command: {result.get('launch_command')}")
        console.print(f"  pid: {result.get('launch_pid')}")
        console.print(f"  log: {result.get('launch_log')}")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("complete")
def scheduler_complete(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    task_packet: Optional[Path] = typer.Option(
        None,
        "--task-packet",
        help="Task packet markdown path / 任务包路径",
    ),
    allow: list[str] = typer.Option(
        [],
        "--allow",
        help="Allowed file or directory prefix / 允许修改的文件或目录前缀",
    ),
    risk: list[str] = typer.Option(
        [],
        "--risk",
        help="Residual risk note / 残余风险说明",
    ),
    base_ref: str = typer.Option(
        "main",
        "--base-ref",
        help="Base ref used for diff and whitelist validation / 对比基线分支",
    ),
    report_file: Optional[Path] = typer.Option(
        None,
        "--report-file",
        help="Machine-readable check report path / 检查报告路径",
    ),
    skip_check: bool = typer.Option(
        False,
        "--skip-check",
        help="Reuse existing report without rerunning check.zsh / 复用已有检查报告",
    ),
    allow_dirty: bool = typer.Option(
        False,
        "--allow-dirty",
        help="Bypass clean worktree guard / 跳过工作区干净检查",
    ),
):
    """
    Verify a scheduler task and write completion state.
    对调度任务做完成验证并回写运行时状态。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(task_packet, "default"):
        task_packet = task_packet.default
    if hasattr(base_ref, "default"):
        base_ref = base_ref.default
    if hasattr(report_file, "default"):
        report_file = report_file.default
    if hasattr(skip_check, "default"):
        skip_check = skip_check.default
    if hasattr(allow_dirty, "default"):
        allow_dirty = allow_dirty.default

    task = task.strip()
    console.print(
        Panel.fit(
            f"[bold blue] Dimcause Scheduler - Complete Task: {task}[/]",
            border_style="blue",
        )
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        if task_packet is None:
            runtime = orchestrator.get_task_runtime(task)
            runtime_task_packet = (
                runtime.get("task_packet_file") if isinstance(runtime, dict) else None
            )
            if isinstance(runtime_task_packet, str) and runtime_task_packet.strip():
                task_packet = Path(runtime_task_packet)
        pr_ready_report, resolved_report = _run_scheduler_pr_ready(
            orchestrator.root,
            task,
            task_packet=task_packet,
            allow=allow,
            risk=risk,
            base_ref=base_ref,
            report_file=report_file,
            skip_check=skip_check,
            allow_dirty=allow_dirty,
        )
        runtime = orchestrator.record_task_completed(
            task,
            pr_ready_report=pr_ready_report,
            report_path=resolved_report,
        )
        console.print("\n[green]Scheduler runtime state updated.[/]")
        console.print(f"  task: {task}")
        console.print(f"  status: {runtime.get('status')}")
        console.print(f"  report: {resolved_report}")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("closeout")
def scheduler_closeout(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    base_ref: str = typer.Option(
        "main",
        "--base-ref",
        help="Base ref used for ff-only closeout / ff-only 收口基线",
    ),
    allow_implementation: bool = typer.Option(
        False,
        "--allow-implementation",
        help="Allow implementation tasks to pass low-risk eligibility / 允许实现类任务通过低风险门槛",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview closeout eligibility without merging / 仅预览收口资格",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation before merge / 跳过合并确认",
    ),
):
    """
    Close out a completed scheduler task via ff-only merge when eligible.
    在满足资格时通过 ff-only 合并完成调度任务收口。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(base_ref, "default"):
        base_ref = base_ref.default
    if hasattr(allow_implementation, "default"):
        allow_implementation = allow_implementation.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    if hasattr(auto_approve, "default"):
        auto_approve = auto_approve.default

    task = task.strip()
    console.print(
        Panel.fit(
            f"[bold blue] Dimcause Scheduler - Closeout: {task}[/]",
            border_style="blue",
        )
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        summary = orchestrator.summarize_task_closeout(
            task,
            base_ref=base_ref,
            allow_implementation=allow_implementation,
        )
        _render_scheduler_closeout_summary(summary)

        if dry_run:
            return

        if not summary.get("eligible"):
            raise RuntimeError(
                "task closeout blocked: "
                + ", ".join(cast(list[str], summary.get("blocking_reasons", [])))
            )

        if not auto_approve and not Confirm.ask(f"Confirm ff-only closeout for {task}?"):
            console.print("[yellow]Cancelled[/]")
            return

        result = orchestrator.auto_closeout_task(
            task,
            base_ref=base_ref,
            allow_implementation=allow_implementation,
        )
        console.print("\n[green]Scheduler task closed out.[/]")
        console.print(f"  task: {task}")
        console.print(f"  merged_commit: {result['merged_commit']}")
        console.print(f"  closeout_status: {result['closeout_status']}")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("fail")
def scheduler_fail(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    reason: str = typer.Option(..., "--reason", help="Failure reason / 失败原因"),
):
    """
    Mark a scheduler task as failed in runtime state.
    将调度任务标记为失败并回写运行时状态。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(reason, "default"):
        reason = reason.default

    task = task.strip()
    console.print(
        Panel.fit(f"[bold blue] Dimcause Scheduler - Fail Task: {task}[/]", border_style="blue")
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        runtime = orchestrator.record_task_failed(task, reason=reason.strip())
        console.print("[yellow]Scheduler runtime state updated.[/]")
        console.print(f"  task: {task}")
        console.print(f"  status: {runtime.get('status')}")
        console.print(f"  reason: {runtime.get('failure_reason')}")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("stop")
def scheduler_stop(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    reason: str = typer.Option(
        "stopped by operator",
        "--reason",
        help="Stop reason / 停止原因",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Use SIGKILL instead of SIGTERM / 使用 SIGKILL 强制终止",
    ),
):
    """
    Stop a running scheduler launch and mark the task failed.
    停止运行中的 scheduler launch，并将任务标记为 failed。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(reason, "default"):
        reason = reason.default
    if hasattr(force, "default"):
        force = force.default

    task = task.strip()
    console.print(
        Panel.fit(f"[bold blue] Dimcause Scheduler - Stop Task: {task}[/]", border_style="blue")
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        result = orchestrator.stop_task_launch(
            task,
            reason=reason.strip(),
            force=force,
        )
        console.print("[yellow]Scheduler task stopped.[/]")
        console.print(f"  task: {task}")
        console.print(f"  status: {result.get('status')}")
        console.print(f"  signal: {result.get('stop_signal')}")
        console.print(f"  signal_sent: {result.get('signal_sent')}")
        console.print(f"  reason: {result.get('failure_reason')}")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("resume")
def scheduler_resume(
    task: str = typer.Argument(..., help="Task ID / 任务 ID"),
    launch: Optional[str] = typer.Option(
        None,
        "--launch",
        help="Override recorded launch command / 覆盖已记录的启动命令",
    ),
):
    """
    Resume a stopped/failed scheduler launch from its existing session bundle.
    基于现有 session bundle 恢复已停止/失败的 scheduler launch。
    """
    if hasattr(task, "default"):
        task = task.default
    if hasattr(launch, "default"):
        launch = launch.default

    task = task.strip()
    console.print(
        Panel.fit(f"[bold blue] Dimcause Scheduler - Resume Task: {task}[/]", border_style="blue")
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        result = orchestrator.resume_task_launch(task, launch=launch)
        console.print("[green]Scheduler task resumed.[/]")
        console.print(f"  task: {task}")
        console.print(f"  status: {result.get('status')}")
        console.print(f"  command: {result.get('launch_command')}")
        console.print(f"  pid: {result.get('launch_pid')}")
        console.print(f"  log: {result.get('launch_log')}")
        console.print(f"  resume_count: {result.get('resume_count')}")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("cleanup")
def scheduler_cleanup(
    include_failed: bool = typer.Option(
        False,
        "--include-failed",
        help="Also cleanup failed runtime tasks / 同时清理失败任务",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview cleanup operations without mutating runtime state / 仅预览",
    ),
    base_ref: str = typer.Option(
        "main",
        "--base-ref",
        help="Base ref used to decide whether branch is merged / 判断分支是否已合并的基线",
    ),
):
    """
    Cleanup scheduler worktree/session runtime footprints.
    清理 scheduler 已完成任务的 worktree/session 运行时足迹。
    """
    if hasattr(include_failed, "default"):
        include_failed = include_failed.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    if hasattr(base_ref, "default"):
        base_ref = base_ref.default

    console.print(Panel.fit("[bold blue] Dimcause Scheduler - Cleanup[/]", border_style="blue"))

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        summary = orchestrator.cleanup_task_workspaces(
            include_failed=include_failed,
            dry_run=dry_run,
            base_ref=base_ref,
        )
        mode_label = "Dry-run preview" if dry_run else "Cleanup applied"
        console.print(f"[green]{mode_label}.[/]")
        console.print(
            "  cleaned: {cleaned} | skipped: {skipped} | errors: {errors}".format(
                cleaned=summary.get("cleaned", 0),
                skipped=summary.get("skipped", 0),
                errors=summary.get("errors", 0),
            )
        )
        tasks = summary.get("tasks")
        if isinstance(tasks, list) and tasks:
            for item in tasks:
                if not isinstance(item, dict):
                    continue
                task_id = item.get("task_id", "-")
                action = item.get("action", "-")
                reason = item.get("reason", "-")
                console.print(f"  - {task_id}: {action} ({reason})")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("prune-runtime")
def scheduler_prune_runtime(
    include_failed: bool = typer.Option(
        False,
        "--include-failed",
        help="Also prune failed runtime tasks / 同时裁剪失败任务",
    ),
    retain_days: int = typer.Option(
        14,
        "--retain-days",
        min=0,
        help="Retention window in days / 保留天数",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview prune operations without mutating runtime state / 仅预览",
    ),
):
    """
    Prune stale scheduler runtime entries after cleanup.
    裁剪 cleanup 后的过期 scheduler 运行时状态条目。
    """
    if hasattr(include_failed, "default"):
        include_failed = include_failed.default
    if hasattr(retain_days, "default"):
        retain_days = retain_days.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default

    console.print(
        Panel.fit("[bold blue] Dimcause Scheduler - Prune Runtime[/]", border_style="blue")
    )

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        summary = orchestrator.prune_runtime_tasks(
            include_failed=include_failed,
            retain_days=retain_days,
            dry_run=dry_run,
        )
        mode_label = "Dry-run preview" if dry_run else "Runtime prune applied"
        console.print(f"[green]{mode_label}.[/]")
        console.print(
            "  pruned: {pruned} | skipped: {skipped}".format(
                pruned=summary.get("pruned", 0),
                skipped=summary.get("skipped", 0),
            )
        )
        tasks = summary.get("tasks")
        if isinstance(tasks, list) and tasks:
            for item in tasks:
                if not isinstance(item, dict):
                    continue
                task_id = item.get("task_id", "-")
                action = item.get("action", "-")
                reason = item.get("reason", "-")
                console.print(f"  - {task_id}: {action} ({reason})")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("reconcile")
def scheduler_reconcile(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview reconcile operations without mutating runtime state / 仅预览",
    ),
):
    """
    Reconcile stale running scheduler tasks whose launch PID already exited.
    收口 launch PID 已退出的 stale running scheduler 任务。
    """
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default

    console.print(Panel.fit("[bold blue] Dimcause Scheduler - Reconcile[/]", border_style="blue"))

    try:
        from dimcause.scheduler.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        summary = orchestrator.reconcile_running_tasks(dry_run=dry_run)
        mode_label = "Dry-run preview" if dry_run else "Runtime reconcile applied"
        console.print(f"[green]{mode_label}.[/]")
        console.print(
            "  reconciled: {reconciled} | skipped: {skipped}".format(
                reconciled=summary.get("reconciled", 0),
                skipped=summary.get("skipped", 0),
            )
        )
        tasks = summary.get("tasks")
        if isinstance(tasks, list) and tasks:
            for item in tasks:
                if not isinstance(item, dict):
                    continue
                task_id = item.get("task_id", "-")
                action = item.get("action", "-")
                reason = item.get("reason", "-")
                console.print(f"  - {task_id}: {action} ({reason})")
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


@scheduler_app.command("loop")
def scheduler_loop(
    max_rounds: int = typer.Option(
        0,
        "--max-rounds",
        "-n",
        help="Maximum number of rounds to run (0 for infinite) / 最大运行轮数 (0 为无限)",
    ),
    auto_continue: bool = typer.Option(
        False,
        "--auto",
        "-a",
        help="Automatically continue to next task without prompt / 自动继续下一个任务",
    ),
    launch: Optional[str] = typer.Option(
        None,
        "--launch",
        help="Launch command forwarded to each scheduled task / 转发给每个调度任务的启动命令",
    ),
):
    """
    Start the scheduler loop (daemon mode).
    启动调度器循环 (守护模式)。

    [bold cyan]用法: dimc scheduler loop [OPTIONS][/]

    Examples:
        dimc scheduler loop
        dimc scheduler loop -n 5
        dimc scheduler loop --auto
        dimc scheduler loop --auto --launch "bash -lc ..."
    """
    if hasattr(max_rounds, "default"):
        max_rounds = max_rounds.default
    if hasattr(auto_continue, "default"):
        auto_continue = auto_continue.default
    if hasattr(launch, "default"):
        launch = launch.default
    from dimcause.scheduler.loop import SchedulerLoop

    try:
        loop = SchedulerLoop()
        loop.run_loop(max_rounds=max_rounds, auto_continue=auto_continue, launch=launch)

    except Exception as e:
        console.print(f"[red] : {e}[/]")
        # import traceback
        # traceback.print_exc()
        raise typer.Exit(1) from None


lint_app = typer.Typer(help="Code Linter / 代码检查器")
app.add_typer(lint_app, name="lint")


@lint_app.command("run")
def lint_run(
    path: str = typer.Argument(".", help="Path to lint / 路径"),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues / 自动修复"),
):
    """
    Run lint checks.
    运行代码检查。

    [bold cyan]用法: dimc lint run [PATH] [OPTIONS][/]

    Examples:
        dimc lint run .
        dimc lint run src/ --fix
    """
    if hasattr(path, "default"):
        path = path.default
    if hasattr(fix, "default"):
        fix = fix.default

    from dimcause.scheduler.lint import format_report, run_lint

    console.print(Panel.fit("[bold blue] Dimcause Lint - Run[/]", border_style="blue"))

    try:
        report = run_lint(target_path=Path(path), fix=fix)

        formatted = format_report(report)
        console.print(Markdown(formatted))

        #
        if report.has_errors:
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red] Lint : {e}[/]")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1) from None


@app.command()
def trace(
    query: str = typer.Argument(..., help="Symbol or keyword to trace / 要追踪的符号或关键词"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum number of results / 最大结果数"),
):
    """
    Trace code symbols and their relationships.
    追踪代码符号及其关系。

    [bold cyan]用法: dimc trace QUERY [OPTIONS][/]

    Examples:
        dimc trace "MyClass.method"
        dimc trace "EventIndex" -n 100
    """
    if hasattr(query, "default"):
        query = query.default
    if hasattr(limit, "default"):
        limit = limit.default

    from dimcause.core.trace import TraceService
    from dimcause.ui.trace_view import TraceView

    try:
        service = TraceService()
        nodes = service.trace(query, limit=limit)

        view = TraceView()
        view.render_trace_tree(query, nodes)

    except Exception as e:
        console.print(f"[red] : {e}[/]")
        # import traceback
        # traceback.print_exc()
        raise typer.Exit(1) from None


# =============================================================================
# E1 Event Extractor (extract)
# =============================================================================


@app.command()
def dashboard(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to display / 显示天数"),
):
    """
    Launch the analytics dashboard.
    启动分析仪表盘 (TUI)。

    [bold cyan]用法: dimc dashboard [OPTIONS][/]

    Examples:
        dimc dashboard
    """
    if hasattr(days, "default"):
        days = days.default
    pass
    from dimcause.analytics.dashboard import DashboardService
    from dimcause.core.event_index import EventIndex
    from dimcause.ui.dashboard_view import DashboardView

    console.print(f"[dim]Loading dashboard for last {days} days...[/]")

    try:
        index = EventIndex()
        service = DashboardService(index)
        data = service.get_dashboard_data(days=days)

        view = DashboardView(console)
        view.render(data)
    except Exception as e:
        console.print(f"[red]Failed to load dashboard: {e}[/]")


@app.command(name="extract", no_args_is_help=True)
def extract_main(
    session_id: str = typer.Argument(None, help="Session ID to extract. Auto-detects if None."),
):
    """
    Run ExtractionPipeline on chunks from a session.
    对指定 session 的 chunks 运行提取流水线（L1 + 可选 L2）。

    [bold cyan]用法: dimc extract [SESSION_ID]

    Examples:
        dimc extract
        dimc extract sess_20260224_01
    """
    from dimcause.core.event_index import EventIndex
    from dimcause.extractors.extraction_pipeline import ExtractionPipeline
    from dimcause.storage.chunk_store import ChunkStore
    from dimcause.storage.graph_store import GraphStore
    from dimcause.utils.state import get_active_job, get_last_session

    # 如果没有提供 session_id，自动推断
    if session_id is None:
        session_id = get_last_session() or get_active_job()
        if session_id is None:
            console.print("[red]No session_id provided and could not auto-detect.[/]")
            raise typer.Exit(1)
        console.print(f"[dim]Auto-detected session: {session_id}[/]")

    # 实例化存储层
    config = get_config()
    data_dir = config.data_dir
    chunk_store = ChunkStore(db_path=data_dir / "chunks.db")
    event_index = EventIndex(db_path=data_dir / "index.db")
    graph_store = GraphStore(db_path=data_dir / "graph.db")

    # 实例化流水线
    pipeline = ExtractionPipeline(
        event_index=event_index,
        graph_store=graph_store,
        chunk_store=chunk_store,
    )

    # 执行
    console.print(f"[bold]Running extraction pipeline for session: {session_id}[/]")
    stats = pipeline.run(session_id)

    # 打印统计
    console.print(
        Panel(
            f"[bold]L1 Events:[/] {stats['l1_count']}\n"
            f"[bold]L2 Events:[/] {stats['l2_count']}\n"
            f"[bold]Errors:[/]   {stats['errors']}",
            title="Extraction Stats",
        )
    )


@app.command(name="extract-chunks")
def extract_chunks(
    session_id: str = typer.Argument(None, help="Session ID to inspect. Auto-detects if None."),
):
    """
    Show chunk status for a session.
    显示指定 session 的 chunks 状态统计。

    [bold cyan]用法: dimc extract-chunks [SESSION_ID]

    Examples:
        dimc extract-chunks
        dimc extract-chunks sess_20260224_01
    """
    from collections import Counter

    from dimcause.storage.chunk_store import ChunkStore
    from dimcause.utils.config import get_config
    from dimcause.utils.state import get_active_job, get_last_session

    # 如果没有提供 session_id，自动推断
    if session_id is None:
        session_id = get_last_session() or get_active_job()
        if session_id is None:
            console.print("[red]No session_id provided and could not auto-detect.[/]")
            raise typer.Exit(1)
        console.print(f"[dim]Auto-detected session: {session_id}[/]")

    # 实例化 ChunkStore
    config = get_config()
    chunk_store = ChunkStore(db_path=config.data_dir / "chunks.db")

    # 获取该 session 的所有 chunks
    chunks = chunk_store.get_pending_extraction(session_id=session_id)

    # 统计各状态数量
    status_counts = Counter(c.status for c in chunks)

    total = len(chunks)
    console.print(
        Panel(
            f"[bold]Session:[/] {session_id}\n"
            f"[bold]Total:[/]   {total}\n\n"
            f"[dim]Status breakdown:[/]\n"
            + "\n".join(f"  {status}: {count}" for status, count in status_counts.items()),
            title="Chunk Status",
        )
    )


# 保留原有 extract file/diff 命令（不通过 extract 子命令）
def extract_file(
    file_path: str = typer.Argument(..., help="File to extract from / 文件路径"),
    provider: str = typer.Option(
        None, "--provider", "-p", help="LLM Provider (ollama, deepseek, ...). Auto-detects if None."
    ),
    model: str = typer.Option(None, "--model", "-m", help="LLM Model name / 模型名称"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry run / 试运行"),
):
    """
    Extract events from a file.
    从文件中提取事件。

    [bold cyan]用法: dimc extract file FILE [OPTIONS][/]

    Examples:
        dimc extract file docs/logs/today.md
    """
    if hasattr(file_path, "default"):
        file_path = file_path.default
    if hasattr(provider, "default"):
        provider = provider.default
    if hasattr(model, "default"):
        model = model.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    import os
    from pathlib import Path

    from dimcause.brain.extractor import EventExtractor
    from dimcause.core.event_index import EventIndex
    from dimcause.extractors.llm_client import LiteLLMClient, LLMConfig

    path = Path(file_path).resolve()
    if not path.exists():
        console.print(f"[red] : {path}[/]")
        raise typer.Exit(1)

    try:
        content = path.read_text(encoding="utf-8")

        console.print(f"[cyan] : {path.name}...[/]")

        # Configure LLM
        # Priority: CLI > Env Var Detection > Default
        if not provider:
            if os.environ.get("DEEPSEEK_API_KEY"):
                provider = "deepseek"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            elif os.environ.get("GOOGLE_API_KEY"):
                provider = "gemini"
            elif os.environ.get("OPENAI_API_KEY"):
                provider = "openai"

        # Set default models if not provided
        if not model:
            if provider == "deepseek":
                model = "deepseek-coder"
            elif provider == "anthropic":
                model = "claude-3-haiku-20240307"
            elif provider == "gemini":
                model = "gemini-1.5-flash"
            elif provider == "openai":
                model = "gpt-4o-mini"

        # Create Config
        llm_config = LLMConfig()
        if provider:
            llm_config.provider = provider
        if model:
            llm_config.model = model

        # Special handling for DeepSeek from Env
        if provider == "deepseek":
            if not llm_config.api_key and os.environ.get("DEEPSEEK_API_KEY"):
                llm_config.api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not llm_config.base_url and os.environ.get("DEEPSEEK_BASE_URL"):
                llm_config.base_url = os.environ.get("DEEPSEEK_BASE_URL")

        console.print(f"[dim]Using LLM: {llm_config.provider}/{llm_config.model}[/]")

        client = LiteLLMClient(config=llm_config)
        extractor = EventExtractor(llm_client=client)

        events = extractor.extract_from_text(content, source_id=path.name)

        if not events:
            console.print("[yellow]  ( LLM )[/]")
            return

        console.print(f"[green]  {len(events)} :[/]")
        for e in events:
            console.print(f"  - [{getattr(e.type, 'value', str(e.type))}] {e.summary}")

        if dry_run:
            console.print("[dim]Dry run: skipping write[/]")
            return

        # Write to storage
        index = EventIndex()
        # Storage Path: ~/.dimcause/events/extracted/YYYY-MM-DD/
        storage_base = Path("~/.dimcause/events/extracted").expanduser()
        today = datetime.now().strftime("%Y-%m-%d")
        storage_dir = storage_base / today
        storage_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for e in events:
            filename = f"{e.id}.md"
            save_path = storage_dir / filename
            save_path.write_text(e.to_markdown(), encoding="utf-8")

            if index.add(e, str(save_path)):
                count += 1

        console.print(f"[bold green]  {count} [/]")

    except Exception as e:
        console.print(f"[red] : {e}[/]")
        # import traceback
        # traceback.print_exc()
        raise typer.Exit(1) from None


@app.command("extract-diff")
def extract_diff(
    commit_range: str = typer.Argument(
        "HEAD~1", help="Git commit range (default: HEAD~1) / 提交范围"
    ),
    provider: str = typer.Option(None, "--provider", "-p", help="LLM Provider"),
    model: str = typer.Option(None, "--model", "-m", help="LLM Model name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry run"),
):
    """
    Extract events from git diff.
    从 Git Diff 中提取事件。

    [bold cyan]用法: dimc extract diff [RANGE] [OPTIONS][/]

    Examples:
        dimc extract diff HEAD~1
    """
    if hasattr(commit_range, "default"):
        commit_range = commit_range.default
    if hasattr(provider, "default"):
        provider = provider.default
    if hasattr(model, "default"):
        model = model.default
    if hasattr(dry_run, "default"):
        dry_run = dry_run.default
    import os
    import subprocess
    from pathlib import Path

    from dimcause.brain.extractor import EventExtractor
    from dimcause.core.event_index import EventIndex
    from dimcause.extractors.llm_client import LiteLLMClient, LLMConfig

    try:
        console.print(f"[cyan]  Git Diff: {commit_range}...[/]")
        # Run git diff
        cmd = ["git", "diff", commit_range]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        diff_content = result.stdout

        if not diff_content.strip():
            console.print("[yellow] Diff [/]")
            return

        console.print(f"[cyan]  Diff ({len(diff_content)} chars)...[/]")

        # Configure LLM (Same logic as above - refactor later if needed)
        # Priority: CLI > Env Var Detection > Default
        if not provider:
            if os.environ.get("DEEPSEEK_API_KEY"):
                provider = "deepseek"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            elif os.environ.get("GOOGLE_API_KEY"):
                provider = "gemini"
            elif os.environ.get("OPENAI_API_KEY"):
                provider = "openai"

        # Set default models if not provided
        if not model:
            if provider == "deepseek":
                model = "deepseek-coder"
            elif provider == "anthropic":
                model = "claude-3-haiku-20240307"
            elif provider == "gemini":
                model = "gemini-1.5-flash"
            elif provider == "openai":
                model = "gpt-4o-mini"

        # Create Config
        llm_config = LLMConfig()
        if provider:
            llm_config.provider = provider
        if model:
            llm_config.model = model

        # Special handling for DeepSeek from Env
        if provider == "deepseek":
            if not llm_config.api_key and os.environ.get("DEEPSEEK_API_KEY"):
                llm_config.api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not llm_config.base_url and os.environ.get("DEEPSEEK_BASE_URL"):
                llm_config.base_url = os.environ.get("DEEPSEEK_BASE_URL")

        console.print(f"[dim]Using LLM: {llm_config.provider}/{llm_config.model}[/]")

        client = LiteLLMClient(config=llm_config)
        extractor = EventExtractor(llm_client=client)

        events = extractor.extract_from_diff(diff_content, source_id=f"diff_{commit_range}")

        if not events:
            console.print("[yellow] [/]")
            return

        console.print(f"[green]  {len(events)} :[/]")
        for e in events:
            console.print(f"  - [{getattr(e.type, 'value', str(e.type))}] {e.summary}")

        if dry_run:
            console.print("[dim]Dry run: skipping write[/]")
            return

        # Write to storage
        index = EventIndex()
        storage_base = Path("~/.dimcause/events/extracted").expanduser()
        today = datetime.now().strftime("%Y-%m-%d")
        storage_dir = storage_base / today
        storage_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for e in events:
            filename = f"{e.id}.md"
            save_path = storage_dir / filename
            save_path.write_text(e.to_markdown(), encoding="utf-8")

            if index.add(e, str(save_path)):
                count += 1

        console.print(f"[bold green]  {count} [/]")

    except subprocess.CalledProcessError:
        console.print("[red] Git .  commit range .[/]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red] : {e}[/]")
        raise typer.Exit(1) from None


def main():
    """
    Entry point for the CLI.
    CLI 入口点。
    """
    # -------------------------------------------------------------------------
    # Auto-migration: ~/.mal -> ~/.dimcause
    # -------------------------------------------------------------------------
    try:
        mal_dir = Path("~/.mal").expanduser()
        dimc_dir = Path("~/.dimcause").expanduser()

        # Only migrate if ~/.mal exists and ~/.dimcause does NOT exist
        # This prevents accidental overwrites if user keeps both
        if mal_dir.exists() and not dimc_dir.exists():
            print(f"[DIMC] Migrating data from {mal_dir} to {dimc_dir}...")
            try:
                mal_dir.rename(dimc_dir)
                print("[DIMC] Migration successful.")
            except Exception as e:
                print(f"[DIMC] Migration failed: {e}")
                print(
                    "[DIMC] Continuing with ~/.dimcause (new empty directory will be created if needed)."
                )
    except Exception:
        # Don't let migration errors crash the app
        pass

    app()


if __name__ == "__main__":
    main()
