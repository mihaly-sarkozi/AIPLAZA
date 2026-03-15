from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class Assertion(BaseModel):
    """Assertion domain modell.

    Az elsődleges időfogalom a valid_time:
    - `valid_time_from` / `valid_time_to` = mikor igaz az assertion a világban
    - `source_time` = a forrás dokumentum ideje
    - `ingest_time` = a tudástárba kerülés ideje

    A `time_from` / `time_to` mezők backward-compatible aliasok a valid_time-ra.
    """
    id: int | None = None
    kb_id: int
    source_point_id: str
    source_document_title: str | None = None
    source_sentence_id: int | None = None
    assertion_primary_subject_mention_id: int | None = None
    subject_resolution_type: str = "explicit"
    subject_entity_id: int | None = None
    predicate: str
    object_entity_id: int | None = None
    object_value: str | None = None
    time_interval_id: int | None = None
    place_id: int | None = None
    time_from: datetime | None = None  # backward-compatible alias: valid_time start
    time_to: datetime | None = None  # backward-compatible alias: valid_time end
    place_key: str | None = None
    attributes: list[str] = Field(default_factory=list)
    modality: str = "asserted"
    polarity: str = "positive"
    canonical_text: str
    assertion_fingerprint: str
    confidence: float = 0.0
    strength: float = 0.05
    baseline_strength: float = 0.05
    decay_rate: float = 0.015
    reinforcement_count: int = 0
    evidence_count: int = 0
    source_diversity: int = 1
    first_seen_at: datetime | None = None
    last_reinforced_at: datetime | None = None
    source_time: datetime | None = None  # forrás szerinti időbélyeg (nem valid_time)
    ingest_time: datetime | None = None  # rendszerbe érkezés ideje (nem valid_time)
    status: str = "active"  # active | uncertain | conflicted | superseded | partially_superseded | generalized | refined

    @property
    def valid_time_from(self) -> datetime | None:
        return self.time_from

    @property
    def valid_time_to(self) -> datetime | None:
        return self.time_to
