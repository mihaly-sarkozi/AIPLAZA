from __future__ import annotations

import asyncio
import json

import pytest

from apps.chat.application.services.chat_service import ChatService
from apps.knowledge.application.context_builder import KnowledgeContextBuilder
from apps.knowledge.application.evaluation import RetrievalEvaluationService
from apps.knowledge.application.retrieval_service import KnowledgeRetrievalService
from apps.knowledge.application.reranker import compute_recency_score

pytestmark = pytest.mark.unit


def test_hybrid_or_fusion_retrieval_improves_candidate_mix():
    svc = KnowledgeRetrievalService(kb_service=None)
    packet = {
        "top_assertions": [
            {"id": "assertion-1", "final_score": 0.82, "semantic_match": 0.86, "lexical_match": 0.05},
            {"id": "assertion-2", "final_score": 0.76, "semantic_match": 0.74, "lexical_match": 0.95},
        ]
    }
    out = svc._apply_candidate_fusion(packet)
    ids = [x["id"] for x in out["top_assertions"]]
    assert len(ids) == 2
    assert "assertion-2" in ids  # lexikailag erős jelölt is top mixbe kerül


def test_context_builder_respects_token_budget(monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "kb_context_token_budget", 80)
    builder = KnowledgeContextBuilder()
    long_text = "Ez egy hosszú mondat " * 30
    packet = builder.build_context_packet(
        assertion_hits=[
            {"id": "assertion-1", "text": long_text, "semantic_match": 0.9, "entity_match": 0.7, "time_match": 0.2, "place_match": 0.0, "graph_proximity": 0.2, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
            {"id": "assertion-2", "text": long_text, "semantic_match": 0.89, "entity_match": 0.7, "time_match": 0.2, "place_match": 0.0, "graph_proximity": 0.2, "strength": 0.6, "confidence": 0.7, "recency": 0.5},
        ],
        sentence_hits=[{"id": "sentence-1", "text": long_text, "semantic_match": 0.6, "entity_match": 0.0, "time_match": 0.0, "place_match": 0.0, "graph_proximity": 0.0, "strength": 0.0, "confidence": 0.0, "recency": 0.5}],
        chunk_hits=[{"id": "chunk-1", "text": long_text, "semantic_match": 0.5, "entity_match": 0.0, "time_match": 0.0, "place_match": 0.0, "graph_proximity": 0.0, "strength": 0.0, "confidence": 0.0, "recency": 0.5}],
        query_focus={"intent": "summary"},
    )
    assert packet["scoring_summary"]["estimated_tokens"] <= packet["scoring_summary"]["token_budget"]


def test_timeline_prompt_template_differs_from_summary_template():
    svc = ChatService(chat_model=object(), kb_service=None, retrieval_service=None, query_parser=None, context_builder=None)  # type: ignore[arg-type]
    timeline = svc._context_text_from_packet(
        {
            "query_focus": {"intent": "timeline", "retrieval_mode": "timeline_first"},
            "summary_assertions": [{"text": "Első"}, {"text": "Második"}],
            "timeline_sequence": [{"time_from": "2024-01-01", "text": "Első"}],
        }
    )
    summary = svc._context_text_from_packet(
        {
            "query_focus": {"intent": "summary", "retrieval_mode": "assertion_first"},
            "summary_assertions": [{"text": "Első"}, {"text": "Második"}],
        }
    )
    assert timeline != summary
    assert "Chronology" in timeline


def test_latency_metrics_are_recorded():
    class _KB:
        async def build_context_for_chat(self, **kwargs):
            _ = kwargs
            return {"top_assertions": [], "related_entities": [], "evidence_sentences": [], "scoring_summary": {}}

    svc = KnowledgeRetrievalService(kb_service=_KB())
    packet = asyncio.run(
        svc.build_context_for_chat(
            question="teszt",
            current_user_id=1,
            current_user_role="owner",
            parsed_query={"retrieval_mode": "assertion_first"},
            debug=True,
        )
    )
    assert "retrieval_service_ms" in packet["scoring_summary"]


def test_feedback_capture_persists_trace():
    class _KB:
        async def build_context_for_chat(self, **kwargs):
            _ = kwargs
            return {"top_assertions": [{"id": "assertion-1"}], "seed_assertions": [], "expanded_assertions": [], "related_entities": [], "evidence_sentences": [], "scoring_summary": {}}

    svc = KnowledgeRetrievalService(kb_service=_KB())
    packet = asyncio.run(
        svc.build_context_for_chat(
            question="teszt",
            current_user_id=1,
            current_user_role="owner",
            parsed_query={"retrieval_mode": "assertion_first"},
            debug=True,
        )
    )
    trace_id = packet["scoring_summary"].get("trace_id")
    out = svc.capture_feedback(trace_id=trace_id, helpful=True, context_useful=True)
    assert out["status"] == "ok"
    assert svc.list_feedback(limit=1)[0]["trace_id"] == trace_id


def test_trace_rows_are_persisted_to_jsonl(tmp_path, monkeypatch):
    from config.settings import settings

    trace_file = tmp_path / "retrieval_traces.jsonl"
    monkeypatch.setattr(settings, "kb_debug_trace_persist", True)
    monkeypatch.setattr(settings, "kb_debug_trace_path", str(trace_file))

    class _KB:
        async def build_context_for_chat(self, **kwargs):
            _ = kwargs
            return {"top_assertions": [{"id": "assertion-1"}], "seed_assertions": [], "expanded_assertions": [], "related_entities": [], "evidence_sentences": [], "scoring_summary": {}}

    svc = KnowledgeRetrievalService(kb_service=_KB())
    packet = asyncio.run(
        svc.build_context_for_chat(
            question="teszt trace",
            current_user_id=1,
            current_user_role="owner",
            parsed_query={"retrieval_mode": "assertion_first"},
            debug=True,
        )
    )
    svc.capture_feedback(trace_id=packet["scoring_summary"].get("trace_id"), helpful=True)
    lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    assert any("trace_id" in json.loads(line) for line in lines if line.strip())


def test_weight_suggestion_runs_on_eval_output():
    output = {
        "metrics": {"time_correctness": 0.5, "entity_recall": 0.6, "average_context_size": 40},
        "query_family_report": {"relation": {"entity_recall": 0.6}},
    }
    suggestions = RetrievalEvaluationService.suggest_weight_adjustments(output)
    assert suggestions and isinstance(suggestions, list)


def test_fallback_hierarchy_uses_chunk_only_as_last_resort():
    order = KnowledgeRetrievalService.resolve_fallback_hierarchy(assertion_hits=0, entity_hits=1, sentence_hits=0)
    assert order[-1] == "chunk_fallback"
    assert order[0] != "chunk_fallback"


def test_recency_uses_source_or_ingest_time_not_valid_time():
    recent = compute_recency_score(source_time="2026-03-14T00:00:00", ingest_time=None)
    old = compute_recency_score(source_time="2020-01-01T00:00:00", ingest_time=None)
    assert recent > old


def test_assertion_first_guard_prevents_chunk_only_prompt():
    svc = ChatService(chat_model=object(), kb_service=None, retrieval_service=None, query_parser=None, context_builder=None)  # type: ignore[arg-type]
    txt = svc._context_text_from_packet(
        {
            "query_focus": {"intent": "summary", "retrieval_mode": "assertion_first"},
            "top_assertions": [],
            "evidence_sentences": [{"text": "csak mondat"}],
            "source_chunks": [{"text": "csak chunk"}],
        }
    )
    assert txt == ""
