from pathlib import Path
from typing import List

from dimcause.audit.engine import BaseCheck, CheckResult


class TimelineIntegrityCheck(BaseCheck):
    name = "timeline_integrity"
    description = "Validate event timeline continuity and generate activity stats"

    def run(self, files: List[Path]) -> CheckResult:
        from datetime import date

        from dimcause.core.timeline import TimelineService

        service = TimelineService()

        # 1. Get stats for today
        today = date.today()
        stats = service.get_daily_stats(today)

        # 2. Construct Message
        msg_parts = [
            f"📅 Today's Activity: {stats.total_events} events",
            f"🏷️  Types: {', '.join([f'{k}:{v}' for k, v in stats.by_type.items()])}",
        ]

        # 3. Details
        details = []
        if stats.gaps:
            details.append("Work Gaps detected:")
            for gap in stats.gaps:
                details.append(f"  - {gap.start_str} -> {gap.end_str} ({gap.duration_hours:.1f}h)")
            details.append("")

        return CheckResult(
            check_name=self.name, success=True, message=" | ".join(msg_parts), details=details
        )
