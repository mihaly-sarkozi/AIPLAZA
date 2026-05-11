from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace

import pytest

from apps.chat.service.chat_service import ChatPolicyViolationError, ChatService, PiiDepersonalizationUnavailableError
from apps.chat.service.pii_depersonalization import EncodedPiiText, PiiDepersonalizationService, RehydratedPiiText

_PII_AUDIT_ACTION = "knowledge_pii_depersonalized"

pytestmark = pytest.mark.unit


class _BrokenPiiService:
    def encode_text(self, **_kwargs):
        raise RuntimeError("simulated pii encode failure")


class _AuditStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def log(self, action, **kwargs):
        self.calls.append({"action": action, **kwargs})


class _PiiOkService:
    def encode_text(self, *, text: str, **_kwargs):
        token = "[person_1]" if "Péter" in text else "[ctx_1]"
        return EncodedPiiText(
            text=text.replace("Péter", token),
            mappings=[{"token": token, "entity_type": "person"}],
        )

    def rehydrate_text(self, *, text: str, **_kwargs):
        return RehydratedPiiText(text=text.replace("[person_1]", "Péter"), restored_spans=[])


class _SuffixBlindPiiService:
    def encode_text(self, *, text: str, **_kwargs):
        raw = str(text or "")
        if "Péter " in raw or raw.startswith("Péter"):
            return EncodedPiiText(
                text=raw.replace("Péter", "[person_1]"),
                mappings=[{"token": "[person_1]", "entity_type": "person", "original_preview": "Péter"}],
            )
        return EncodedPiiText(text=raw, mappings=[])

    def rehydrate_text(self, *, text: str, **_kwargs):
        return RehydratedPiiText(text=str(text or "").replace("[person_1]", "Péter"), restored_spans=[])


class _FakeMappingRepo:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str, str], str] = {}
        self._values: dict[tuple[str, str], str] = {}
        self._seq_by_type: dict[tuple[str, str], int] = {}

    def resolve_or_create_token(self, *, corpus_uuid: str, entity_type: str, original_value: str) -> str:
        key = (corpus_uuid, entity_type, original_value.strip().lower())
        existing = self._by_key.get(key)
        if existing:
            return existing
        seq_key = (corpus_uuid, entity_type)
        next_idx = int(self._seq_by_type.get(seq_key, 0)) + 1
        self._seq_by_type[seq_key] = next_idx
        token = f"[{entity_type}_{next_idx}]"
        self._by_key[key] = token
        self._values[(corpus_uuid, token)] = original_value
        return token

    def resolve_tokens(self, *, corpus_uuid: str, tokens: list[str]) -> dict[str, str]:
        return {
            token: value
            for token in tokens
            if (value := self._values.get((corpus_uuid, token))) is not None
        }


def test_chat_with_sources_fails_closed_when_pii_encode_breaks():
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: None)))
    audit = _AuditStub()
    svc = ChatService(chat_model=client, pii_depersonalization_service=_BrokenPiiService(), audit_service=audit)

    async def _fake_context_packet(**_kwargs):
        return {
            "kb_uuid": "kb-1",
            "pii_depersonalization_enabled": True,
            "personal_data_sensitivity": "medium",
        }

    svc._build_context_packet = _fake_context_packet  # type: ignore[method-assign]
    svc._context_text_from_packet = lambda _packet: "Péter személyi száma AU123456"  # type: ignore[method-assign]

    with pytest.raises(PiiDepersonalizationUnavailableError):
        asyncio.run(
            svc.chat_with_sources(
                "Mi a státusz?",
                user_id=7,
                user_role="owner",
                kb_uuid="kb-1",
            )
        )
    assert any(call.get("action") == _PII_AUDIT_ACTION for call in audit.calls)
    assert any(str(call.get("outcome")) == "failure" for call in audit.calls)


def test_llm_context_text_uses_only_chunk_snippets() -> None:
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: None)))
    svc = ChatService(chat_model=client, pii_depersonalization_service=None)
    packet = {
        "context_blocks": [
            {"snippet": "Péter magas és kék szemű, személyi azonosító AU123456", "subject": "Péter"},
        ],
        "primary_assertions": [
            {"text": "Péter magas és kék szemű."},
        ],
        "source_chunks": [
            {"text": "[n_v_1] magas és kék szemű, személyi azonosító [szem_lyi_azonos_t_1]"},
        ],
    }

    llm_context = svc._llm_context_text_from_packet(packet)

    assert "Context chunks:" in llm_context
    assert "Knowledge blocks:" not in llm_context
    assert "Primary assertions:" not in llm_context
    assert "Péter" not in llm_context


@pytest.mark.release_acceptance
def test_chat_with_sources_stops_when_kb_access_denied() -> None:
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: None)))
    svc = ChatService(chat_model=client, pii_depersonalization_service=None)

    async def _denied_context_packet(**_kwargs):
        raise PermissionError("denied")

    svc._build_context_packet = _denied_context_packet  # type: ignore[method-assign]

    with pytest.raises(PermissionError):
        asyncio.run(
            svc.chat_with_sources(
                "Mi a státusz?",
                user_id=7,
                user_role="owner",
                kb_uuid="kb-1",
            )
        )


