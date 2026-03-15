from typer.testing import CliRunner

from dimcause.cli import app
from dimcause.core.timeline import TimelineEventView

runner = CliRunner()


def test_timeline_limit_renders_context_boundaries():
    raw_events = [
        {
            "id": "evt_1",
            "type": "decision",
            "timestamp": "2026-03-07T09:00:00",
            "summary": "first event",
        },
        {
            "id": "evt_2",
            "type": "reasoning",
            "timestamp": "2026-03-07T09:05:00",
            "summary": "second event",
        },
    ]
    views = [
        TimelineEventView(
            event=raw_events[0],
            session_id="sess_a",
            job_id="job-a",
            context_key="session:sess_a|job:job-a",
            context_label="session=sess_a | job=job-a",
        ),
        TimelineEventView(
            event=raw_events[1],
            session_id="sess_a",
            job_id="job-a",
            context_key="session:sess_a|job:job-a",
            context_label="session=sess_a | job=job-a",
        ),
    ]

    class _FakeTimelineService:
        def get_recent_events(self, limit, event_type=None):
            return raw_events

        def build_event_views(self, events):
            return views

    import dimcause.core.timeline as timeline_mod

    original = timeline_mod.TimelineService
    timeline_mod.TimelineService = _FakeTimelineService
    try:
        result = runner.invoke(app, ["timeline", "--limit", "2"])
    finally:
        timeline_mod.TimelineService = original

    assert result.exit_code == 0
    assert "session=sess_a | job=job-a" in result.stdout
    assert "first event" in result.stdout
