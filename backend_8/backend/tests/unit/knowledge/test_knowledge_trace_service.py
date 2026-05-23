from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import ProgrammingError

from apps.knowledge.api.schemas import IngestRunTraceResponse
from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.service.knowledge_trace_service import KnowledgeTraceService


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _ts() -> datetime:
    return datetime.now(timezone.utc)


class _SingleItemStore:
    def __init__(self, item):
        self._item = item

    def get(self, _key):
        return self._item


class _ListStore:
    def __init__(self, items):
        self._items = list(items)

    def list_for_run(self, _run_id):
        return list(self._items)

    def list_for_document(self, _document_id):
        return list(self._items)

    def list_for_sentence(self, _sentence_id):
        return list(self._items)


class _MissingFrameStore:
    def list_for_sentence(self, _sentence_id):
        raise ProgrammingError(
            "select * from knowledge_space_time_frames",
            {},
            Exception('relation "knowledge_space_time_frames" does not exist'),
        )


def test_build_trace_includes_claim_time_and_space_modes() -> None:
    run = SimpleNamespace(id="run-1", status="completed", created_at=_ts())
    item = SimpleNamespace(source_id="source-1", display_name="Source item")
    source = SimpleNamespace(title="Trace source", metadata={"language": "hu"})
    document = SimpleNamespace(id="doc-1", language="hu")
    sentence = SimpleNamespace(id="sentence-1", order_index=1, char_start=0, text_content="Budapesten aktív.", created_at=_ts(), metadata={"language": "hu"})
    mention = SimpleNamespace(
        mention_id="mention-1",
        surface_text="Budapest",
        normalized_text="budapest",
        mention_type="location",
        char_start=0,
        char_end=9,
        confidence=0.8,
        created_at=_ts(),
    )
    claim = SimpleNamespace(
        claim_id="claim-1",
        claim_text="iroda aktív",
        subject_text="iroda",
        predicate="aktív",
        object_text=None,
        claim_type="state",
        claim_group="default",
        claim_status="active",
        confidence=0.77,
        identity_weight=0.9,
        similarity_weight=1.0,
        tension_weight=0.1,
        conflict_behavior="additive",
        cardinality="multi",
        time_mode="current",
        space_mode="bounded",
        created_at=_ts(),
    )
    frame = SimpleNamespace(
        claim_id="claim-1",
        frame_id="frame-1",
        time_mode="current",
        time_value="Korábban",
        time_start=None,
        time_end=None,
        time_precision="relative",
        time_confidence=0.7,
        space_mode="bounded",
        space_value="Budapest",
        space_precision="city",
        space_confidence=0.8,
        overall_confidence=0.8,
    )
    service = KnowledgeTraceService(
        ingest_run_store=_SingleItemStore(run),
        ingest_item_store=_ListStore([item]),
        source_store=_SingleItemStore(source),
        document_store=SimpleNamespace(get_for_source=lambda _source_id: document),
        sentence_store=_ListStore([sentence]),
        mention_store=_ListStore([mention]),
        claim_store=_ListStore([claim]),
        space_time_frame_store=_ListStore([frame]),
    )

    trace = service.build_trace("run-1")

    assert trace is not None
    assert trace["summary"]["space_time_frame_count"] == 1
    assert trace["summary"]["subject_context"]["context_subject_applied_count"] == 0
    assert trace["summary"]["subject_context"]["context_subject_skipped_count"] == 0
    assert trace["summary"]["subject_context"]["context_subject_reset_count"] == 0
    assert trace["summary"]["subject_context"]["context_subject_weak_subject_override_count"] == 0
    assert trace["summary"]["quality"]["rejected_claim_count"] == 0
    assert trace["summary"]["quality"]["diagnostics_persistence_status"] == "summary_only"
    assert trace["sentences"][0]["language"] == "hu"
    assert trace["sentences"][0]["claims"][0]["time_mode"] == "current"
    assert trace["sentences"][0]["claims"][0]["space_mode"] == "bounded"
    assert trace["sentences"][0]["claims"][0]["space_time_frame"]["time_value"] == "korábban"
    assert trace["sentences"][0]["claims"][0]["space_time_frame"]["frame_id"] == "frame-1"
    assert trace["summary"]["local_entity_cluster_count"] == 0
    assert trace["summary"]["local_entity_count"] == 0
    assert trace["summary"]["low_coherence_local_entity_count"] == 0
    assert trace["summary"]["unknown_entity_type_count"] == 0
    assert trace["local_entities"] == []
    assert trace["local_entity_clusters"] == []
    assert trace["local_resolver_trace"] is None


