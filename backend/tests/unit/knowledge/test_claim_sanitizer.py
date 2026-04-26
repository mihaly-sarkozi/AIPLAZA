from __future__ import annotations

import pytest

from apps.knowledge.service.claim_sanitizer import sanitize_subject, strip_leading_source_phrase, subject_sanitizer_tags


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.mark.parametrize(
    ("language", "raw", "expected"),
    [
        ("hu", "A dokumentum szerint Nagy Eszter", "Nagy Eszter"),
        ("hu", "Dokumentum szerint Nagy Eszter", "Nagy Eszter"),
        ("hu", "A forrás szerint Nagy Eszter", "Nagy Eszter"),
        ("hu", "A szöveg szerint Nagy Eszter", "Nagy Eszter"),
        ("hu", "A riport szerint Nagy Eszter", "Nagy Eszter"),
        ("en", "According to the document Sarah Miller", "Sarah Miller"),
        ("en", "According to the source Sarah Miller", "Sarah Miller"),
        ("en", "The document says Sarah Miller", "Sarah Miller"),
        ("en", "The report states Sarah Miller", "Sarah Miller"),
        ("es", "Según el documento Carlos García", "Carlos García"),
        ("es", "Según la fuente Carlos García", "Carlos García"),
        ("es", "El documento indica Carlos García", "Carlos García"),
    ],
)
def test_strip_leading_source_phrase_removes_report_source_markers(
    language: str, raw: str, expected: str
) -> None:
    assert strip_leading_source_phrase(raw, language=language) == expected
    assert sanitize_subject(raw, language=language) == expected


def test_source_phrase_sanitizer_keeps_plain_subject() -> None:
    assert sanitize_subject("Nagy Eszter", language="hu") == "Nagy Eszter"


def test_source_phrase_sanitizer_normalizes_hu_admin_user_dative_subject() -> None:
    assert (
        sanitize_subject("A dokumentum szerint az admin felhasználónak", language="hu")
        == "admin felhasználó"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("felhasználónak", "felhasználó"),
        ("admin felhasználónak", "admin felhasználó"),
        ("admin felhasználón", "admin felhasználó"),
        ("login rendszerben", "login rendszer"),
        ("admin felhasználónál", "admin felhasználó"),
        ("admin felhasználónél", "admin felhasználó"),
    ],
)
def test_hu_subject_suffix_normalizer_v1(raw: str, expected: str) -> None:
    assert sanitize_subject(raw, language="hu") == expected


def test_hu_subject_suffix_normalizer_does_not_strip_plain_admin() -> None:
    assert sanitize_subject("admin", language="hu") == "admin"


def test_hu_subject_sanitizer_removes_temporal_tail_before_suffix_normalization() -> None:
    assert sanitize_subject("A dokumentum 2026 márciusában", language="hu") == "dokumentum"


def test_subject_sanitizer_tags_report_source_and_suffix() -> None:
    raw = "A dokumentum szerint az admin felhasználónak"
    cleaned = sanitize_subject(raw, language="hu")

    assert cleaned == "admin felhasználó"
    assert subject_sanitizer_tags(raw, cleaned, language="hu") == ["source_phrase", "suffix_normalization"]
