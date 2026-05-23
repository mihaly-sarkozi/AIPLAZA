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


class _MultiKbReadyButNoMatchService:
    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:
        return True

    def list_all(self, current_user_id: int, current_user):
        return [SimpleNamespace(uuid="kb-1", name="KB 1", deleted_at=None)]

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
    ) -> dict:
        return {
            "no_ready_index_build": False,
            "answer_text": "",
            "source_chunks": [],
            "top_assertions": [],
            "evidence_sentences": [],
            "scoring_summary": {},
        }


class _MultiKbDiagnosticsService:
    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:
        return True

    def list_all(self, current_user_id: int, current_user):
        return [
            SimpleNamespace(uuid="kb-1", name="KB 1", deleted_at=None),
            SimpleNamespace(uuid="kb-2", name="KB 2", deleted_at=None),
            SimpleNamespace(uuid="kb-3", name="KB 3", deleted_at=None),
        ]

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> dict:
        if kb_uuid == "kb-1":
            return {
                "retrieval_confidence": 0.9,
                "answer_text": "",
                "context_blocks": [
                    {
                        "kb_uuid": "kb-1",
                        "block_id": "block-1",
                        "source_id": "src-1",
                        "subject": "Péter",
                        "snippet": "Péter kék szemű.",
                        "match_score": 4.2,
                    }
                ],
                "source_chunks": [
                    {
                        "id": "chunk-1",
                        "kb_uuid": "kb-1",
                        "source_point_id": "p-1",
                        "source_id": "src-1",
                        "source_document_title": "Teszt forrás",
                        "text": "Péter kék szemű.",
                    }
                ],
                "scoring_summary": {"result_count": 1},
            }
        return {
            "retrieval_confidence": 0.8,
            "answer_text": "",
            "context_blocks": [],
            "source_chunks": [],
            "scoring_summary": {"result_count": 0},
            "no_ready_index_build": False,
        }


class _ChunkIdOnlyKbService:
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
            "answer_text": "",
            "source_chunks": [
                {
                    "id": "chunk-1",
                    "kb_uuid": "kb-1",
                    "source_document_title": "Teszt forrás",
                    "text": "Péter magas és kék szemű.",
                }
            ],
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


class _PolicyRefusalCompletions:
    async def create(self, model: str, messages: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            "Az adott név adatvédelmi okból tokenizálva van; "
                            "a teljes választ a felület automatikusan visszacseréli."
                        )
                    )
                )
            ]
        )


class _PolicyRefusalOpenAI:
    def __init__(self) -> None:
        self.completions = _PolicyRefusalCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class _PiiSpanStub:
    def detect_plain_spans(self, *, text: str, enabled: bool, sensitivity: str = "medium"):
        if not enabled:
            return []
        raw = str(text or "")
        marker = "Péter"
        idx = raw.find(marker)
        if idx < 0:
            return []
        return [{"start": idx, "end": idx + len(marker), "token": None, "value": marker, "entity_type": "person"}]


class _DirectPiiAnswerKbService:
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
            "answer_text": "Péter kék szemű.",
            "answer_mode": "direct",
            "synthesis_confidence": 0.95,
            "pii_depersonalization_enabled": True,
            "personal_data_sensitivity": "medium",
            "source_chunks": [
                {
                    "id": "chunk-1",
                    "kb_uuid": kb_uuid or "kb-1",
                    "source_point_id": "p-1",
                    "source_id": "src-1",
                    "source_document_title": "Teszt forrás",
                    "text": "Péter kék szemű.",
                }
            ],
            "scoring_summary": {"result_count": 1},
        }


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

    assert result["answer"] == "Nem találtam releváns választ a kiválasztott tudástárban."
    assert result["debug"]["top_assertion_count"] == 0
    assert result["debug"]["evidence_sentence_count"] == 0
    assert result["debug"]["source_chunk_count"] == 0
    assert result["debug"]["related_entity_count"] == 0
    assert result["debug"]["context_preview"] == ""
    assert model.completions.calls == 0


def test_chat_with_sources_rewrites_weak_synthesized_answer_with_context_llm():
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

    assert result["answer"] == "Teszt válasz"
    assert result["answer_source"] == "knowledge_llm"
    assert result["sources"][0]["point_id"] == "p-1"
    assert result["debug"]["source_chunk_count"] == 1
    assert model.completions.calls == 1


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


def test_chat_with_sources_rewrites_english_direct_answer_for_hungarian_question():
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
            question="Mi a londoni iroda státusza?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=True,
        )
    )

    assert result["answer"] == "Teszt válasz"
    assert result["answer_source"] == "knowledge_llm"
    assert model.completions.calls == 1


def test_build_messages_requires_answer_language_to_match_question():
    messages = ChatService._build_messages(
        question="Mi a londoni iroda státusza?",
        context_text="Current facts:\n- The London office is inactive.",
    )

    assert "A válasz nyelve mindig egyezzen meg" in messages[1]["content"]
    assert "magyar kérdésre magyarul" in messages[1]["content"]


