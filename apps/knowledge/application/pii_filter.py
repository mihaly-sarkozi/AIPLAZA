# apps/knowledge/application/pii_filter.py
"""
Személyes adatok kezelése: Presidio központú pipeline (regex + később NER + policy).
Rétegek: 1) regex a biztos adatokra, 2) NER (spaCy/Stanza) puha entitásokra,
3) saját policy engine, 4) opcionális fallback (pl. GLiNER).
A program előszűr, de nem minden személyes adat felismerhető.
"""
from __future__ import annotations

from apps.knowledge.pii import (
    filter_pii,
    apply_pii_replacements,
    PiiMatch,
    PiiConfirmationRequiredError,
)

__all__ = [
    "filter_pii",
    "apply_pii_replacements",
    "PiiMatch",
    "PiiConfirmationRequiredError",
]
