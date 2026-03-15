from datetime import datetime, timedelta

from dimcause.core.models import Event, EventType
from dimcause.reasoning.time_window import TimeWindowLinker


class TestTimeWindowLinker:
    def setup_method(self):
        self.linker = TimeWindowLinker()
        self.base_time = datetime(2026, 2, 14, 10, 0, 0)

    def create_event(self, id, type, offset_sec, summary=""):
        return Event(
            id=id,
            type=type,
            timestamp=self.base_time + timedelta(seconds=offset_sec),
            summary=summary,
            content=summary,
        )

    def test_fixes_link(self):
        # Incident at T=0
        incident = self.create_event("inc-1", EventType.DIAGNOSTIC, 0, "NullPointerException crash")
        # Commit at T=100 fixing it
        commit = self.create_event("cmt-1", EventType.GIT_COMMIT, 100, "Fixes NPE crash")

        links = self.linker.link([incident, commit], window_sec=3600)

        assert len(links) == 1
        link = links[0]
        assert link.source == "cmt-1"
        assert link.target == "inc-1"
        assert link.relation == "fixes"

    def test_realizes_link(self):
        # Decision at T=0
        decision = self.create_event("dec-1", EventType.DECISION, 0, "Use Neo4j")
        # Commit at T=200 implementing it
        commit = self.create_event("cmt-2", EventType.CODE_CHANGE, 200, "Implement Neo4j adapter")

        links = self.linker.link([decision, commit], window_sec=3600)

        assert len(links) == 1
        link = links[0]
        assert link.source == "cmt-2"
        assert link.target == "dec-1"
        assert link.relation == "realizes"

    def test_triggers_link_reverse(self):
        # Incident at T=0
        incident = self.create_event("inc-2", EventType.INCIDENT, 0, "Database outage")
        # Decision at T=300 triggered by it
        decision = self.create_event(
            "dec-2", EventType.DECISION, 300, "Plan to fix database outage"
        )

        links = self.linker.link([incident, decision], window_sec=3600)

        assert len(links) == 1
        link = links[0]
        assert link.source == "inc-2"  # Past
        assert link.target == "dec-2"  # Current
        assert link.relation == "triggers"

    def test_out_of_window(self):
        incident = self.create_event("inc-3", EventType.DIAGNOSTIC, 0, "Error")
        commit = self.create_event("cmt-3", EventType.GIT_COMMIT, 4000, "Fix error")  # > 3600s

        links = self.linker.link([incident, commit], window_sec=3600)
        assert len(links) == 0

    def test_no_match(self):
        incident = self.create_event("inc-4", EventType.DIAGNOSTIC, 0, "Error")
        commit = self.create_event("cmt-4", EventType.GIT_COMMIT, 10, "Refactor UI")  # No keywords

        links = self.linker.link([incident, commit], window_sec=3600)
        assert len(links) == 0
