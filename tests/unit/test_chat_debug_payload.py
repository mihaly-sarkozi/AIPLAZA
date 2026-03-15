from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from apps.chat.application.services.chat_service import ChatService


pytestmark = pytest.mark.unit


class _DummyKbService:
    def user_can_use(self, kb_uuid: str, user_id: int, user_role: str | None) -> bool:
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
    def user_can_use(self, kb_uuid: str, user_id: int, user_role: str | None) -> bool:
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


class _DummyCompletions:
    async def create(self, model: str, messages: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Teszt válasz"))]
        )


class _DummyOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_DummyCompletions())


def test_chat_with_sources_debug_payload_contains_counts_and_preview():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
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


def test_chat_with_sources_debug_payload_handles_empty_context():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
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

    assert result["debug"]["top_assertion_count"] == 0
    assert result["debug"]["evidence_sentence_count"] == 0
    assert result["debug"]["source_chunk_count"] == 0
    assert result["debug"]["related_entity_count"] == 0
    assert result["debug"]["context_preview"] == ""
