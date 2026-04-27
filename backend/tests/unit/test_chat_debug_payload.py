from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from apps.chat.service.chat_service import ChatService


pytestmark = pytest.mark.unit


class _DummyKbService:
    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:
        return True

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
    ) -> dict:
        return {
            "query_focus": parsed_query,
            "top_assertions": [
                {
                    "id": "assertion-1",
                    "text": "Alice Budapesten dolgozik.",
                    "kb_uuid": "kb-1",
                    "source_point_id": "p-1",
                }
            ],
            "evidence_sentences": [
                {
                    "sentence_id": 11,
                    "assertion_id": 1,
                    "text": "Alice telefonszáma +36123456789, Budapesten dolgozik.",
                    "kb_uuid": "kb-1",
                    "source_point_id": "p-1",
                }
            ],
            "source_chunks": [
                {
                    "chunk_id": 21,
                    "text": "Kapcsolat: alice@example.com. Alice Budapesten dolgozik.",
                    "kb_uuid": "kb-1",
                    "source_point_id": "p-1",
                }
            ],
            "related_entities": [{"canonical_name": "Alice"}],
            "scoring_summary": {"retrieval_mode": "assertion_first"},
        }


class _EmptyKbService:
    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:
        return True

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
    ) -> dict:
        return {
            "query_focus": parsed_query,
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": [],
            "related_entities": [],
            "scoring_summary": {},
        }


class _SynthesizedAnswerKbService:
    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:
        return True

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
    ) -> dict:
        return {
            "answer_text": "The London office is currently inactive. Historically, it was inactive in 2024.",
            "answer_mode": "historical",
            "query_focus": parsed_query,
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": [
                {
                    "id": "chunk-1",
                    "kb_uuid": "kb-1",
                    "source_point_id": "p-1",
                    "source_document_title": "London source",
                    "text": "London office (location)\nCurrent facts:\n- currently inactive",
                }
            ],
            "related_entities": [],
            "scoring_summary": {},
        }


class _BuildChatContextKbService:
    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:
        return True

    async def build_chat_context(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> dict:
        return {
            "query_run_id": "qr-1",
            "answer_text": "The London office is currently inactive.",
            "answer_mode": "direct",
            "synthesis_confidence": 0.82,
            "evidence_summary": [
                {
                    "claim_id": "c-current",
                    "sentence_id": "s-current",
                    "source_id": "src-london",
                    "claim_text": "The London office is currently inactive.",
                }
            ],
            "cited_claim_ids": ["c-current"],
            "cited_sentence_ids": ["s-current"],
            "cited_source_ids": ["src-london"],
            "query_profile": {"intent": "state"},
            "matched_chunks": [{"entity_name": "London office"}],
            "matched_claims": [{"claim_id": "c-current"}],
            "source_chunks": [
                {
                    "id": "chunk-1",
                    "kb_uuid": kb_uuid or "",
                    "source_point_id": "p-1",
                    "source_id": "src-london",
                    "source_document_title": "London source",
                    "source_type": "text",
                    "file_ref": None,
                    "text": "London office (location)",
                }
            ],
            "scoring_summary": {},
        }


class _NoReadyIndexKbService:
    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:
        return True

    async def build_chat_context(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> dict:
        return {
            "no_ready_index_build": True,
            "answer_text": "",
            "source_chunks": [],
            "top_assertions": [],
            "evidence_sentences": [],
            "scoring_summary": {},
        }


class _DummyCompletions:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, model: str, messages: list[dict]) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Teszt válasz"))]
        )


class _DummyOpenAI:
    def __init__(self) -> None:
        self.completions = _DummyCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def test_chat_with_sources_debug_payload_contains_counts_and_preview():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_DummyKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="Hol dolgozik Alice?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=True,
        )
    )

    assert result["answer"] == "Teszt válasz"
    assert result["debug"]["top_assertion_count"] == 1
    assert result["debug"]["evidence_sentence_count"] == 1
    assert result["debug"]["source_chunk_count"] == 1
    assert result["debug"]["related_entity_count"] == 1
    assert result["debug"]["top_assertion_ids"] == ["assertion-1"]
    assert result["debug"]["source_point_ids"] == ["p-1"]
    assert len(result["debug"]["context_preview"]) <= 403
    assert "[redacted_email]" in result["debug"]["context_preview"] or "[redacted_phone]" in result["debug"]["context_preview"]
    assert model.completions.calls == 1


