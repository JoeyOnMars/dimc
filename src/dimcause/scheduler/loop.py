import time

from rich.console import Console
from rich.panel import Panel

from dimcause.scheduler.orchestrator import Orchestrator
from dimcause.scheduler.runner import TaskRunner

console = Console()


class SchedulerLoop:
    """
    负责自动化任务循环 (Automation Loop)

    流程:
    1. Load State
    2. Identify Next Task
    3. Run Task (via TaskRunner)
    4. Verify & Update State (Simulated for V1.0)
    """

    def __init__(self):
        self.orchestrator = Orchestrator()
        self.runner = TaskRunner(self.orchestrator)

    def _auto_reconcile_stale_runtime(self) -> None:
        summary = self.orchestrator.reconcile_running_tasks()
        reconciled = int(summary.get("reconciled", 0))
        if reconciled > 0:
            console.print(
                f"[yellow]♻️ Auto-reconciled {reconciled} stale running task(s) before scheduling.[/]"
            )

    def _wait_for_active_job(self, poll_interval: float) -> None:
        """等待当前活跃 job 结束。"""
        while True:
            self._auto_reconcile_stale_runtime()
            active_job = self.orchestrator.get_active_job()
            if not active_job:
                return
            job_id, job_dir = active_job
            console.print(
                f"[yellow]⏳ Active job still running:[/] [bold]{job_id}[/] [dim]({job_dir})[/]"
            )
            time.sleep(poll_interval)

    def run_loop(
        self,
        max_rounds: int = 5,
        auto_continue: bool = False,
        poll_interval: float = 5.0,
        launch: str | None = None,
    ):
        """执行主循环"""
        round_limit_label = "∞" if max_rounds == 0 else str(max_rounds)
        console.print(
            Panel.fit(
                f"[bold blue]🔄 Starting Scheduler Loop (Max Rounds: {round_limit_label})[/]",
                border_style="blue",
            )
        )

        round_num = 0
        while max_rounds == 0 or round_num < max_rounds:
            round_num += 1
            console.print(f"\n[bold]═ Round {round_num}/{round_limit_label} ═[/]")

            self._auto_reconcile_stale_runtime()
            active_job = self.orchestrator.get_active_job()
            if active_job:
                job_id, job_dir = active_job
                console.print(
                    f"[yellow]⚠️ Active job detected:[/] [bold]{job_id}[/] [dim]({job_dir})[/]"
                )
                if auto_continue:
                    console.print(
                        "[dim]Waiting for the active job to finish before scheduling a new one...[/]"
                    )
                    self._wait_for_active_job(poll_interval=poll_interval)
                    continue

                console.print(
                    "[yellow]Finish the current job first, then rerun `dimc scheduler loop`.[/]"
                )
                break

            # 1. Load & Plan
            self.orchestrator.load_state()
            next_task = self.orchestrator.get_next_task()

            if not next_task:
                console.print("[green]✅ No pending tasks found. All done![/]")
                break

            console.print(
                f"🎯 Target: [bold cyan]{next_task.id}[/] - {next_task.name} ({getattr(next_task.status, 'value', str(next_task.status))})"
            )

            # 2. Confirm (if not auto)
            if not auto_continue:
                from rich.prompt import Confirm

                if not Confirm.ask(f"Proceed with {next_task.id}?"):
                    console.print("[yellow]Loop paused by user.[/]")
                    break

            # 3. Execution
            try:
                # auto_approve=True because user already approved loop step
                run_result = self.runner.run_task(
                    next_task.id,
                    auto_approve=True,
                    launch=launch,
                )

                job_id = (
                    run_result.get("job_id")
                    if isinstance(run_result, dict)
                    else f"{next_task.id.strip().lower()}-auto"
                )

                console.print(f"\n[yellow]⚠️ Task {next_task.id} started as job {job_id}.[/]")
                if auto_continue:
                    console.print(
                        "[dim]Waiting for job completion before next scheduling round...[/]"
                    )
                    self._wait_for_active_job(poll_interval=poll_interval)
                else:
                    console.print(
                        "[blue]Complete the task in the separate window/tab, then run `dimc job-end` and rerun the scheduler.[/]"
                    )
                    break

            except Exception as e:
                console.print(f"[red]❌ Loop Error: {e}[/]")
                break
