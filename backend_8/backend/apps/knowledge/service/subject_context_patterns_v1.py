"""Implicit subject / carry-barát mondatminták (v1, regex, nyelvenként).

Bővíthető lista; jelenleg trace / diagnosztika és a resolver meta mezője számára.
"""
from __future__ import annotations

import re
from typing import Pattern

_VERSION = "subject_context_patterns_v1"

# (regex, stabil pattern_id) — sorrend: első találat nyer.
_PATTERN_ROWS: dict[str, tuple[tuple[Pattern[str], str], ...]] = {
    "hu": (
        (re.compile(r"^korábban\b.*\bfelelt\b", re.IGNORECASE | re.DOTALL), "hu_korabban_felelt"),
        (re.compile(r"^előtte\b.*\bfelelt\b", re.IGNORECASE | re.DOTALL), "hu_elotte_felelt"),
        (re.compile(r"^elotte\b.*\bfelelt\b", re.IGNORECASE | re.DOTALL), "hu_elotte_felelt"),
        (re.compile(r"^később\b.*\bfelelt\b", re.IGNORECASE | re.DOTALL), "hu_kesobb_felelt"),
        (re.compile(r"^kesobb\b.*\bfelelt\b", re.IGNORECASE | re.DOTALL), "hu_kesobb_felelt"),
        (re.compile(r"^akkoriban\b.*\bfelelt\b", re.IGNORECASE | re.DOTALL), "hu_akkoriban_felelt"),
        (re.compile(r"^jelenleg\b.*\bműködik\b", re.IGNORECASE | re.DOTALL), "hu_jelenleg_mukodik"),
        (re.compile(r"^jelenleg\s+is\b.*\bműködik\b", re.IGNORECASE | re.DOTALL), "hu_jelenleg_is_mukodik"),
        (re.compile(r"^most\b.*\bfelel\b", re.IGNORECASE | re.DOTALL), "hu_most_felel"),
    ),
    "en": (
        (re.compile(r"^she\s+works\s+in\b", re.IGNORECASE | re.DOTALL), "en_she_works_in"),
        (re.compile(r"^he\s+works\s+in\b", re.IGNORECASE | re.DOTALL), "en_he_works_in"),
        (re.compile(r"^was\s+previously\s+responsible\s+for\b", re.IGNORECASE | re.DOTALL), "en_was_previously_responsible_for"),
        (re.compile(r"^previously\s+responsible\s+for\b", re.IGNORECASE | re.DOTALL), "en_previously_responsible_for"),
        (re.compile(r"^earlier\s+responsible\s+for\b", re.IGNORECASE | re.DOTALL), "en_earlier_responsible_for"),
        (re.compile(r"^later\s+responsible\s+for\b", re.IGNORECASE | re.DOTALL), "en_later_responsible_for"),
        (re.compile(r"^at\s+that\s+time\s+responsible\s+for\b", re.IGNORECASE | re.DOTALL), "en_at_that_time_responsible_for"),
        (re.compile(r"^it\s+was\s+active\b", re.IGNORECASE | re.DOTALL), "en_it_was_active"),
        (re.compile(r"^it\s+was\s+inactive\b", re.IGNORECASE | re.DOTALL), "en_it_was_inactive"),
        (re.compile(r"^currently\s+manages\b", re.IGNORECASE | re.DOTALL), "en_currently_manages"),
    ),
    "es": (
        (re.compile(r"^anteriormente\s+fue\s+responsable\s+(?:de|del)\b", re.IGNORECASE | re.DOTALL), "es_anteriormente_fue_responsable_de"),
        (re.compile(r"^antes\s+fue\s+responsable\s+(?:de|del)\b", re.IGNORECASE | re.DOTALL), "es_antes_fue_responsable_de"),
        (re.compile(r"^luego\s+fue\s+responsable\s+(?:de|del)\b", re.IGNORECASE | re.DOTALL), "es_luego_fue_responsable_de"),
        (re.compile(r"^en\s+ese\s+momento\s+fue\s+responsable\s+(?:de|del)\b", re.IGNORECASE | re.DOTALL), "es_en_ese_momento_fue_responsable_de"),
        (re.compile(r"^fue\s+actualizad[ao]\b", re.IGNORECASE | re.DOTALL), "es_fue_actualizado"),
        (re.compile(r"^actualizad[ao]\b", re.IGNORECASE | re.DOTALL), "es_actualizado"),
        (re.compile(r"^estaba\s+inactiv[ao]\b", re.IGNORECASE | re.DOTALL), "es_estaba_inactivo"),
        (re.compile(r"^estaba\s+activ[ao]\b", re.IGNORECASE | re.DOTALL), "es_estaba_activo"),
        (re.compile(r"^actualmente\s+gestiona\b", re.IGNORECASE | re.DOTALL), "es_actualmente_gestiona"),
    ),
}


def match_implicit_subject_sentence_pattern_id(text: str, language: str) -> str | None:
    """Első illeszkedő minta azonosítója, vagy ``None``."""
    raw = (text or "").strip()
    if not raw:
        return None
    lang = (language or "en").strip().lower()
    if lang not in _PATTERN_ROWS:
        return None
    for rx, pid in _PATTERN_ROWS[lang]:
        if rx.match(raw):
            return pid
    return None


IMPLICIT_SUBJECT_PATTERN_VERSION = _VERSION

__all__ = [
    "IMPLICIT_SUBJECT_PATTERN_VERSION",
    "match_implicit_subject_sentence_pattern_id",
]
