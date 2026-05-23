from __future__ import annotations

import pytest

from apps.chat.service.pii_depersonalization import PiiDepersonalizationService

pytestmark = pytest.mark.unit


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


def test_encode_and_rehydrate_roundtrip_is_reversible():
    svc = PiiDepersonalizationService(
        _FakeMappingRepo(),
        detector=lambda _text, _sensitivity: [
            (0, 10, "person", "John Smith"),
            (18, 34, "email", "john@example.com"),
        ],
    )

    encoded = svc.encode_text(
        corpus_uuid="kb-1",
        text="John Smith email: john@example.com",
        enabled=True,
        sensitivity="medium",
    )
    assert encoded.text == "[person_1] email: [email_1]"

    restored = svc.rehydrate_text(corpus_uuid="kb-1", text=encoded.text, enabled=True)
    assert restored.text == "John Smith email: john@example.com"
    assert len(restored.restored_spans) == 2
    assert restored.restored_spans[0]["token"] == "[person_1]"


def test_encode_disabled_is_noop():
    svc = PiiDepersonalizationService(_FakeMappingRepo(), detector=lambda *_args, **_kwargs: [])
    encoded = svc.encode_text(corpus_uuid="kb-1", text="Nincs csere", enabled=False, sensitivity="medium")
    assert encoded.text == "Nincs csere"
    assert encoded.mappings == []


def test_rehydrate_ignores_user_injected_tokens_outside_allowlist():
    svc = PiiDepersonalizationService(
        _FakeMappingRepo(),
        detector=lambda _text, _sensitivity: [(0, 10, "person", "John Smith")],
    )
    encoded = svc.encode_text(
        corpus_uuid="kb-1",
        text="John Smith",
        enabled=True,
        sensitivity="medium",
    )
    allowed = [mapping["token"] for mapping in encoded.mappings]
    restored = svc.rehydrate_text(
        corpus_uuid="kb-1",
        text="[person_1] és [email_5]",
        enabled=True,
        allowed_tokens=allowed,
    )
    assert restored.text == "John Smith és [email_5]"


@pytest.mark.release_acceptance
def test_same_value_gets_same_token_within_corpus():
    svc = PiiDepersonalizationService(
        _FakeMappingRepo(),
        detector=lambda _text, _sensitivity: [
            (0, 11, "name", "Kovács Anna"),
            (15, 26, "name", "Kovács Anna"),
        ],
    )
    encoded = svc.encode_text(
        corpus_uuid="kb-1",
        text="Kovács Anna és Kovács Anna",
        enabled=True,
        sensitivity="medium",
    )
    assert encoded.text.count("[name_1]") == 2


@pytest.mark.release_acceptance
def test_different_values_get_different_tokens():
    svc = PiiDepersonalizationService(
        _FakeMappingRepo(),
        detector=lambda _text, _sensitivity: [
            (0, 11, "name", "Kovács Anna"),
            (15, 28, "name", "Kovács Andrea"),
        ],
    )
    encoded = svc.encode_text(
        corpus_uuid="kb-1",
        text="Kovács Anna és Kovács Andrea",
        enabled=True,
        sensitivity="medium",
    )
    assert "[name_1]" in encoded.text
    assert "[name_2]" in encoded.text
