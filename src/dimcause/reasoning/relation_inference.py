from __future__ import annotations

from typing import Optional

from dimcause.core.models import Event, EventType
from dimcause.core.ontology import get_ontology

ONTOLOGY_EVENT_CLASS_MAP = {
    EventType.DECISION.value: "Decision",
    EventType.REQUIREMENT.value: "Requirement",
    EventType.INCIDENT.value: "Incident",
    EventType.EXPERIMENT.value: "Experiment",
    EventType.GIT_COMMIT.value: "Commit",
    EventType.CODE_CHANGE.value: "Commit",
    EventType.CONVENTION.value: "Convention",
}


def to_ontology_event_class(event: Event) -> Optional[str]:
    event_type = getattr(event.type, "value", str(event.type))
    return ONTOLOGY_EVENT_CLASS_MAP.get(event_type)


def infer_directed_ontology_relation(
    event_a: Event, event_b: Event
) -> tuple[str, Event, Event] | None:
    """
    在本体中查找 event_a 和 event_b 之间的合法有向关系。

    返回 `(relation_name, true_source, true_target)`，找不到则返回 `None`。
    """

    ontology = get_ontology()
    class_a = to_ontology_event_class(event_a)
    class_b = to_ontology_event_class(event_b)

    if not class_a or not class_b:
        return None

    for rel in ontology.list_valid_relations(class_a):
        rel_def = ontology.get_relation(rel)
        if rel_def and rel_def.range == class_b:
            return (rel, event_a, event_b)

    for rel in ontology.list_valid_relations(class_b):
        rel_def = ontology.get_relation(rel)
        if rel_def and rel_def.range == class_a:
            return (rel, event_b, event_a)

    return None


def infer_semantic_relation(event_a: Event, event_b: Event) -> tuple[str, Event, Event] | None:
    """
    为语义链接推断一个合法的本体关系。

    这里只返回可在当前 ontology 中落盘的关系，不再退回不存在的 `related_to`。
    """

    relation = infer_directed_ontology_relation(event_a, event_b)
    if relation is None:
        return None

    relation_name, source, target = relation
    if relation_name != "overrides":
        return relation

    # `Decision -> Decision` 不能仅凭相似度就默认覆写，至少要有替换/覆盖语义信号。
    combined = f"{event_a.summary} {event_a.content} {event_b.summary} {event_b.content}".lower()
    override_markers = ("override", "overrides", "replace", "replaced", "supersede", "instead")
    if not any(marker in combined for marker in override_markers):
        return None

    newer, older = sorted((source, target), key=lambda event: event.timestamp, reverse=True)
    return ("overrides", newer, older)
