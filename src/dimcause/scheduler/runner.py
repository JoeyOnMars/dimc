import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from dimcause.scheduler.orchestrator import Orchestrator

console = Console()


class TaskRunner:
    """
    负责执行 Orchestrator 调度的任务 (V1.0)

    核心职责:
    1. 获取任务上下文 (Context Prompt)
    2. 启动子 Agent (mal job-start)
    3. (Future) 自动提交结果
    """

    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.root = orchestrator.root

    def _auto_reconcile_stale_runtime(self) -> None:
        summary = self.orchestrator.reconcile_running_tasks()
        reconciled = int(summary.get("reconciled", 0))
        if reconciled > 0:
            console.print(
                f"[yellow]♻️ Auto-reconciled {reconciled} stale running task(s) before launch.[/]"
            )

    def run_task(
        self,
        task_id: str,
        dry_run: bool = False,
        auto_approve: bool = False,
        launch: str | None = None,
    ):
        """
        执行指定任务

        Args:
            task_id: 任务 ID (e.g., "D1")
            dry_run: 如果为 True，只显示 Prompt 不执行
            auto_approve: 跳过人工确认
        """
        # 1. 加载任务卡 & 生成 Prompt
        console.print(f"[bold blue]🚀 Starting Task Runner for {task_id}...[/]")

        prompt = self.orchestrator.generate_task_prompt(task_id, include_code=True)

        if "❌ 任务卡加载失败" in prompt:
            console.print(prompt)
            raise typer.Exit(1)

        # 2. 显示预览
        console.print(
            Panel(
                f"Ready to start task: [bold]{task_id}[/]\nContext Length: {len(prompt)} chars",
                title="Task Execution Plan",
                border_style="green",
            )
        )

        if dry_run:
            console.print("[dim]Dry run enabled. Prompt preview:[/]")
            console.print(prompt[:1000] + "\n... (truncated)")
            return

        # 3. 确认执行
        if not auto_approve and not Confirm.ask(f"Confirm start job for {task_id}?"):
            console.print("[yellow]Cancelled[/]")
            return

        # 4. 执行 job-start (通过 subprocess 调用 mal CLI 或直接调用函数)
        # 为了保证上下文隔离，建议调用 mal CLI
        return self._execute_job_start(task_id, prompt, launch=launch)

    def _build_auto_job_id(self, task_id: str) -> str:
        return task_id.strip().lower().replace(" ", "-") + "-auto"

    def _infer_work_class(self, task_id: str) -> str:
        return self.orchestrator.infer_work_class_for_task(task_id)

    def _execute_job_start(self, task_id: str, prompt: str, launch: str | None = None):
        """
        调用 dimc job-start

        注意：dimc job-start 目前主要是创建日志文件。
        在 V1.0 中，我们更希望它能直接把 Prompt 喂给 Agent。
        但由于当前 Agent 是"人机协作"模式，我们主要做的是：
        1. 创建 Job
        2. 将 Prompt 复制到剪贴板 或 输出到屏幕供用户复制
        3. (Future) 通过 API 直接传给 Agent
        """
        import shlex
        import subprocess
        import sys

        self._auto_reconcile_stale_runtime()
        active_job = self.orchestrator.get_active_job()
        if active_job:
            active_job_id, active_job_dir = active_job
            raise RuntimeError(f"Active job already running: {active_job_id} ({active_job_dir})")

        import pyperclip  # Optional

        job_id = self._build_auto_job_id(task_id)
        work_class = self._infer_work_class(task_id)
        workspace = self.orchestrator.provision_task_workspace(task_id, work_class=work_class)
        provisioned_branch = workspace["branch"]
        provisioned_worktree = workspace["worktree"]

        # 1. Start Job
        cmd = [sys.executable, "-m", "dimcause.cli", "job-start", job_id]
        console.print(f"[dim]Executing: {' '.join(cmd)}[/]")
        subprocess.run(cmd, cwd=self.root, check=True)

        # 2. Output Prompt
        console.print("\n[bold green]✅ Job Started![/]")
        console.print("[bold]Context Prompt has been generated.[/]")

        try:
            pyperclip.copy(prompt)
            console.print("[green]✨ Prompt copied to clipboard![/]")
        except Exception:
            console.print("[dim](Clipboard not available, please copy from below)[/]")

        # Save validation prompt to a temp file for easy access
        files_dir = self.root / "tmp" / "context"
        files_dir.mkdir(parents=True, exist_ok=True)
        context_file = files_dir / f"{task_id}_context.md"
        context_file.write_text(prompt, encoding="utf-8")
        console.print(f"[blue]📝 Context saved to: {context_file}[/]")
        task_packet_file = self.orchestrator.materialize_task_packet(
            task_id,
            job_id=job_id,
            branch=provisioned_branch,
            worktree=provisioned_worktree,
        )
        job_dir = self.orchestrator.resolve_job_dir(job_id)
        session_bundle = self.orchestrator.materialize_task_session_bundle(
            task_id=task_id,
            job_id=job_id,
            job_dir=job_dir,
            context_file=context_file,
            task_packet_file=task_packet_file,
            branch=provisioned_branch,
            worktree=provisioned_worktree,
            work_class=work_class,
        )
        job_dir = self.orchestrator.persist_task_evidence_on_start(
            task_id=task_id,
            job_id=job_id,
            context_file=context_file,
            task_packet_file=task_packet_file,
            branch=provisioned_branch,
            worktree=provisioned_worktree,
            job_dir=job_dir,
            session_dir=session_bundle["session_dir"],
            session_file=session_bundle["session_file"],
            session_readme=session_bundle["session_readme"],
            durable_session_file=session_bundle["durable_session_file"],
            session_preflight_script=session_bundle["session_preflight_script"],
            session_launch_script=session_bundle["session_launch_script"],
        )
        task_board_file = self.orchestrator.task_board_path()
        console.print(f"[blue]📦 Task packet saved to: {task_packet_file}[/]")
        console.print(f"[blue]🧭 Session bundle saved to: {session_bundle['session_dir']}[/]")
        console.print(
            f"[blue]🛂 Preflight script saved to: {session_bundle['session_preflight_script']}[/]"
        )
        console.print(
            f"[blue]▶️ Launch script saved to: {session_bundle['session_launch_script']}[/]"
        )
        self.orchestrator.record_task_started(
            task_id,
            job_id=job_id,
            context_file=context_file,
            task_packet_file=task_packet_file,
            task_board_file=task_board_file,
            job_dir=job_dir,
            branch=provisioned_branch,
            worktree=provisioned_worktree,
            session_dir=session_bundle["session_dir"],
            session_file=session_bundle["session_file"],
            session_readme=session_bundle["session_readme"],
            durable_session_file=session_bundle["durable_session_file"],
            session_preflight_script=session_bundle["session_preflight_script"],
            session_launch_script=session_bundle["session_launch_script"],
            session_launch_command=None,
            session_launch_pid=None,
            session_launch_log=None,
        )
        launch_pid = None
        launch_log = None
        if launch:
            launch_log = session_bundle["session_dir"] / "launch.log"
            with launch_log.open("a", encoding="utf-8") as handle:
                handle.write(f"# launch command: {launch}\n")
            with launch_log.open("a", encoding="utf-8") as handle:
                process = subprocess.Popen(
                    [str(session_bundle["session_launch_script"]), *shlex.split(launch)],
                    cwd=self.root,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
            launch_pid = process.pid
            self.orchestrator.update_task_session_launch(
                session_file=session_bundle["session_file"],
                durable_session_file=session_bundle["durable_session_file"],
                command=launch,
                pid=launch_pid,
                log_file=launch_log,
            )
            self.orchestrator.update_task_evidence_launch(
                job_dir=job_dir,
                command=launch,
                pid=launch_pid,
                log_file=launch_log,
            )
            self.orchestrator.record_task_started(
                task_id,
                job_id=job_id,
                context_file=context_file,
                task_packet_file=task_packet_file,
                task_board_file=task_board_file,
                job_dir=job_dir,
                branch=provisioned_branch,
                worktree=provisioned_worktree,
                session_dir=session_bundle["session_dir"],
                session_file=session_bundle["session_file"],
                session_readme=session_bundle["session_readme"],
                durable_session_file=session_bundle["durable_session_file"],
                session_preflight_script=session_bundle["session_preflight_script"],
                session_launch_script=session_bundle["session_launch_script"],
                session_launch_command=launch,
                session_launch_pid=launch_pid,
                session_launch_log=launch_log,
            )
            console.print(f"[blue]🚀 Launch command started with PID: {launch_pid}[/]")
            console.print(f"[blue]📝 Launch log: {launch_log}[/]")
        return {
            "job_id": job_id,
            "job_dir": job_dir,
            "context_file": context_file,
            "task_packet_file": task_packet_file,
            "task_board_file": task_board_file,
            "branch": provisioned_branch,
            "worktree": provisioned_worktree,
            "work_class": work_class,
            "session_dir": session_bundle["session_dir"],
            "session_file": session_bundle["session_file"],
            "session_readme": session_bundle["session_readme"],
            "durable_session_file": session_bundle["durable_session_file"],
            "session_preflight_script": session_bundle["session_preflight_script"],
            "session_launch_script": session_bundle["session_launch_script"],
            "launch_command": launch,
            "launch_pid": launch_pid,
            "launch_log": launch_log,
        }