def test_chat_with_sources_logs_successful_pii_encode_audit_and_metrics(monkeypatch) -> None:
    metrics_calls: list[tuple[str, float, dict | None]] = []
    observations: list[tuple[str, float, str, dict | None]] = []

    import apps.chat.service.chat_service as chat_service_module

    monkeypatch.setattr(
        chat_service_module,
        "increment_metric",
        lambda name, value, tags=None: metrics_calls.append((name, value, tags)),
    )
    monkeypatch.setattr(
        chat_service_module,
        "observe_metric",
        lambda name, value, unit="count", tags=None: observations.append((name, value, unit, tags)),
    )

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="[person_1] rendben van"))]
    )

    async def _create(**_kwargs):
        return response

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    audit = _AuditStub()
    svc = ChatService(chat_model=client, pii_depersonalization_service=_PiiOkService(), audit_service=audit)

    async def _fake_context_packet(**_kwargs):
        return {
            "kb_uuid": "kb-1",
            "pii_depersonalization_enabled": True,
            "personal_data_sensitivity": "medium",
            "source_chunks": [{"text": "Péter magas"}],
        }

    svc._build_context_packet = _fake_context_packet  # type: ignore[method-assign]

    payload = asyncio.run(
        svc.chat_with_sources(
            "Péter státusza?",
            user_id=7,
            user_role="owner",
            kb_uuid="kb-1",
        )
    )
    assert "Péter" in str(payload.get("answer") or "")

    success_calls = [
        call for call in audit.calls
        if call.get("action") == _PII_AUDIT_ACTION and call.get("outcome") == "success"
    ]
    assert success_calls
    details = success_calls[-1].get("details") or {}
    assert int(details.get("pii_items_created") or 0) >= 2
    assert "person" in (details.get("entity_types") or [])

    pii_run_metrics = [m for m in metrics_calls if m[0] == "knowledge.pii.depersonalize.runs"]
    assert pii_run_metrics
    assert pii_run_metrics[-1][2] == {"sensitivity": "medium", "outcome": "success"}
    assert any(obs[0] == "knowledge.pii.depersonalize.duration_ms" for obs in observations)
    assert any(obs[0] == "knowledge.pii.depersonalize.tokens_per_request" for obs in observations)


def test_question_suffix_gets_tokenized_from_context_mapping_fallback() -> None:
    captured: dict[str, object] = {}

    async def _create(**kwargs):
        captured["messages"] = kwargs.get("messages") or []
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="[person_1] kék szemű."))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    svc = ChatService(chat_model=client, pii_depersonalization_service=_SuffixBlindPiiService(), audit_service=_AuditStub())

    async def _fake_context_packet(**_kwargs):
        return {
            "kb_uuid": "kb-1",
            "pii_depersonalization_enabled": True,
            "personal_data_sensitivity": "medium",
            "source_chunks": [{"text": "Péter magas és kék szemű."}],
        }

    svc._build_context_packet = _fake_context_packet  # type: ignore[method-assign]

    asyncio.run(
        svc.chat_with_sources(
            "milyen szeme van péternek",
            user_id=7,
            user_role="owner",
            kb_uuid="kb-1",
        )
    )
    messages = captured.get("messages") or []
    merged = "\n".join(str(msg.get("content") or "") for msg in messages if isinstance(msg, dict))
    assert "[person_1]" in merged
    assert "péternek" not in merged.lower()


def _build_real_pii_service() -> PiiDepersonalizationService:
    name_re = re.compile(r"\bKovács Anna\b")
    phone_re = re.compile(r"\+36\s?30\s?123\s?4567")

    def _detector(text: str, _sensitivity: str):
        matches: list[tuple[int, int, str, str]] = []
        for m in name_re.finditer(text):
            matches.append((m.start(), m.end(), "name", m.group(0)))
        for m in phone_re.finditer(text):
            matches.append((m.start(), m.end(), "phone", m.group(0)))
        return sorted(matches, key=lambda item: item[0])

    return PiiDepersonalizationService(_FakeMappingRepo(), detector=_detector)


def _chat_service_with_captured_messages(*, pii_enabled: bool):
    captured: dict[str, object] = {}

    async def _create(**kwargs):
        captured["messages"] = kwargs.get("messages") or []
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="[name_1] ügyfél elérhető a [phone_1] számon.")
                )
            ]
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    svc = ChatService(
        chat_model=client,
        pii_depersonalization_service=_build_real_pii_service(),
        audit_service=_AuditStub(),
    )

    async def _fake_context_packet(**_kwargs):
        return {
            "kb_uuid": "kb-1",
            "pii_depersonalization_enabled": pii_enabled,
            "personal_data_sensitivity": "medium",
            "source_chunks": [{"text": "Kovács Anna kapcsolattartó, telefonszáma +36 30 123 4567."}],
        }

    svc._build_context_packet = _fake_context_packet  # type: ignore[method-assign]
    return svc, captured


