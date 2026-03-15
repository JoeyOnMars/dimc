import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dimcause.core.event_index import EventIndex


@dataclass
class TimeGap:
    start_ts: float
    end_ts: float
    duration_hours: float
    start_str: str
    end_str: str


@dataclass
class DailyStats:
    date_str: str
    total_events: int
    by_type: Dict[str, int]
    by_hour: Dict[int, int]
    by_session: Dict[str, int]
    by_job: Dict[str, int]
    gaps: List[TimeGap]


@dataclass
class TimelineEventView:
    event: Dict[str, Any]
    session_id: Optional[str]
    job_id: Optional[str]
    context_key: str
    context_label: str


class TimelineService:
    """
    Shared service for timeline analysis and statistics.
    Used by CLI (dimc timeline) and Audit (TimelineIntegrityCheck).
    """

    def __init__(self, index: Optional[EventIndex] = None):
        self.index = index or EventIndex()

    def get_recent_events(
        self, limit: int = 20, event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch recent events.

        Args:
            limit: 最大返回数量
            event_type: 事件类型过滤（支持逗号分隔的多个类型）
        """
        # 处理多类型过滤
        if event_type:
            # EventIndex.query 只支持单一 type，所以需要多次查询或手动过滤
            # 为简化实现，先查询全部再内存过滤
            types = [t.strip() for t in event_type.split(",")]
            events = self.index.query(
                limit=limit * 10, date_from="2020-01-01", date_to="2099-12-31"
            )
            events = [e for e in events if e.get("type") in types]
            events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return events[:limit]
        else:
            events = self.index.query(limit=limit, date_from="2020-01-01", date_to="2099-12-31")
            events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return events

    @staticmethod
    def _extract_event_context(event: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        session_id = None
        job_id = event.get("job_id") or None
        raw_cache = event.get("json_cache")

        if raw_cache:
            try:
                cached = json.loads(raw_cache)
            except (TypeError, json.JSONDecodeError):
                cached = {}
            metadata = cached.get("metadata", {}) if isinstance(cached, dict) else {}
            if isinstance(metadata, dict):
                session_id = metadata.get("session_id") or session_id
                job_id = metadata.get("job_id") or job_id

        return session_id, job_id

    def build_event_views(self, events: List[Dict[str, Any]]) -> List[TimelineEventView]:
        views: List[TimelineEventView] = []
        for event in events:
            session_id, job_id = self._extract_event_context(event)
            if session_id and job_id:
                context_key = f"session:{session_id}|job:{job_id}"
                context_label = f"session={session_id} | job={job_id}"
            elif session_id:
                context_key = f"session:{session_id}"
                context_label = f"session={session_id}"
            elif job_id:
                context_key = f"job:{job_id}"
                context_label = f"job={job_id}"
            else:
                context_key = "ungrouped"
                context_label = "ungrouped"

            views.append(
                TimelineEventView(
                    event=event,
                    session_id=session_id,
                    job_id=job_id,
                    context_key=context_key,
                    context_label=context_label,
                )
            )
        return views

    def get_events_in_range(
        self, start: datetime, end: datetime, limit: int = 1000, event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch raw event data within a time range.

        Args:
            start: 开始时间
            end: 结束时间
            limit: 最大返回数量
            event_type: 事件类型过滤（支持逗号分隔的多个类型）
        """
        start.isoformat()
        end.isoformat()

        # Use query interface (assumes index has date range support or we filter)
        # Check if EventIndex has native range query.
        # Current EventIndex.query has date_from/date_to which are DATE strings (YYYY-MM-DD),
        # not datetime. So we might need to fetch by day and filter, OR update EventIndex.
        # Let's inspect EventIndex.query implementation again.
        # It uses: query_sql += " AND date >= ?" ...
        # So it filters by DATE column.

        # Strategy:
        # 1. Fetch by date range (broad)
        # 2. Filter by exact timestamp (narrow) in memory

        date_from = start.strftime("%Y-%m-%d")
        date_to = end.strftime("%Y-%m-%d")

        raw_events = self.index.query(date_from=date_from, date_to=date_to, limit=limit)

        # Filter by exact timestamp
        start_ts = start.timestamp()
        end_ts = end.timestamp()

        filtered = []
        for evt in raw_events:
            ts_str = evt.get("timestamp", "")
            try:
                # Optimized parsing: if date matches, check detailed time
                dt = datetime.fromisoformat(ts_str)
                ts = dt.timestamp()
                if start_ts <= ts <= end_ts:
                    # 类型过滤
                    if event_type:
                        types = [t.strip() for t in event_type.split(",")]
                        if evt.get("type") in types:
                            filtered.append(evt)
                    else:
                        filtered.append(evt)
            except ValueError:
                continue

        # Sort by timestamp ascending for timeline view (Audit uses descending usually)
        filtered.sort(key=lambda x: x.get("timestamp", ""))
        return filtered

    def get_daily_stats(self, target_date: date) -> DailyStats:
        """Calculate statistics for a specific day."""
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        events = self.get_events_in_range(start, end)

        stats = DailyStats(
            date_str=target_date.strftime("%Y-%m-%d"),
            total_events=len(events),
            by_type={},
            by_hour={},
            by_session={},
            by_job={},
            gaps=[],
        )

        # Aggregation
        timestamps = []

        for evt in events:
            # Type
            evt_type = evt.get("type", "unknown")
            stats.by_type[evt_type] = stats.by_type.get(evt_type, 0) + 1

            session_id, job_id = self._extract_event_context(evt)
            if session_id:
                stats.by_session[session_id] = stats.by_session.get(session_id, 0) + 1
            if job_id:
                stats.by_job[job_id] = stats.by_job.get(job_id, 0) + 1

            # Hour
            ts_str = evt.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                stats.by_hour[dt.hour] = stats.by_hour.get(dt.hour, 0) + 1
                timestamps.append(dt.timestamp())
            except ValueError:
                pass

        # Gap Analysis
        if timestamps:
            timestamps.sort()
            for i in range(len(timestamps) - 1):
                diff = timestamps[i + 1] - timestamps[i]
                if diff > 3600 * 4:  # 4 hours gap
                    stats.gaps.append(
                        TimeGap(
                            start_ts=timestamps[i],
                            end_ts=timestamps[i + 1],
                            duration_hours=diff / 3600,
                            start_str=datetime.fromtimestamp(timestamps[i]).strftime("%H:%M"),
                            end_str=datetime.fromtimestamp(timestamps[i + 1]).strftime("%H:%M"),
                        )
                    )

        return stats
