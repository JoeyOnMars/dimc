from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from dimcause.core.models import Event, RawData
from dimcause.core.schema import ChunkRecord

from .contracts import (
    Check,
    Claim,
    ClaimStatus,
    Material,
    Relation,
    RelationDirectionality,
    RelationState,
    RelationStateHistoryEntry,
    Result,
)


class ObjectProjectionBundle(BaseModel):
    """Pipeline 过渡期对象投影视图。"""

    version: str = Field(default="v1")
    material: Material
    claims: List[Claim] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)
    checks: List[Check] = Field(default_factory=list)
    results: List[Result] = Field(default_factory=list)

    def to_metadata_payload(self) -> dict:
        return self.model_dump(mode="json")


def project_raw_event_bundle(raw: RawData, event: Event) -> ObjectProjectionBundle:
    """基于 RawData + Event 生成最小对象投影视图。"""
    material = Material(
        id=f"mat_raw_{raw.id}",
        material_type="raw_capture",
        source_ref=raw.id,
        title=event.summary or raw.id,
        evidence_refs=[f"raw:{raw.id}"],
        metadata={
            "source_type": raw.source.value,
            "project_path": raw.project_path,
            "files_mentioned": list(raw.files_mentioned or []),
            "event_id": event.id,
        },
    )
    return _build_bundle(material=material, event=event, evidence_ref=f"raw:{raw.id}")


def project_chunk_event_bundle(chunk: ChunkRecord, event: Event) -> ObjectProjectionBundle:
    """基于 ChunkRecord + Event 生成最小对象投影视图。"""
    material = Material(
        id=f"mat_chunk_{chunk.chunk_id}",
        material_type="session_chunk",
        source_ref=chunk.chunk_id,
        title=event.summary or chunk.chunk_id,
        evidence_refs=[f"chunk:{chunk.chunk_id}"],
        metadata={
            "session_id": chunk.session_id,
            "source_event_id": chunk.source_event_id,
            "status": chunk.status,
            "event_id": event.id,
        },
    )
    return _build_bundle(material=material, event=event, evidence_ref=f"chunk:{chunk.chunk_id}")


def attach_object_projection(event: Event, bundle: ObjectProjectionBundle) -> None:
    """将对象投影结果挂到 Event metadata，作为过渡期桥接落点。"""
    if event.metadata is None:
        event.metadata = {}
    event.metadata["object_projection"] = bundle.to_metadata_payload()


def _build_bundle(material: Material, event: Event, evidence_ref: str) -> ObjectProjectionBundle:
    claim = Claim(
        id=f"claim_{event.id}",
        claim_type=f"{event.type.value}_claim",
        statement=_claim_statement(event),
        target_refs=[material.id],
        evidence_refs=[evidence_ref],
        status=ClaimStatus.PROPOSED,
        metadata={"event_id": event.id},
    )
    relation = Relation(
        id=f"rel_{event.id}_grounded_in",
        relation_type="grounded_in",
        from_ref=claim.id,
        to_ref=material.id,
        directionality=RelationDirectionality.DIRECTED,
        state=RelationState.CANDIDATE,
        state_history=[
            RelationStateHistoryEntry(
                state=RelationState.CANDIDATE,
                changed_at=event.timestamp.isoformat(),
            )
        ],
        evidence_refs=[evidence_ref],
        metadata={"event_id": event.id},
    )
    return ObjectProjectionBundle(material=material, claims=[claim], relations=[relation])


def _claim_statement(event: Event) -> str:
    if event.summary.strip():
        return event.summary.strip()
    content = event.content.strip()
    if len(content) <= 280:
        return content
    return f"{content[:277]}..."