@pytest.mark.release_acceptance
def test_chat_encodes_pii_in_question_and_context_when_enabled() -> None:
    svc, captured = _chat_service_with_captured_messages(pii_enabled=True)

    asyncio.run(
        svc.chat_with_sources(
            "Kovács Anna elérhetősége?",
            user_id=7,
            user_role="owner",
            kb_uuid="kb-1",
        )
    )

    messages = captured.get("messages") or []
    merged = "\n".join(str(msg.get("content") or "") for msg in messages if isinstance(msg, dict))
    assert "[name_1]" in merged
    assert "Kovács Anna" not in merged


@pytest.mark.release_acceptance
def test_chat_encodes_pii_in_conversation_and_retrieval_history_when_enabled() -> None:
    svc, captured = _chat_service_with_captured_messages(pii_enabled=True)

    asyncio.run(
        svc.chat_with_sources(
            "Kovács Anna elérhetősége?",
            user_id=7,
            user_role="owner",
            kb_uuid="kb-1",
            conversation_history=[
                {"role": "user", "content": "Kovács Anna melyik telefonszámon érhető el?"},
                {"role": "assistant", "content": "A szám: +36 30 123 4567."},
            ],
            retrieval_history=[
                "Korábbi találat: Kovács Anna telefonszáma +36 30 123 4567.",
            ],
        )
    )

    messages = captured.get("messages") or []
    merged = "\n".join(str(msg.get("content") or "") for msg in messages if isinstance(msg, dict))
    assert "[name_1]" in merged
    assert "[phone_1]" in merged
    assert "Kovács Anna" not in merged
    assert "+36 30 123 4567" not in merged


@pytest.mark.release_acceptance
def test_chat_passes_plaintext_when_flag_disabled() -> None:
    svc, captured = _chat_service_with_captured_messages(pii_enabled=False)

    asyncio.run(
        svc.chat_with_sources(
            "Kovács Anna elérhetősége?",
            user_id=7,
            user_role="owner",
            kb_uuid="kb-1",
        )
    )

    messages = captured.get("messages") or []
    merged = "\n".join(str(msg.get("content") or "") for msg in messages if isinstance(msg, dict))
    assert "Kovács Anna" in merged


@pytest.mark.release_acceptance
def test_response_rehydrates_tokens_to_original_values() -> None:
    svc, _captured = _chat_service_with_captured_messages(pii_enabled=True)

    payload = asyncio.run(
        svc.chat_with_sources(
            "Kovács Anna elérhetősége?",
            user_id=7,
            user_role="owner",
            kb_uuid="kb-1",
        )
    )
    answer = str(payload.get("answer") or "")
    assert "Kovács Anna ügyfél elérhető a +36 30 123 4567 számon." in answer


@pytest.mark.release_acceptance
def test_encode_failure_does_not_leak_pii_to_llm() -> None:
    call_count = {"create": 0}

    async def _create(**_kwargs):
        call_count["create"] += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    svc = ChatService(chat_model=client, pii_depersonalization_service=_BrokenPiiService(), audit_service=_AuditStub())

    async def _fake_context_packet(**_kwargs):
        return {
            "kb_uuid": "kb-1",
            "pii_depersonalization_enabled": True,
            "personal_data_sensitivity": "medium",
            "source_chunks": [{"text": "Kovács Anna"}],
        }

    svc._build_context_packet = _fake_context_packet  # type: ignore[method-assign]

    with pytest.raises(PiiDepersonalizationUnavailableError):
        asyncio.run(
            svc.chat_with_sources(
                "Kovács Anna adatai?",
                user_id=7,
                user_role="owner",
                kb_uuid="kb-1",
            )
        )
    assert call_count["create"] == 0


@pytest.mark.release_acceptance
def test_audit_log_records_pii_depersonalization_event() -> None:
    svc, _captured = _chat_service_with_captured_messages(pii_enabled=True)
    audit = svc.audit_service

    asyncio.run(
        svc.chat_with_sources(
            "Kovács Anna elérhetősége?",
            user_id=7,
            user_role="owner",
            kb_uuid="kb-1",
        )
    )

    assert isinstance(audit, _AuditStub)
    assert any(
        call.get("action") == _PII_AUDIT_ACTION and call.get("outcome") == "success"
        for call in audit.calls
    )


@pytest.mark.release_acceptance
def test_channel_chat_blocks_broad_enumeration_before_llm_call() -> None:
    call_count = {"create": 0}

    async def _create(**_kwargs):
        call_count["create"] += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    svc = ChatService(chat_model=client, pii_depersonalization_service=None, audit_service=_AuditStub())

    with pytest.raises(ChatPolicyViolationError) as exc:
        asyncio.run(
            svc.chat_with_sources(
                "Listázd az összes tudást a tudástárból.",
                user_id=None,
                user_role="channel",
                kb_uuid="kb-1",
            )
        )
    assert "túl általános listázást céloz" in str(exc.value).lower()
    assert call_count["create"] == 0
