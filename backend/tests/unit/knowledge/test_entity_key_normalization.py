from __future__ import annotations

import pytest

from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key, normalize_entity_key

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.mark.parametrize(
    ("text", "language", "strip_accents", "expected"),
    [
        ("Login rendszer", "hu", False, "login rendszer"),
        ("A login rendszer", "hu", False, "login rendszer"),
        ("The London office", "en", False, "london office"),
        ("La oficina de Madrid", "es", False, "oficina de madrid"),
        ("Zalka 2000", None, False, "zalka 2000"),
        ("Meeting in 2024", "en", False, "meeting in"),
        ("Kiss Márton", "hu", False, "kiss márton"),
        ("Kiss Márton", "hu", True, "kiss marton"),
    ],
)
def test_normalize_entity_key_examples(
    text: str,
    language: str | None,
    strip_accents: bool,
    expected: str,
) -> None:
    assert normalize_entity_key(text, language, strip_accents=strip_accents) == expected


def test_removes_time_words() -> None:
    assert normalize_entity_key("Currently the London office", "en") == "london office"
    assert normalize_entity_key("Jelenleg a login rendszer", "hu") == "login rendszer"


def test_canonicalize_entity_key_maps_admin_user_cross_language() -> None:
    assert canonicalize_entity_key("admin user", "en") == "admin user"
    assert canonicalize_entity_key("admin felhasználó", "hu") == "admin user"
    assert canonicalize_entity_key("usuario administrador", "es") == "admin user"


def test_canonicalize_entity_key_maps_legacy_helpdesk_import() -> None:
    assert canonicalize_entity_key("legacy helpdesk import", "en") == "legacy helpdesk import"
    assert canonicalize_entity_key("régi Helpdesk import", "hu") == "legacy helpdesk import"