def test_build_messages_includes_conversation_history_before_knowledge_context():
    messages = ChatService._build_messages(
        question="És mit tud még?",
        context_text="Knowledge block: SK MAX rendszer kezeli a szerződéseket.",
        conversation_history=[
            {"role": "user", "content": "Mit csinál az SK MAX rendszer?"},
            {"role": "assistant", "content": "Az SK MAX szerződéseket kezel."},
        ],
    )

    assert "Beszélgetési előzmény" in messages[1]["content"]
    assert "Mit csinál az SK MAX rendszer?" in messages[1]["content"]
    assert "Knowledge block" in messages[2]["content"]


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


def test_chat_sources_fallback_to_context_block_source_ids_when_citations_are_missing():
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
            "context_blocks": [{"block_id": "block-2", "source_id": "source-second-doc"}],
        }
    )

    assert len(sources) == 1
    assert sources[0]["kb_uuid"] == "kb-1"
    assert sources[0]["source_id"] == "source-second-doc"


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

    assert result["answer"] == "Nem találtam releváns választ a kiválasztott tudástárban."
    assert model.completions.calls == 0


def test_chat_with_sources_all_kb_no_match_does_not_report_missing_index():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_MultiKbReadyButNoMatchService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="Kinek kék a szeme?",
            user_id=1,
            user_role="owner",
            kb_uuid=None,
            debug=True,
        )
    )

    assert "nincs kész keresési index" not in result["answer"]
    assert model.completions.calls == 0


def test_chat_with_sources_all_kb_debug_reports_processed_candidate_count():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_MultiKbDiagnosticsService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="Milyen szeme van Péternek?",
            user_id=1,
            user_role="owner",
            kb_uuid=None,
            debug=True,
        )
    )

    index_debug = result["prompt_context"]["index_debug"]
    scoring_summary = index_debug["scoring_summary"]
    diagnostics = index_debug["multi_kb_diagnostics"]
    assert scoring_summary["kb_count"] == 3
    assert scoring_summary["kb_qualified_count"] == 1
    assert diagnostics["candidate_kb_count"] == 3
    assert diagnostics["processed_kb_count"] == 3
    assert diagnostics["context_kb_count"] == 1
    assert diagnostics["empty_context_kb_count"] == 2


def test_chat_with_sources_maps_source_chunk_id_as_point_id():
    model = _DummyOpenAI()
    svc = ChatService(
        chat_model=model,
        kb_service=_ChunkIdOnlyKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="Kinek kék a szeme?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=True,
        )
    )

    assert result["answer"] == "Teszt válasz"
    assert result["sources"][0]["point_id"] == "chunk-1"
    assert result["sources"][0]["title"] == "Teszt forrás"
    assert model.completions.calls == 1


def test_chat_with_sources_hides_pii_policy_refusal_text_from_user():
    svc = ChatService(
        chat_model=_PolicyRefusalOpenAI(),
        kb_service=_ChunkIdOnlyKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="Kinek kék a szeme?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=False,
        )
    )

    assert result["answer"] == "Nincs elegendő információ a válaszhoz a kiválasztott tudástár alapján."


def test_strong_entity_candidates_ignores_verb_phrases_but_keeps_name_tokens():
    candidates = ChatService._strong_entity_candidates(
        {
            "entity_candidates": [
                "van Péternek",
                "Péternek",
                "szeme van",
            ]
        }
    )

    assert "peter" in candidates
    assert "szeme" not in candidates


def test_direct_knowledge_answer_includes_pii_spans_for_highlight():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
        kb_service=_DirectPiiAnswerKbService(),
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
        pii_depersonalization_service=_PiiSpanStub(),
    )

    result = asyncio.run(
        svc.chat_with_sources(
            question="Milyen szeme van Péternek?",
            user_id=1,
            user_role="owner",
            kb_uuid="kb-1",
            debug=False,
        )
    )

    spans = result.get("restored_pii_spans") or []
    assert result["answer_source"] == "knowledge"
    assert any(str(span.get("value") or "") == "Péter" for span in spans)


def test_extract_place_candidates_does_not_derive_place_from_question_word():
    places = ChatService._extract_place_candidates("Milyen szeme van péternek?")

    assert "Mily" not in places


def test_strong_entity_candidates_lexical_hint_skips_attribute_words():
    candidates = ChatService._strong_entity_candidates(
        {
            "entity_candidates": [],
            "lexical_focus_terms": ["szemének", "péternek"],
        }
    )

    assert "peter" in candidates
    assert "szeme" not in candidates


def test_extract_entity_candidates_strips_question_prefix_and_keeps_name():
    candidates = ChatService._extract_entity_candidates("Milyen Péter?")

    assert "Milyen Péter" not in candidates
    assert "Mily Péter" not in candidates
    assert "Péter" in candidates


