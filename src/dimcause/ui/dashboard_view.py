from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dimcause.analytics.dashboard import DashboardData


class DashboardView:
    def __init__(self, console: Console = None):
        self.console = console or Console()

    def render(self, data: DashboardData):
        # Header
        header_text = f"📊 Engineering Dashboard ({data.start_date} ~ {data.end_date})"
        self.console.print(
            Panel(Text(header_text, justify="center", style="bold white"), style="blue")
        )

        # 1. Trend Chart
        trend_table = Table(box=None, show_header=False, expand=True)
        trend_table.add_column("Date", style="dim", width=12)
        trend_table.add_column("Bar")
        trend_table.add_column("Count", justify="right")

        if data.daily_stats:
            max_val = max(data.daily_stats.values()) if data.daily_stats else 1
            max_val = max(max_val, 1)  # avoid div by zero

            for date, count in data.daily_stats.items():
                # Display MM-DD
                d_short = date[5:]
                bar_len = int((count / max_val) * 40)  # Wider bars
                bar = "█" * bar_len
                style = "green" if count > 0 else "dim"
                trend_table.add_row(d_short, f"[{style}]{bar}[/]", str(count))
        else:
            trend_table.add_row("No Data", "", "")

        self.console.print(Panel(trend_table, title="Weekly Activity Trend", border_style="green"))

        # 2. Distribution
        dist_table = Table(box=box.SIMPLE, show_header=True, expand=True)
        dist_table.add_column("Type", style="bold cyan")
        dist_table.add_column("Count", justify="right")
        dist_table.add_column("Pct", justify="right")

        total = data.total_events if data.total_events > 0 else 1
        for dtype, count in data.type_stats.items():
            pct = count / total * 100
            bar = "▪" * int(pct / 5)
            dist_table.add_row(dtype, str(count), f"{pct:.1f}%  [dim]{bar}[/]")

        self.console.print(
            Panel(dist_table, title="Event Type Distribution", border_style="yellow")
        )

        # 3. Top Modules
        mod_table = Table(box=box.SIMPLE, expand=True)
        mod_table.add_column("Module / Tag", style="magenta")
        mod_table.add_column("Events", justify="right")

        if data.top_modules:
            for mod, count in data.top_modules:
                mod_table.add_row(mod, str(count))
        else:
            mod_table.add_row("[dim]No tags found[/]", "")

        self.console.print(Panel(mod_table, title="Top Active Contexts", border_style="magenta"))