def test_build_trace_handles_missing_space_time_table() -> None:
    run = SimpleNamespace(id="run-2", status="processing", created_at=_ts())
    item = SimpleNamespace(source_id="source-2", display_name="Source item")
    source = SimpleNamespace(title="Trace source", metadata={})
    document = SimpleNamespace(id="doc-2", language="en")
    sentence = SimpleNamespace(id="sentence-2", order_index=1, char_start=0, text_content="The account was created.", created_at=_ts(), metadata={"language": "en"})
    claim = SimpleNamespace(
        claim_id="claim-2",
        claim_text="account created",
        subject_text="account",
        predicate="created",
        object_text=None,
        claim_type="event",
        claim_group="default",
        claim_status="active",
        confidence=0.66,
        identity_weight=0.5,
        similarity_weight=0.7,
        tension_weight=0.0,
        conflict_behavior="additive",
        cardinality="multi",
        time_mode="event",
        space_mode="unknown",
        created_at=_ts(),
    )
    service = KnowledgeTraceService(
        ingest_run_store=_SingleItemStore(run),
        ingest_item_store=_ListStore([item]),
        source_store=_SingleItemStore(source),
        document_store=SimpleNamespace(get_for_source=lambda _source_id: document),
        sentence_store=_ListStore([sentence]),
        mention_store=_ListStore([]),
        claim_store=_ListStore([claim]),
        space_time_frame_store=_MissingFrameStore(),
    )

    trace = service.build_trace("run-2")

    assert trace is not None
    assert trace["summary"]["space_time_frame_count"] == 0
    assert trace["summary"]["quality"]["fragment_sentence_count"] == 0
    assert trace["sentences"][0]["claims"][0]["time_mode"] == "event"
    assert trace["sentences"][0]["claims"][0]["space_mode"] == "unknown"
    assert trace["sentences"][0]["claims"][0]["space_time_frame"]["frame_id"] == "compat:claim-2"
    assert trace["sentences"][0]["claims"][0]["space_time_frame"]["time_mode"] == "event"


class _InterpretationStore:
    def __init__(self, interpretation):
        self._interpretation = interpretation

    def get_for_document(self, _document_id):
        return self._interpretation