def test_extract_entity_candidates_skips_verb_driven_bigram():
    candidates = ChatService._extract_entity_candidates("mit tudsz péterről?")

    assert "tudsz péterről" not in candidates


def test_strong_entity_candidates_accepts_lowercase_name_token():
    candidates = ChatService._strong_entity_candidates(
        {
            "entity_candidates": ["péter"],
            "lexical_focus_terms": [],
        }
    )

    assert "peter" in candidates


def test_text_matches_strong_entity_uses_token_boundaries():
    assert not ChatService._text_matches_strong_entity(
        "kamatjövedelmet a magánszemély - jellemzően -",
        ["szeme"],
    )


def test_merge_context_packets_keeps_only_entity_relevant_rows():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
        kb_service=None,
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )
    merged = svc._merge_context_packets(
        [
            {
                "kb_uuid": "kb-1",
                "retrieval_confidence": 0.9,
                "context_blocks": [
                    {"block_id": "b-1", "source_id": "src-1", "subject": "Péter", "snippet": "Péter kék szemű.", "match_score": 4.2},
                ],
                "source_chunks": [
                    {"id": "src-1", "source_id": "src-1", "text": "Péter kék szemű."},
                ],
                "scoring_summary": {"result_count": 1},
            },
            {
                "kb_uuid": "kb-2",
                "retrieval_confidence": 0.92,
                "context_blocks": [
                    {"block_id": "b-2", "source_id": "src-2", "subject": "Házőrző biztosítás", "snippet": "Biztosítási feltételek.", "match_score": 4.5},
                ],
                "source_chunks": [
                    {"id": "src-2", "source_id": "src-2", "text": "Házőrző biztosítási feltételek."},
                ],
                "scoring_summary": {"result_count": 1},
            },
        ],
        kb_names={"kb-1": "KB 1", "kb-2": "KB 2"},
        parsed={"entity_candidates": [], "lexical_focus_terms": ["péternek"], "parse_time_ms": 0.0},
        no_ready_index_build=False,
    )

    kept_blocks = merged.get("context_blocks") or []
    kept_chunks = merged.get("source_chunks") or []
    assert len(kept_blocks) == 1
    assert kept_blocks[0]["source_id"] == "src-1"
    assert len(kept_chunks) == 1
    assert kept_chunks[0]["source_id"] == "src-1"


def test_merge_context_packets_sets_effective_kb_for_single_qualified_packet():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
        kb_service=None,
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )
    merged = svc._merge_context_packets(
        [
            {
                "kb_uuid": "kb-1",
                "retrieval_confidence": 0.9,
                "pii_depersonalization_enabled": True,
                "personal_data_sensitivity": "high",
                "context_blocks": [
                    {"block_id": "b-1", "source_id": "src-1", "subject": "Péter", "snippet": "Péter kék szemű.", "match_score": 4.2},
                ],
                "source_chunks": [
                    {"id": "src-1", "source_id": "src-1", "text": "Péter kék szemű."},
                ],
                "scoring_summary": {"result_count": 1},
            }
        ],
        kb_names={"kb-1": "KB 1"},
        parsed={"entity_candidates": ["Péter"], "lexical_focus_terms": [], "parse_time_ms": 0.0},
        no_ready_index_build=False,
    )

    assert merged["kb_uuid"] == "kb-1"
    assert merged["corpus_uuid"] == "kb-1"
    assert merged["pii_depersonalization_enabled"] is True
    assert merged["personal_data_sensitivity"] == "high"


def test_merge_context_packets_uses_non_entity_fallback_for_attribute_followup():
    svc = ChatService(
        chat_model=_DummyOpenAI(),
        kb_service=None,
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
    )
    merged = svc._merge_context_packets(
        [
            {
                "kb_uuid": "kb-1",
                "retrieval_confidence": 0.7,
                "context_blocks": [
                    {"block_id": "b-1", "source_id": "src-1", "subject": "Péter", "snippet": "Péter útlevélszáma PW897654.", "match_score": 0.9},
                ],
                "source_chunks": [
                    {"id": "src-1", "source_id": "src-1", "text": "Péter útlevélszáma PW897654."},
                ],
                "scoring_summary": {"result_count": 1},
            }
        ],
        kb_names={"kb-1": "KB 1"},
        parsed={"entity_candidates": ["utlevel szama"], "lexical_focus_terms": ["utlevel", "szama"], "parse_time_ms": 0.0},
        no_ready_index_build=False,
    )

    assert (merged.get("scoring_summary") or {}).get("kb_qualified_count") == 1
    assert (merged.get("context_blocks") or [])
    reasons = merged.get("filtered_out_reason") or []
    assert any("entity_gate_fallback" in str(reason) for reason in reasons)
