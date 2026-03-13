# apps/knowledge/pii – Presidio központú PII felismerés és helyettesítés
#
# Algoritmus (mag: Presidio):
#   1) Regex a biztos adatokra: email, telefonszám, IBAN, rendszám, ügyfélazonosító,
#      szerződésszám, ticket ID, dátum (Presidio PatternRecognizer).
#   2) NER (spaCy / Stanza): angol + spanyol = spaCy, magyar = Stanza → név, szervezet, hely.
#   3) Saját policy engine: weak/medium/strong, később céges email, review szabályok.
#   4) Fallback: nehéz esetekre opcionálisan GLiNER – később.
# Modellek: python scripts/download_pii_models.py (spaCy en_core_web_sm, es_core_news_sm; Stanza hu).
# Ha az NLP modellek nincsenek, legacy regex réteg fut.
from __future__ import annotations

from apps.knowledge.pii.pipeline import (
    filter_pii,
    apply_pii_replacements,
    PiiMatch,
)
from apps.knowledge.pii.policy import PiiConfirmationRequiredError

__all__ = [
    "filter_pii",
    "apply_pii_replacements",
    "PiiMatch",
    "PiiConfirmationRequiredError",
]