def test_build_trace_includes_local_resolver_from_interpretation_metadata() -> None:
    run = SimpleNamespace(
        id="run-lr",
        status="completed",
        created_at=_ts(),
        metadata={
            "quality_diagnostics": {
                "noise_sentence_skipped_count": 2,
                "skipped_sentences": ["This sentence should not create an important claim."],
                "bad_subject_claim_count": 3,
                "rejected_claims": [
                    {
                        "reason": "claim_bad_subject",
                        "subject_text": "This sentence",
                        "predicate": "should not create",
                        "object_text": "important claim",
                    },
                    {
                        "reason": "claim_bad_subject",
                        "subject_text": "Random",
                        "predicate": "note",
                        "object_text": "Paris onboarding is smooth",
                    },
                ],
            }
        },
    )
    item = SimpleNamespace(source_id="source-lr", display_name="Source item")
    source = SimpleNamespace(title="LR source", metadata={"language": "en"})
    document = SimpleNamespace(id="doc-lr", language="en")
    sentence = SimpleNamespace(
        id="sentence-lr",
        order_index=1,
        char_start=0,
        text_content="Example.",
        created_at=_ts(),
        metadata={"language": "en"},
    )
    interpretation = SimpleNamespace(
        id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        metadata={
            "local_entity_cluster_count": 2,
            "local_entity_clusters": [
                {
                    "local_entity_id": "e1",
                    "canonical_name": "Acme",
                    "entity_type": "company",
                    "normalized_key": "acme",
                    "confidence": 0.9,
                    "coherence_score": 0.85,
                    "surface_forms": ["Acme"],
                    "mention_ids": [],
                    "claim_ids": [],
                    "sentence_ids": [],
                    "evidence_refs": [],
                },
                {
                    "local_entity_id": "e2",
                    "canonical_name": "Beta",
                    "entity_type": "unknown",
                    "normalized_key": "beta",
                    "confidence": 0.5,
                    "coherence_score": 0.5,
                    "surface_forms": [],
                    "mention_ids": [],
                    "claim_ids": [],
                    "sentence_ids": [],
                    "evidence_refs": [],
                },
            ],
            "technical_entities": [
                {
                    "technical_entity_id": "te1",
                    "local_entity_id": "e1",
                    "canonical_name": "Acme",
                    "entity_type": "company",
                    "canonical_key": "acme",
                    "coherence_state": "stable",
                    "descriptor_claims": [],
                    "state_claims": [
                        {
                            "claim_id": "c1",
                            "time_mode": "current",
                            "time_value": "currently",
                            "space_mode": "bounded",
                            "space_value": "London office",
                        },
                        {
                            "claim_id": "c2",
                            "time_mode": "bounded",
                            "time_value": "before March 2025",
                            "space_mode": "bounded",
                            "space_value": "London office",
                        },
                    ],
                    "relation_claims": [],
                    "event_claims": [],
                    "time_signature": {
                        "has_current_claims": True,
                        "has_historical_claims": True,
                        "time_values": ["currently", "before March 2025"],
                    },
                    "space_signature": {
                        "has_bounded_space": True,
                        "space_values": ["London office"],
                    },
                    "builder_version": "technical_entity_builder_v1",
                }
            ],
            "technical_memory_chunks": [
                {
                    "technical_memory_chunk_id": "tmc1",
                    "technical_entity_id": "te1",
                    "local_entity_id": "e1",
                    "entity_name": "Acme",
                    "entity_type": "company",
                    "normalized_key": "acme",
                    "summary_text": "Acme állapotai: active.",
                    "facts": [
                        {
                            "claim_id": "c1",
                            "sentence_id": "s1",
                            "claim_group": "state",
                            "claim_type": "state",
                            "predicate": "active",
                            "object_text": None,
                            "confidence": 0.8,
                            "time_mode": "current",
                            "time_value": "currently",
                            "space_mode": "bounded",
                            "space_value": "London office",
                        }
                    ],
                    "time_profile": {
                        "dominant_time_mode": "current",
                        "has_current_claims": True,
                        "has_historical_claims": False,
                        "time_values": ["currently"],
                    },
                    "space_profile": {
                        "dominant_space_mode": "bounded",
                        "has_bounded_space": True,
                        "space_values": ["London office"],
                    },
                    "relation_profile": {
                        "relation_predicates": [],
                        "relation_objects": [],
                        "relation_count": 0,
                    },
                    "evidence_refs": [{"claim_id": "c1", "sentence_id": "s1"}],
                    "coherence_state": "stable",
                    "coherence_score": 0.9,
                    "confidence": 0.8,
                    "builder_version": "technical_memory_chunk_builder_v1",
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "search_profiles": [
                {
                    "search_profile_id": "sp1",
                    "technical_memory_chunk_id": "tmc1",
                    "technical_entity_id": "te1",
                    "local_entity_id": "e1",
                    "entity_name": "Acme",
                    "entity_type": "company",
                    "normalized_key": "acme",
                    "canonical_key": "acme",
                    "canonical_text": "Acme | company | active",
                    "search_text": "Acme company active",
                    "aliases": ["Acme", "acme"],
                    "keywords": ["acme", "company", "active"],
                    "claim_group_signals": {
                        "relation": 0,
                        "state": 1,
                        "rule": 0,
                        "event": 0,
                        "descriptor": 0,
                        "other": 0,
                    },
                    "time_filters": {
                        "dominant": "current",
                        "values": ["currently"],
                        "has_current": True,
                        "has_historical": False,
                    },
                    "space_filters": {
                        "dominant": "bounded",
                        "values": ["London office"],
                        "has_bounded": True,
                    },
                    "relation_filters": {
                        "predicates": [],
                        "objects": [],
                    },
                    "evidence_refs": [{"claim_ids": ["c1"], "sentence_ids": ["s1"], "source_id": "source-lr"}],
                    "builder_version": "search_profile_builder_v1",
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "candidate_selections": [
                {
                    "search_profile_id": "sp1",
                    "candidate_entity_id": "te-support",
                    "candidate_name": "support modul",
                    "score": 0.8,
                    "reasons": ["canonical_name_match:0.42"],
                    "evidence": {"claim_ids": ["c1"], "sentence_ids": ["s1"]},
                },
                {
                    "search_profile_id": "sp1",
                    "candidate_entity_id": "te-support",
                    "candidate_name": "módulo de soporte",
                    "score": 0.79,
                    "reasons": ["canonical_name_match:0.42"],
                    "evidence": {"claim_ids": ["c2"], "sentence_ids": ["s2"]},
                },
            ],
            "similarity_analyses": [
                {
                    "search_profile_id": "sp1",
                    "candidate_entity_id": "te-support",
                    "similarity_band": "high",
                    "total_similarity_score": 0.92,
                    "similarity_reasons": ["name:canonical_exact", "same_type_strong_lexical_overlap_boost"],
                    "evidence": {"claim_ids": ["c1"], "sentence_ids": ["s1"]},
                },
                {
                    "search_profile_id": "sp1",
                    "candidate_entity_id": "te-support",
                    "similarity_band": "medium",
                    "total_similarity_score": 0.71,
                    "similarity_reasons": ["name:canonical_exact"],
                    "evidence": {"claim_ids": ["c2"], "sentence_ids": ["s2"]},
                },
                {
                    "search_profile_id": "sp-account",
                    "candidate_entity_id": "te-account",
                    "similarity_band": "medium",
                    "total_similarity_score": 0.62,
                    "similarity_reasons": ["name:canonical_exact"],
                    "candidate_name_a": "account",
                    "candidate_name_b": "cuenta",
                    "evidence": {"claim_ids": ["c3"], "sentence_ids": ["s3"]},
                }
            ],
            "tension_analyses": [
                {
                    "tension_band": "low",
                    "tension_type": "temporal_change",
                    "tension_reasons": ["temporal_change:different_time_values"],
                    "evidence": {"claim_ids": ["c1", "c2"], "sentence_ids": ["s1", "s2"]},
                }
            ],
            "decision_analyses": [
                {
                    "decision": "keep_separate",
                    "decision_confidence": 0.75,
                    "selected_profile_id": None,
                    "created_profile_id": "global-profile:te1",
                    "decision_reason": "create_new:low_similarity_low_tension",
                    "manual_review_required": False,
                }
            ],
            "global_profiles": [
                {
                    "profile_id": "global-profile:te1",
                    "decision": "create_new",
                    "created_profile_id": "global-profile:te1",
                    "decision_confidence": 0.75,
                    "decision_reason": "create_new:low_similarity_low_tension",
                    "builder_version": "global_profile_builder_v0",
                }
            ],
            "local_resolver_trace": {
                "resolver_version": "local_resolver_v1",
                "steps": [],
                "entity_type_resolutions": [{"resolution": "conflict_split"}],
            },
        },
    )
    service = KnowledgeTraceService(
        ingest_run_store=_SingleItemStore(run),
        ingest_item_store=_ListStore([item]),
        source_store=_SingleItemStore(source),
        document_store=SimpleNamespace(get_for_source=lambda _source_id: document),
        sentence_store=_ListStore([sentence]),
        mention_store=_ListStore([]),
        claim_store=_ListStore([]),
        space_time_frame_store=_ListStore([]),
        interpretation_run_store=_InterpretationStore(interpretation),
    )

    trace = service.build_trace("run-lr")

    assert trace is not None
    assert trace["summary"]["local_entity_cluster_count"] == 2
    assert trace["summary"]["technical_entities"] == 1
    assert trace["summary"]["technical_memory_chunks"] == 1
    assert trace["summary"]["search_profiles"] == 1
    assert trace["summary"]["local_entity_count"] == 2
    assert trace["summary"]["low_coherence_local_entity_count"] == 1
    assert trace["summary"]["unknown_entity_type_count"] == 1
    assert len(trace["local_entities"]) == 2
    assert trace["local_entities"][0]["canonical_name"] == "Acme"
    assert trace["local_entities"][1]["entity_type"] == "unknown"
    assert trace["local_entity_clusters"][0]["canonical_name"] == "Acme"
    assert trace["technical_entities"][0]["canonical_name"] == "Acme"
    assert trace["technical_entities"][0]["builder_version"] == "technical_entity_builder_v1"
    te = trace["technical_entities"][0]
    assert te["index"] == 1
    assert te["name"] == "Acme"
    assert te["type"] == "company"
    assert te["coherence"] == "stable"
    assert te["coherence_state"] == "stable"
    assert te["claim_groups"]["descriptor"] == 0
    assert te["claim_groups"]["state"] == 2
    assert te["claim_groups"]["relation"] == 0
    assert te["claim_groups"]["event"] == 0
    assert te["claims"]["descriptor"] == 0
    assert te["claims"]["state"] == 2
    assert te["claims"]["relation"] == 0
    assert te["claims"]["event"] == 0
    assert te["time_signature_report"]["current"] == "yes"
    assert te["time_signature_report"]["historical"] == "yes"
    assert te["time_signature_report"]["values"] == ["currently", "before March 2025"]
    assert te["space_signature_report"]["bounded"] == "yes"
    assert te["space_signature_report"]["values"] == ["London office"]
    assert te["evidence"]["claims"] == 2
    assert trace["technical_memory_chunks"][0]["entity_name"] == "Acme"
    assert trace["technical_memory_chunks"][0]["facts"][0]["claim_id"] == "c1"
    assert trace["search_profiles"][0]["entity_name"] == "Acme"
    assert trace["search_profiles"][0]["builder_version"] == "search_profile_builder_v1"
    assert trace["local_resolver_trace"]["resolver_version"] == "local_resolver_v1"
    assert trace["summary"]["similarity_boost_reason_count"] == 2
    assert "name:canonical_exact" in trace["summary"]["similarity_boost_reasons"]
    assert trace["summary"]["candidate_selection_attempted_count"] == 0
    assert trace["summary"]["candidate_pool_size"] == 1
    assert trace["summary"]["similarity_score_distribution"]["count"] == 2
    assert trace["summary"]["similarity_score_distribution"]["max"] == 0.92
    assert trace["summary"]["timeline_compatibility_reason_count"] == 1
    assert "temporal_change:different_time_values" in trace["summary"]["timeline_compatibility_reasons"]
    assert trace["summary"]["near_duplicate_guard_trigger_count"] == 2
    assert trace["summary"]["global_profile_count"] == 1
    assert trace["global_profiles"][0]["created_profile_id"] == "global-profile:te1"
    assert trace["summary"]["quality"]["rejected_noise_sentence_count"] == 2
    assert trace["summary"]["quality"]["bad_subject_claim_count"] == 3
    assert trace["summary"]["quality"]["bad_subject_claim_examples"][0]["subject_text"] == "This sentence"
    assert trace["summary"]["rejected_noise_sentence_count"] == 2
    assert trace["summary"]["bad_subject_claim_examples"][0]["reason"] == "claim_bad_subject"
    assert trace["summary"]["multilingual_alias_match_count"] >= 1
    assert trace["summary"]["candidate_duplicate_removed_count"] == 1
    candidate_ids = [item["candidate_entity_id"] for item in trace["candidate_selections"]]
    assert len(candidate_ids) == len(set(candidate_ids))
    similarity_keys = [
        (item.get("candidate_entity_id"), item.get("technical_entity_id") or item.get("search_profile_id"))
        for item in trace["similarity_analyses"]
    ]
    assert len(similarity_keys) == len(set(similarity_keys))
    assert trace["candidate_selections"][0]["candidate_name"] == "support modul"
    assert trace["summary"]["canonical_entity_merge_suggestion_count"] == 2
    assert trace["summary"]["unknown_entity_type_examples"] == ["Beta"]

    summary_trace = service.build_trace("run-lr", log_level="SUMMARY")
    assert summary_trace is not None
    assert summary_trace["log_level"] == "SUMMARY"
    assert summary_trace["sentences"] == []
    assert summary_trace["local_entities"] == []
    assert summary_trace["search_profiles"] == []
    assert len(summary_trace["similarity_analyses"]) <= 5
    assert len(summary_trace["candidate_selections"]) <= 5
    assert summary_trace["top_entities"][0]["canonical_name"] == "Acme"
    assert summary_trace["top_candidates"][0]["candidate_entity_id"] == "te-support"
    assert summary_trace["top_problems"]
    assert summary_trace["merge_events"]

    inspect_trace = service.build_trace("run-lr", log_level="INSPECT")
    assert inspect_trace is not None
    assert inspect_trace["log_level"] == "INSPECT"
    assert inspect_trace["search_profiles"] == []
    assert all(row["claims"] == [] for row in inspect_trace["sentences"])
    assert inspect_trace["local_entities"][0]["claim_ids"] == []
    assert inspect_trace["inspect"]["bad_subject_claim_examples"][0]["subject_text"] == "This sentence"

    debug_trace = service.build_trace("run-lr", log_level="SUMMARY", debug=True)
    assert debug_trace is not None
    assert debug_trace["log_level"] == "FULL_TRACE"
    assert debug_trace["search_profiles"][0]["entity_name"] == "Acme"


class _LocalClusterRepo:
    def __init__(self, clusters: list[LocalEntityCluster]) -> None:
        self._clusters = list(clusters)

    def list_by_run(self, _run_id: object) -> list[LocalEntityCluster]:
        return list(self._clusters)


def test_build_trace_prefers_persisted_local_entities() -> None:
    run = SimpleNamespace(id="run-db", status="completed", created_at=_ts())
    item = SimpleNamespace(source_id="source-db", display_name="Source item")
    source = SimpleNamespace(title="DB source", metadata={"language": "en"})
    document = SimpleNamespace(id="doc-db", language="en")
    sentence = SimpleNamespace(
        id="sentence-db",
        order_index=1,
        char_start=0,
        text_content="Example.",
        created_at=_ts(),
        metadata={"language": "en"},
    )
    interp_uuid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    persisted = LocalEntityCluster(
        canonical_name="Persisted Co",
        entity_type="company",
        normalized_key="persisted co",
        confidence=0.88,
        coherence_score=0.9,
        surface_forms=["Persisted Co"],
    )
    interpretation = SimpleNamespace(
        id=interp_uuid,
        metadata={
            "local_entity_cluster_count": 5,
            "local_entity_clusters": [{"local_entity_id": "meta-only", "canonical_name": "Ignored"}],
            "local_resolver_trace": None,
        },
    )
    service = KnowledgeTraceService(
        ingest_run_store=_SingleItemStore(run),
        ingest_item_store=_ListStore([item]),
        source_store=_SingleItemStore(source),
        document_store=SimpleNamespace(get_for_source=lambda _source_id: document),
        sentence_store=_ListStore([sentence]),
        mention_store=_ListStore([]),
        claim_store=_ListStore([]),
        space_time_frame_store=_ListStore([]),
        interpretation_run_store=_InterpretationStore(interpretation),
        local_entity_cluster_repository=_LocalClusterRepo([persisted]),
    )

    trace = service.build_trace("run-db")

    assert trace is not None
    assert trace["summary"]["local_entity_count"] == 1
    assert trace["summary"]["local_entity_cluster_count"] == 1
    assert trace["local_entities"][0]["canonical_name"] == "Persisted Co"
    assert trace["local_entity_clusters"][0]["canonical_name"] == "Ignored"


def test_build_trace_uses_persisted_quality_diagnostics() -> None:
    run = SimpleNamespace(
        id="run-3",
        status="completed",
        created_at=_ts(),
        metadata={
            "quality_diagnostics": {
                "skipped_sentence_count": 2,
                "rejected_claim_count": 5,
                "describes_claim_count": 1,
                "low_confidence_claim_count": 1,
                "bad_subject_claim_count": 2,
                "question_sentence_count": 1,
                "fragment_sentence_count": 1,
                "skipped_sentences": [{"reason": "sentence_is_question", "text": "What does it do?"}],
                "rejected_claim_examples": [{"reason": "claim_bad_subject", "subject_text": "the"}],
            }
        },
    )
    item = SimpleNamespace(source_id="source-3", display_name="Source item")
    source = SimpleNamespace(title="Trace source", metadata={"language": "en"})
    document = SimpleNamespace(id="doc-3", language="en")
    sentence = SimpleNamespace(id="sentence-3", order_index=1, char_start=0, text_content="The account was created.", created_at=_ts(), metadata={"language": "en"})
    service = KnowledgeTraceService(
        ingest_run_store=_SingleItemStore(run),
        ingest_item_store=_ListStore([item]),
        source_store=_SingleItemStore(source),
        document_store=SimpleNamespace(get_for_source=lambda _source_id: document),
        sentence_store=_ListStore([sentence]),
        mention_store=_ListStore([]),
        claim_store=_ListStore([]),
        space_time_frame_store=_ListStore([]),
    )

    trace = service.build_trace("run-3")

    assert trace is not None
    assert trace["summary"]["quality"]["skipped_sentence_count"] == 2
    assert trace["summary"]["quality"]["rejected_claim_count"] == 5
    assert trace["summary"]["quality"]["question_sentence_count"] == 1
    assert trace["summary"]["quality"]["skipped_sentences"][0]["reason"] == "sentence_is_question"
    assert "todo" not in trace["summary"]["quality"]


def test_build_trace_subject_context_summary_and_claim_report() -> None:
    run = SimpleNamespace(id="run-sc", status="completed", created_at=_ts())
    item = SimpleNamespace(source_id="source-sc", display_name="Source")
    source = SimpleNamespace(title="S", metadata={"language": "hu"})
    document = SimpleNamespace(id="doc-sc", language="hu")
    s0 = SimpleNamespace(id="sid-0", order_index=0, char_start=0, text_content="Kiss Márton vezető.", created_at=_ts(), metadata={"language": "hu"})
    s1 = SimpleNamespace(id="sid-1", order_index=1, char_start=0, text_content="Korábban felelt.", created_at=_ts(), metadata={"language": "hu"})
    c_keep = SimpleNamespace(
        claim_id="c-keep",
        claim_text="x",
        subject_text="Nagy Péter",
        predicate="p",
        object_text=None,
        claim_type="relation",
        claim_group="default",
        claim_status="active",
        confidence=0.7,
        identity_weight=0.0,
        similarity_weight=1.0,
        tension_weight=1.0,
        conflict_behavior="additive",
        cardinality="multi",
        time_mode="unknown",
        space_mode="unknown",
        created_at=_ts(),
        metadata={
            "context_subject_applied": False,
            "context_subject_reason": "explicit_subject_kept",
        },
    )
    c_skip = SimpleNamespace(
        claim_id="c-skip",
        claim_text="y",
        subject_text="",
        predicate="p",
        object_text=None,
        claim_type="relation",
        claim_group="default",
        claim_status="active",
        confidence=0.7,
        identity_weight=0.0,
        similarity_weight=1.0,
        tension_weight=1.0,
        conflict_behavior="additive",
        cardinality="multi",
        time_mode="unknown",
        space_mode="unknown",
        created_at=_ts(),
        metadata={
            "context_subject_applied": False,
            "context_subject_reason": "no_strong_anchor_in_previous_two_sentences",
        },
    )
    c_applied = SimpleNamespace(
        claim_id="c-applied",
        claim_text="z",
        subject_text="Kiss Márton",
        predicate="felelt",
        object_text="audit",
        claim_type="relation",
        claim_group="default",
        claim_status="active",
        confidence=0.7,
        identity_weight=0.0,
        similarity_weight=1.0,
        tension_weight=1.0,
        conflict_behavior="additive",
        cardinality="multi",
        time_mode="unknown",
        space_mode="unknown",
        created_at=_ts(),
        metadata={
            "context_subject_applied": True,
            "context_subject_source_sentence_id": "sid-0",
            "context_subject_source_claim_id": "c0",
            "context_subject_source_subject": "Kiss Márton",
            "context_subject_reason": "weak_subject_override",
        },
    )

    class _ClaimsBySentence:
        def list_for_sentence(self, sid: str):
            if sid == "sid-1":
                return [c_keep, c_skip, c_applied]
            return []

    service = KnowledgeTraceService(
        ingest_run_store=_SingleItemStore(run),
        ingest_item_store=_ListStore([item]),
        source_store=_SingleItemStore(source),
        document_store=SimpleNamespace(get_for_source=lambda _source_id: document),
        sentence_store=_ListStore([s0, s1]),
        mention_store=_ListStore([]),
        claim_store=_ClaimsBySentence(),
        space_time_frame_store=_ListStore([]),
    )
    trace = service.build_trace("run-sc")
    assert trace is not None
    sc = trace["summary"]["subject_context"]
    assert sc["context_subject_applied_count"] == 1
    assert sc["context_subject_skipped_count"] == 1
    assert sc["context_subject_reset_count"] == 1
    assert sc["context_subject_weak_subject_override_count"] == 1
    claims_row = trace["sentences"][1]["claims"]
    keep = next(c for c in claims_row if c["claim_id"] == "c-keep")
    assert keep["context_subject_applied"] == "no"
    rep = next(c for c in claims_row if c["claim_id"] == "c-applied")
    assert rep["context_subject_applied"] == "yes"
    assert rep["context_subject_source"] == "sentence #1"
    assert rep["context_subject_source_sentence_index"] == 0
    assert rep["context_subject_source_subject"] == "Kiss Márton"
    assert rep["context_subject_reason"] == "weak_subject_override"
    IngestRunTraceResponse.model_validate(trace)


def _claim(
    *,
    claim_id: str,
    subject_text: str,
    metadata: dict,
):
    return SimpleNamespace(
        claim_id=claim_id,
        claim_text="x",
        subject_text=subject_text,
        predicate="p",
        object_text=None,
        claim_type="relation",
        claim_group="default",
        claim_status="active",
        confidence=0.7,
        identity_weight=0.0,
        similarity_weight=1.0,
        tension_weight=1.0,
        conflict_behavior="additive",
        cardinality="multi",
        time_mode="unknown",
        space_mode="unknown",
        created_at=_ts(),
        metadata=metadata,
    )


def test_build_trace_summary_exposes_context_carryover_and_sanitizer_counters() -> None:
    """Spec: 5 új trace counter (additív, a régi subject_context blokk mellett megmarad)."""
    run = SimpleNamespace(id="run-cc", status="completed", created_at=_ts())
    item = SimpleNamespace(source_id="source-cc", display_name="Source")
    source = SimpleNamespace(title="S", metadata={"language": "hu"})
    document = SimpleNamespace(id="doc-cc", language="hu")
    s = SimpleNamespace(
        id="sid-cc",
        order_index=0,
        char_start=0,
        text_content="Mondat.",
        created_at=_ts(),
        metadata={"language": "hu"},
    )

    c_source_phrase = _claim(
        claim_id="c-sp",
        subject_text="admin felhasználó",
        metadata={
            "sanitizers_applied": ["source_phrase"],
            "context_subject_applied": False,
            "context_subject_reason": "explicit_subject_kept",
        },
    )
    c_suffix = _claim(
        claim_id="c-suf",
        subject_text="admin felhasználó",
        metadata={
            "sanitizers_applied": ["suffix_normalization"],
            "context_subject_applied": False,
            "context_subject_reason": "explicit_subject_kept",
        },
    )
    c_both = _claim(
        claim_id="c-both",
        subject_text="admin felhasználó",
        metadata={
            "sanitizers_applied": ["source_phrase", "suffix_normalization"],
            "context_subject_applied": False,
            "context_subject_reason": "explicit_subject_kept",
        },
    )
    c_blocked_with_subject = _claim(
        claim_id="c-blkd",
        subject_text="iroda",
        metadata={
            "context_subject_applied": False,
            "context_subject_reason": "incompatible_subject_context:user",
        },
    )
    c_blocked_missing = _claim(
        claim_id="c-mis",
        subject_text="",
        metadata={
            "context_subject_applied": False,
            "context_subject_reason": "no_strong_anchor_in_previous_two_sentences",
        },
    )
    c_applied = _claim(
        claim_id="c-app",
        subject_text="Kiss Márton",
        metadata={
            "context_subject_applied": True,
            "context_subject_source_sentence_id": "sid-0",
            "context_subject_source_subject": "Kiss Márton",
            "context_subject_reason": "weak_subject_override",
        },
    )

    class _ClaimsBySentence:
        def list_for_sentence(self, sid: str):
            return [c_source_phrase, c_suffix, c_both, c_blocked_with_subject, c_blocked_missing, c_applied]

    service = KnowledgeTraceService(
        ingest_run_store=_SingleItemStore(run),
        ingest_item_store=_ListStore([item]),
        source_store=_SingleItemStore(source),
        document_store=SimpleNamespace(get_for_source=lambda _source_id: document),
        sentence_store=_ListStore([s]),
        mention_store=_ListStore([]),
        claim_store=_ClaimsBySentence(),
        space_time_frame_store=_ListStore([]),
    )
    trace = service.build_trace("run-cc")
    assert trace is not None
    summary = trace["summary"]

    # Spec által kért 5 új mező a riport summary-ben:
    assert summary["context_carryover_applied_count"] == 1
    assert summary["context_carryover_blocked_count"] == 2  # incompatible + no_strong_anchor
    assert summary["source_phrase_stripped_count"] == 2  # c_source_phrase + c_both
    assert summary["subject_suffix_normalized_count"] == 2  # c_suffix + c_both
    assert summary["carryover_missing_subject_error_count"] == 1  # c_blocked_missing (üres subject)

    # Régi subject_context blokk változatlanul (workspace-rule: trace JSON kompatibilitás).
    sc = summary["subject_context"]
    assert sc["context_subject_applied_count"] == 1
    assert sc["context_subject_skipped_count"] >= 2
    assert sc["context_subject_weak_subject_override_count"] == 1

    IngestRunTraceResponse.model_validate(trace)
