from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClaimType(str, Enum):
    IDENTIFIER = "identifier"
    STABLE_DESCRIPTOR = "stable_descriptor"
    STATE = "state"
    RELATION = "relation"
    EVENT = "event"
    RULE_PROCEDURE = "rule_procedure"
    OPINION = "opinion"
    OTHER = "other"


class ClaimStatus(str, Enum):
    ACTIVE = "active"
    WEAKENED = "weakened"
    BANNED = "banned"
    HISTORICAL = "historical"


class ConflictBehavior(str, Enum):
    ADDITIVE = "additive"
    SINGLE_VALUE = "single_value"
    TEMPORAL = "temporal"
    EXCLUSIVE = "exclusive"
    WEAK = "weak"


class Cardinality(str, Enum):
    SINGLE = "single"
    MULTI = "multi"
    TEMPORAL_MULTI = "temporal_multi"


@dataclass(frozen=True)
class Claim:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    source_id: str = ""
    document_id: str = ""
    sentence_id: str = ""
    interpretation_run_id: str = ""
    subject_mention_id: str | None = None
    object_mention_id: str | None = None
    subject_text: str = ""
    predicate_text: str = ""
    object_text: str | None = None
    claim_group: str = "default"
    claim_type: str | ClaimType = ClaimType.OTHER.value
    claim_status: str | ClaimStatus = ClaimStatus.ACTIVE.value
    assertion_mode: str = "fact"
    time_mode: str = "unknown"
    time_label: str | None = None
    space_mode: str = "unknown"
    space_label: str | None = None
    confidence: float = 0.5
    identity_weight: float = 0.0
    similarity_weight: float = 1.0
    tension_weight: float = 1.0
    conflict_behavior: str | ConflictBehavior = ConflictBehavior.ADDITIVE.value
    cardinality: str | Cardinality = Cardinality.MULTI.value
    space_time_frame_id: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.claim_type, ClaimType):
            object.__setattr__(self, "claim_type", self.claim_type.value)
        if isinstance(self.claim_status, ClaimStatus):
            object.__setattr__(self, "claim_status", self.claim_status.value)
        if isinstance(self.conflict_behavior, ConflictBehavior):
            object.__setattr__(self, "conflict_behavior", self.conflict_behavior.value)
        if isinstance(self.cardinality, Cardinality):
            object.__setattr__(self, "cardinality", self.cardinality.value)

    @property
    def claim_id(self) -> str:
        return self.id

    @property
    def predicate(self) -> str:
        return self.predicate_text

    @property
    def claim_text(self) -> str:
        return " ".join(part for part in [self.subject_text, self.predicate_text, self.object_text] if part).strip()

    def debug_repr(self) -> str:
        md = self.metadata or {}
        pat = md.get("extraction_pattern") or md.get("pattern_name")
        lang = md.get("extraction_language") or md.get("language")
        prov = f" pattern={pat} lang={lang}" if pat or lang else ""
        return (
            f"[CLAIM] {self.claim_type}/{self.claim_group} "
            f"{self.subject_text} --{self.predicate}--> {self.object_text} "
            f"status={self.claim_status} conf={self.confidence} "
            f"sim_w={self.similarity_weight} tension_w={self.tension_weight} "
            f"behavior={self.conflict_behavior}{prov}"
        )


__all__ = [
    "Cardinality",
    "Claim",
    "ClaimStatus",
    "ClaimType",
    "ConflictBehavior",
]
