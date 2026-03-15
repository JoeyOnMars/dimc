import json
from datetime import date

from dimcause.core.timeline import TimelineService


class _StubIndex:
    def __init__(self, events):
        self._events = events

    def query(self, **kwargs):
        return list(self._events)


def _event(event_id, timestamp, *, event_type="decision", session_id=None, job_id=None):
    metadata = {}
    if session_id:
        metadata["session_id"] = session_id
    if job_id:
        metadata["job_id"] = job_id

    return {
        "id": event_id,
        "type": event_type,
        "timestamp": timestamp,
        "date": timestamp[:10],
        "summary": f"summary:{event_id}",
        "job_id": job_id or "",
        "json_cache": json.dumps({"metadata": metadata}),
    }


def test_build_event_views_extracts_session_and_job_context():
    events = [
        _event("evt_1", "2026-03-07T09:00:00", session_id="sess_a", job_id="job-a"),
        _event("evt_2", "2026-03-07T09:05:00", session_id="sess_a"),
        _event("evt_3", "2026-03-07T10:00:00", job_id="job-b"),
    ]
    service = TimelineService(index=_StubIndex(events))

    views = service.build_event_views(events)

    assert views[0].context_label == "session=sess_a | job=job-a"
    assert views[1].context_label == "session=sess_a"
    assert views[2].context_label == "job=job-b"


def test_get_daily_stats_counts_sessions_and_jobs():
    events = [
        _event("evt_1", "2026-03-07T09:00:00", session_id="sess_a", job_id="job-a"),
        _event("evt_2", "2026-03-07T09:05:00", session_id="sess_a", job_id="job-a"),
        _event("evt_3", "2026-03-07T10:00:00", session_id="sess_b", job_id="job-b"),
    ]
    service = TimelineService(index=_StubIndex(events))

    stats = service.get_daily_stats(date(2026, 3, 7))

    assert stats.total_events == 3
    assert stats.by_session["sess_a"] == 2
    assert stats.by_session["sess_b"] == 1
    assert stats.by_job["job-a"] == 2
    assert stats.by_job["job-b"] == 1
