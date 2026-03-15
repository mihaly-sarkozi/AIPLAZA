from __future__ import annotations

from pydantic import BaseModel, Field

from apps.knowledge.domain.assertion import Assertion
from apps.knowledge.domain.entity import Entity
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.structural_chunk import StructuralChunk


class RetrievalContext(BaseModel):
    """Retrieval context domain modell.

    A query és a context időmetszetei elsődlegesen `valid_time` szemantikát követnek.
    A `query_focus.time_window` csak backward-compatible alias lehet a
    `query_focus.valid_time_window` mellett.
    """
    query_focus: dict = Field(default_factory=dict)
    local_assertion_space: dict = Field(default_factory=dict)
    seed_assertions: list[Assertion] = Field(default_factory=list)
    expanded_assertions: list[Assertion] = Field(default_factory=list)
    top_assertions: list[Assertion] = Field(default_factory=list)
    key_assertions: list[Assertion] = Field(default_factory=list)
    supporting_assertions: list[Assertion] = Field(default_factory=list)
    conflicting_assertions: list[Assertion] = Field(default_factory=list)
    superseded_assertions: list[Assertion] = Field(default_factory=list)
    conflict_bundles: list[dict] = Field(default_factory=list)
    refinement_bundles: list[dict] = Field(default_factory=list)
    assertion_summaries: list[dict] = Field(default_factory=list)
    summary_assertions: list[Assertion] = Field(default_factory=list)
    evidence_sentences: list[Sentence] = Field(default_factory=list)
    source_chunks: list[StructuralChunk] = Field(default_factory=list)
    dynamic_chunks: list[dict] = Field(default_factory=list)
    assertion_neighborhoods: list[dict] = Field(default_factory=list)
    related_entities: list[Entity] = Field(default_factory=list)
    related_places: list[dict] = Field(default_factory=list)
    primary_entities: list[Entity] = Field(default_factory=list)
    per_entity_assertion_groups: list[dict] = Field(default_factory=list)
    per_place_assertion_groups: list[dict] = Field(default_factory=list)
    time_slice_groups: list[dict] = Field(default_factory=list)
    assertion_mention_traces: list[dict] = Field(default_factory=list)
    comparison_left: list[Assertion] = Field(default_factory=list)
    comparison_right: list[Assertion] = Field(default_factory=list)
    comparison_summary: dict = Field(default_factory=dict)
    timeline_sequence: list[dict] = Field(default_factory=list)
    scoring_summary: dict = Field(default_factory=dict)