def test_chat_with_sources_debug_payload_handles_empty_context():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_EmptyKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="Nincs találat?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=True,
        )
    )

    assert result["answer"] == ""
    assert result["debug"]["top_assertion_count"] == 0
    assert result["debug"]["evidence_sentence_count"] == 0
    assert result["debug"]["source_chunk_count"] == 0
    assert result["debug"]["related_entity_count"] == 0
    assert result["debug"]["context_preview"] == ""
    assert model.completions.calls == 0


def test_chat_with_sources_returns_synthesized_answer_without_llm_call():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_SynthesizedAnswerKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="What is the status of London office?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=True,
        )
    )

    assert result["answer"] == "The London office is currently inactive. Historically, it was inactive in 2024."
    assert result["answer_source"] == "knowledge"
    assert result["sources"][0]["point_id"] == "p-1"
    assert result["debug"]["source_chunk_count"] == 1
    assert model.completions.calls == 0


def test_chat_with_sources_uses_build_chat_context_facade_adapter():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_BuildChatContextKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="What is the status of London office?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=True,
        )
    )

    assert result["answer"] == "The London office is currently inactive."
    assert result["query_run_id"] == "qr-1"
    assert result["answer_mode"] == "direct"
    assert result["answer_source"] == "knowledge"
    assert result["confidence"] == 0.82
    assert result["evidence"][0]["claim_id"] == "c-current"
    assert result["cited_claim_ids"] == ["c-current"]
    assert result["query_profile"] == {"intent": "state"}
    assert result["matched_chunks"] == [{"entity_name": "London office"}]
    assert result["claims"] == [{"claim_id": "c-current"}]
    assert result["debug"]["query_profile"] == {"intent": "state"}
    assert result["debug"]["matched_chunks"] == [{"entity_name": "London office"}]
    assert result["debug"]["claims"] == [{"claim_id": "c-current"}]
    assert result["sources"][0]["kb_uuid"] == "kb-1"
    assert result["sources"][0]["source_id"] == "src-london"
    assert result["sources"][0]["source_type"] == "text"
    assert model.completions.calls == 0


def test_chat_sources_skip_vector_profile_rows_without_downloadable_source_id():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
        kb_service=None,
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    sources = svc._build_sources_from_packet(
        {
            "source_chunks": [
                {
                    "id": "profile-row",
                    "kb_uuid": "kb-1",
                    "source_point_id": "236d02a6-9df0-5b47-a4d9-6a44a8efef1b",
                    "build_id": "index-build-1",
                    "source_document_title": "Vector profile row",
                },
                {
                    "id": "source-row",
                    "kb_uuid": "kb-1",
                    "source_point_id": "source-real",
                    "source_id": "source-real",
                    "source_document_title": "London policy.pdf",
                    "display_type": "PDF",
                    "created_by_label": "Felhasználó #11",
                },
            ]
        }
    )

    assert len(sources) == 1
    assert sources[0]["source_id"] == "source-real"
    assert sources[0]["title"] == "London policy.pdf"


def test_chat_sources_fallback_to_cited_source_ids_when_source_chunks_are_missing():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
        kb_service=None,
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    sources = svc._build_sources_from_packet(
        {
            "kb_uuid": "kb-1",
            "cited_source_ids": ["source-real"],
            "evidence_summary": [{"source_id": "source-real"}],
        }
    )

    assert len(sources) == 1
    assert sources[0]["kb_uuid"] == "kb-1"
    assert sources[0]["source_id"] == "source-real"
    assert sources[0]["title"] == "Forrás source-r"


def test_chat_with_sources_reports_missing_ready_index_build():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_NoReadyIndexKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="What is the status of London office?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=True,
        )
    )

    assert "nincs kész keresési index" in result["answer"]
    assert model.completions.calls == 0
