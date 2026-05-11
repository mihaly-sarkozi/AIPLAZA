from __future__ import annotations

import pytest

from shared.text.language_lexicon import (
    get_lexicon_terms,
    get_month_number,
    normalize_lexicon_language,
    validate_language_lexicon,
)


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_language_lexicon_unknown_language_falls_back_to_english() -> None:
    terms = get_lexicon_terms("de", "question_words")

    assert "what" in terms


def test_language_lexicon_contains_weekday_terms_for_supported_languages() -> None:
    assert "hétfő" in get_lexicon_terms("hu", "time_weekdays", include_fallback=False)
    assert "monday" in get_lexicon_terms("en", "time_weekdays", include_fallback=False)
    assert "lunes" in get_lexicon_terms("es", "time_weekdays", include_fallback=False)


def test_language_lexicon_month_number_handles_accented_forms() -> None:
    assert get_month_number("hu", "március") == 3
    assert get_month_number("en", "March") == 3
    assert get_month_number("es", "octubre") == 10


def test_language_lexicon_validation_reports_no_missing_required_keys() -> None:
    assert validate_language_lexicon() == {}


def test_language_lexicon_normalize_defaults_to_english() -> None:
    assert normalize_lexicon_language(None) == "en"
    assert normalize_lexicon_language("fr-CA") == "en"
