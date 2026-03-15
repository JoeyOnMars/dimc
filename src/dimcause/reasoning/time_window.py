import logging
from datetime import timedelta
from typing import List, Optional

from dimcause.core.models import Event, EventType
from dimcause.reasoning.causal import CausalLink
from dimcause.reasoning.linker_base import BaseLinker

logger = logging.getLogger(__name__)


class TimeWindowLinker(BaseLinker):
    """
    Heuristic Linker based on temporal proximity and rule matching.
    """

    def __init__(self, window_seconds: float = 3600.0):
        self.window_seconds = window_seconds

    def link(self, events: List[Event], window_sec: Optional[float] = None) -> List[CausalLink]:
        """
        Link events based on time window and heuristics.

        Args:
            events: List of events to process.
            window_sec: Lookback window in seconds (default 1 hour).

        Returns:
            List of CausalLink.
        """
        window_sec = window_sec if window_sec is not None else self.window_seconds
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        links: List[CausalLink] = []
        window = timedelta(seconds=window_sec)

        # Optimization: Use a sliding window if list is huge, but double loop is fine for <10k
        for i, current_event in enumerate(sorted_events):
            # We look BACK in time for causes
            # Example: Commit (Current) -> fixes -> Incident (Past)

            # Start strict checking from Ontology definitions
            # Only valid domains can be sources
            # For now, implemented heuristics:
            # 1. Commit -> fixes -> Incident
            # 2. Decision -> triggers -> Incident (Wait, Incident triggers Decision) -> Incident (Past) triggers Decision (Current)

            j = i - 1
            while j >= 0:
                past_event = sorted_events[j]
                time_diff = current_event.timestamp - past_event.timestamp

                if time_diff > window:
                    break  # Outside window

                # Apply Heuristics
                match = self._match_heuristic(current_event, past_event)
                if match:
                    relation, is_reverse = match

                    if is_reverse:
                        # Past -> Current (e.g., Incident triggers Decision)
                        src_id = past_event.id
                        tgt_id = current_event.id
                    else:
                        # Current -> Past (e.g., Commit fixes Incident)
                        src_id = current_event.id
                        tgt_id = past_event.id

                    link = CausalLink(
                        source=src_id,
                        target=tgt_id,
                        relation=relation,
                        weight=0.7,
                        metadata={
                            "strategy": "time_window",
                            "heuristic": "proximity_rule",
                            "time_diff_sec": time_diff.total_seconds(),
                        },
                    )
                    links.append(link)
                    logger.debug(f"Linked {src_id} --{relation}--> {tgt_id}")

                j -= 1

        return links

    def _match_heuristic(self, current: Event, past: Event) -> Optional[tuple[str, bool]]:
        """
        Determine relation between current (later) and past (earlier) event.

        Args:
            current: The later event (t2)
            past: The earlier event (t1)

        Returns:
            Tuple (relation_name, is_reverse) or None.
            is_reverse=True means relation is Past -> Current.
            is_reverse=False means relation is Current -> Past.
        """

        # Rule 1: Commit fixes Incident (Current -> Past)
        if self._is_commit(current) and self._is_incident(past):
            if self._text_match(current, ["fix", "resolv", "close"]):
                return ("fixes", False)

        # Rule 2: Commit realizes Decision (Current -> Past)
        if self._is_commit(current) and self._is_decision(past):
            if self._text_match(current, ["implement", "feat", "reali"]):
                return ("realizes", False)

        # Rule 3: Incident triggers Decision (Past -> Current)
        if self._is_decision(current) and self._is_incident(past):
            # If decision mentions "incident", "outage", "bug"
            if self._text_match(current, ["incident", "outage", "fail", "fix"]):
                return ("triggers", True)

        return None

    def _text_match(self, event: Event, keywords: List[str]) -> bool:
        content = (event.summary + " " + (event.content or "")).lower()
        return any(k in content for k in keywords)

    def _is_commit(self, event: Event) -> bool:
        return event.type in (EventType.GIT_COMMIT, EventType.CODE_CHANGE)

    def _is_incident(self, event: Event) -> bool:
        # Include 'diagnostic' as often errors appear there
        if event.type in (EventType.DIAGNOSTIC, EventType.UNKNOWN, EventType.INCIDENT):
            keywords = ["error", "fail", "exception", "bug", "crash"]
            if event.type == EventType.INCIDENT:
                return True
            return self._text_match(event, keywords)
        return False

    def _is_decision(self, event: Event) -> bool:
        return event.type == EventType.DECISION
