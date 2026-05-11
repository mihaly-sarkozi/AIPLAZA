from __future__ import annotations

import pytest

from apps.knowledge.service.claim_typing import CLAIM_TYPE_CONFIGS, guess_claim_type


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.mark.parametrize(
    ("predicate", "language", "expected"),
    [
        ("készít", "hu", "stable_descriptor"),
        ("működik", "hu", "state"),
        ("felelt", "hu", "relation"),
        ("vezetője", "hu", "relation"),
        ("megszűnt", "hu", "event"),
        ("megmarad", "hu", "state"),
        ("remain", "en", "stable_descriptor"),
        ("remains", "en", "state"),
        ("conflict with", "en", "relation"),
        ("permanecen", "es", "state"),
        ("está activa", "es", "state"),
        ("fue desactivado", "es", "event"),
    ],
)
def test_guess_claim_type_matches_expected_mapping(predicate: str, language: str, expected: str) -> None:
    claim_type = guess_claim_type(predicate, None, predicate, language=language)
    assert claim_type == expected


def test_context_header_claim_type_is_explicitly_configured() -> None:
    config = CLAIM_TYPE_CONFIGS["context_header"]
    assert config.claim_group == "other"
    assert config.conflict_behavior == "weak"
    assert config.time_sensitive is False
