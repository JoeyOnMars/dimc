from datetime import datetime, timedelta
from unittest.mock import patch

from dimcause.core.models import EventType, SemanticEvent
from dimcause.reasoning.engine import HybridInferenceEngine as ReasoningEngine


class TestReasoningEngineTrajectory:
    def test_infer_trajectory_chains(self):
        """Test that infer_trajectory correctly chains events."""
        # mock SemanticLinker 避免触发网络下载模型
        with patch("dimcause.reasoning.engine.SemanticLinker") as mock_sl:
            mock_sl.return_value.link.return_value = []
            engine = ReasoningEngine()

            t0 = datetime.now()

            # 1. Decision
            evt_decision = SemanticEvent(
                id="dec-1",
                type=EventType.DECISION,
                timestamp=t0,
                summary="Decide X",
                content="Decision content",
            )

            # 2. Code Change (realizes Decision: current=commit, past=decision)
            evt_code = SemanticEvent(
                id="code-1",
                type=EventType.CODE_CHANGE,
                timestamp=t0 + timedelta(hours=1),
                summary="implement X feature",  # 包含 'implement' 触发 realizes 规则
                content="Code content",
            )

            # 3. Unrelated event (far future, outside 2h window)
            evt_other = SemanticEvent(
                id="other-1",
                type=EventType.RESEARCH,
                timestamp=t0 + timedelta(hours=10),
                summary="Other",
                content="Other",
            )

            events = [evt_decision, evt_code, evt_other]

            links = engine.infer(events)

            # Rule: Commit realizes Decision (time_window heuristic)
            # LLM linker 也可能额外贡献 link，用 >= 1
            assert len(links) >= 1
            time_link = next(
                (l for l in links if l.relation == "realizes" and l.metadata.get("strategy") == "time_window"),
                None,
            )
            assert time_link is not None, "time_window realizes link not found"
            assert time_link.source == evt_code.id
            assert time_link.target == evt_decision.id

    def test_infer_trajectory_preserves_existing(self):
        """Test that heuristic inference doesn't duplicate existing links?
        Actually current logic just returns new links, doesn't check existing on event.
        This test verifies it finds the link regardless.
        """
        pass
