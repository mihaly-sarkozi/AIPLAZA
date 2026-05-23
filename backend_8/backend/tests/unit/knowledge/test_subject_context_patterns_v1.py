from __future__ import annotations

import pytest

from apps.knowledge.service.subject_context_patterns_v1 import match_implicit_subject_sentence_pattern_id


@pytest.mark.parametrize(
    "text,pid",
    [
        ("Korábban a belső audit folyamatért felelt.", "hu_korabban_felelt"),
        ("Jelenleg a modul stabilan működik.", "hu_jelenleg_mukodik"),
        ("Most ő felel az ügyért.", "hu_most_felel"),
    ],
)
def test_hu_implicit_sentence_patterns(text: str, pid: str) -> None:
    assert match_implicit_subject_sentence_pattern_id(text, "hu") == pid


@pytest.mark.parametrize(
    "text,pid",
    [
        ("Previously responsible for internal audit.", "en_previously_responsible_for"),
        ("Was previously responsible for compliance.", "en_was_previously_responsible_for"),
        ("Currently manages the London office.", "en_currently_manages"),
    ],
)
def test_en_implicit_sentence_patterns(text: str, pid: str) -> None:
    assert match_implicit_subject_sentence_pattern_id(text, "en") == pid


@pytest.mark.parametrize(
    "text,pid",
    [
        ("Anteriormente fue responsable de auditoría.", "es_anteriormente_fue_responsable_de"),
        ("Actualmente gestiona el proceso.", "es_actualmente_gestiona"),
    ],
)
def test_es_implicit_sentence_patterns(text: str, pid: str) -> None:
    assert match_implicit_subject_sentence_pattern_id(text, "es") == pid


def test_pattern_no_match_wrong_language() -> None:
    assert match_implicit_subject_sentence_pattern_id("Korábban felelt.", "en") is None


def test_pattern_was_preferred_over_previously() -> None:
    t = "Was previously responsible for risk."
    assert match_implicit_subject_sentence_pattern_id(t, "en") == "en_was_previously_responsible_for"
