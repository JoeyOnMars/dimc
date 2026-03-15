from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from dimcause.core.event_index import EventIndex


@dataclass
class DashboardData:
    total_events: int
    daily_stats: Dict[str, int]
    type_stats: Dict[str, int]
    top_modules: List[Tuple[str, int]]
    start_date: str
    end_date: str


class DashboardService:
    def __init__(self, index: EventIndex):
        self.index = index

    def get_dashboard_data(self, days: int = 7, type_filter: Optional[str] = None) -> DashboardData:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        date_from_str = start_date.strftime("%Y-%m-%d")

        # 1. Daily Stats
        daily = self.index.get_stats_daily(date_from=date_from_str)
        # Fill missing days with 0
        current = start_date
        while current <= end_date:
            d_str = current.strftime("%Y-%m-%d")
            if d_str not in daily:
                daily[d_str] = 0
            current += timedelta(days=1)
        # Sort
        daily = dict(sorted(daily.items()))

        # 2. Type Stats
        type_dist = self.index.get_stats_by_type(date_from=date_from_str)

        # 3. Top Modules (Heuristic based on Tags and File Paths)
        # Fetch raw events for more complex analysis
        # Limit to 1000 to avoid performance hit
        raw_events = self.index.query(date_from=date_from_str, limit=1000)

        module_counter = Counter()
        for evt in raw_events:
            # 1. Check metadata for source ref (file path)
            # 2. Check tags
            # 3. Check summary keywords

            # Extract from file path in metadata?
            # query() returns dict meta.
            pass
            # Wait, EventIndex.query returns dicts.
            # Does it have 'markdown_path'?
            # Let's check query output. It selects * from events.
            # It has 'markdown_path', 'tags'.

            # Strategy: Tags are best if available.
            tags_str = evt.get("tags", "")
            if tags_str:
                # tags are comma separated string in DB
                try:
                    # Check if tags is list (if loaded from json) or string (if raw DB row)
                    # DB row: string. cached json: list.
                    # EventIndex.query returns DB row dicts.
                    t_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                    for t in t_list:
                        module_counter[t] += 1
                except Exception:
                    pass

            # Also try to infer from 'source' if it's a file path?
            # 'source' col is enum (manual/git).
            # We don't have easy file path association in query results unless we parse markdown_path or json_cache.
            # json_cache might be best.
            json_cache = evt.get("json_cache")
            if json_cache:
                import json

                try:
                    json.loads(json_cache)
                    # Check for related files?
                    # For now just trust tags.
                    pass
                except Exception:
                    pass

        top_modules = module_counter.most_common(10)

        total = sum(daily.values())

        return DashboardData(
            total_events=total,
            daily_stats=daily,
            type_stats=type_dist,
            top_modules=top_modules,
            start_date=date_from_str,
            end_date=end_date.strftime("%Y-%m-%d"),
        )
