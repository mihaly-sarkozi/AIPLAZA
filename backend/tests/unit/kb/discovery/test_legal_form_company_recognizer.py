from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.entities.LegalFormCompanyRecognizer import LegalFormCompanyRecognizer
from apps.kb.kb_discovery.enums.EntityType import EntityType

pytestmark = pytest.mark.unit


def _context() -> DiscoveryContext:
    return DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
    )


def _recognize(text: str, language_code: str) -> list[str]:
    recognizer = LegalFormCompanyRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text=text,
            chunk_type="paragraph",
            order_index=0,
            language_code=language_code,
        )
    ]
    return [item.name for item in recognizer.recognize(chunks, _context())]


@pytest.mark.parametrize(
    ("text", "language_code", "expected"),
    [
        (
            "This policy was signed with OpenAI, LLC yesterday.",
            "en",
            "OpenAI, LLC",
        ),
        ("The team met OpenAI LLC.", "en", "OpenAI LLC"),
        (
            "Az ügyfél a Zalka 2000 Kft. szerződését kéri.",
            "hu",
            "Zalka 2000 Kft.",
        ),
        (
            "Contrato con Empresa Ejemplo S.L. firmado.",
            "es",
            "Empresa Ejemplo S.L.",
        ),
        ("ACME Ltd. sent the invoice.", "en", "ACME Ltd."),
        ("A Teszt Zrt. dokumentuma hiányzik.", "hu", "Teszt Zrt."),
        ("A Zalka 2000 Kft. Budapesten működik.", "hu", "Zalka 2000 Kft."),
    ],
)
def test_legal_form_recognizer_extracts_company_only(text, language_code, expected) -> None:
    names = _recognize(text, language_code)
    assert expected in names
    assert all(expected in name and len(name) <= len(expected) + 2 for name in names if expected in name)


@pytest.mark.parametrize(
    ("text", "language_code"),
    [
        ("We use Series A funding data.", "en"),
        ("This is a limited offer.", "en"),
        ("A contract was signed with the client.", "en"),
        ("La empresa firmó el contrato.", "es"),
    ],
)
def test_legal_form_recognizer_avoids_false_positives(text, language_code) -> None:
    names = _recognize(text, language_code)
    assert names == []


def test_legal_form_recognizer_metadata_contains_legal_form() -> None:
    recognizer = LegalFormCompanyRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="OpenAI, LLC policy applies.",
            chunk_type="paragraph",
            order_index=0,
            language_code="en",
        )
    ]
    result = recognizer.recognize(chunks, _context())
    assert len(result) == 1
    metadata = dict(result[0].metadata)
    assert metadata["recognizer"] == "legal_form_company"
    assert metadata["legal_form_source"] == "suffix"
    assert metadata["matched_suffix"]
    assert metadata["company_name_tokens"] == ["OpenAI"]
    assert metadata["legal_form"] in {"LLC", "L.L.C."}


def test_legal_form_gazetteer_splits_suffix_and_full_names() -> None:
    from apps.kb.kb_discovery.gazetteers.LegalFormGazetteer import LegalFormGazetteer

    gazetteer = LegalFormGazetteer()
    suffixes = gazetteer.suffixes_for_language("hu")
    full_names = gazetteer.full_names_for_language("hu")
    assert "Kft." in suffixes
    assert len(suffixes) < len(full_names) + len(suffixes)
    assert "Series" not in suffixes
