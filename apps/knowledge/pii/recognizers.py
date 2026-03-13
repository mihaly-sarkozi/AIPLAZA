# apps/knowledge/pii/recognizers.py
"""
Egyéni Presidio PatternRecognizer-ek a biztos mintákra (regex).
Réteg 1: email, telefonszám, IBAN, rendszám, ügyfélazonosító, szerződésszám, ticket ID, dátum.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

# Entitás típusok (Presidio és belső név egyezik a tárolt típusnévvel)
ENTITY_EMAIL = "email"
ENTITY_PHONE = "telefonszám"
ENTITY_IBAN = "iban"
ENTITY_LICENSE_PLATE = "rendszám"
ENTITY_CUSTOMER_ID = "ügyfélazonosító"
ENTITY_CONTRACT_NUMBER = "szerződésszám"
ENTITY_TICKET_ID = "ticket_id"
ENTITY_DATE = "dátum"

def _pattern(name: str, regex: str, score: float = 0.8) -> Pattern:
    return Pattern(name=name, regex=regex, score=score)


def get_custom_recognizers(lang: str = "en"):
    """Egyéni regex recognizerek listája a megadott nyelvhez (en, es, hu)."""
    return [
        _email_recognizer(lang),
        _phone_recognizer(lang),
        _iban_recognizer(lang),
        _license_plate_recognizer(lang),
        _customer_id_recognizer(lang),
        _contract_number_recognizer(lang),
        _ticket_id_recognizer(lang),
        _date_recognizer(lang),
    ]


def _email_recognizer(lang: str) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=ENTITY_EMAIL,
        patterns=[
            _pattern("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 0.95),
        ],
        supported_language=lang,
    )


def _phone_recognizer(lang: str) -> PatternRecognizer:
    # HU: +36/06, külföldi prefixek; általános számformák
    return PatternRecognizer(
        supported_entity=ENTITY_PHONE,
        patterns=[
            _pattern("phone_hu", r"\b(?:\+36|06)[\s\-/]?\d{1,2}[\s\-/]?\d{3}[\s\-/]?\d{4}\b", 0.9),
            _pattern("phone_short", r"\b\d{2}[\s\-/]\d{3}[\s\-/]\d{4}\b", 0.75),
            _pattern("phone_intl", r"\+\d{1,3}[\s\-]?(?:\d[\s\-]?){8,14}\d\b", 0.8),
        ],
        supported_language=lang,
    )


def _iban_recognizer(lang: str) -> PatternRecognizer:
    # IBAN: 2 betű ország + 2 szám + 4 betű/szám + max 30 karakter
    return PatternRecognizer(
        supported_entity=ENTITY_IBAN,
        patterns=[
            _pattern("iban", r"\b[A-Z]{2}\d{2}\s?(?:[A-Z0-9]\s?){4}(?:[A-Z0-9]\s?){4,28}\b", 0.9),
        ],
        supported_language=lang,
    )


def _license_plate_recognizer(lang: str) -> PatternRecognizer:
    # HU régi: 3 betű-3 szám (ABC-123), új: 3 betű-3 szám vagy 2 betű-2 szám-2 betű-2 szám
    return PatternRecognizer(
        supported_entity=ENTITY_LICENSE_PLATE,
        patterns=[
            _pattern("plate_hu", r"\b[A-Z]{3}[- ]?\d{3}\b", 0.85),
            _pattern("plate_hu_new", r"\b[A-Z]{2}[- ]?\d{2}[- ]?[A-Z]{2}[- ]?\d{2}\b", 0.85),
        ],
        supported_language=lang,
    )


def _customer_id_recognizer(lang: str) -> PatternRecognizer:
    # Ügyfélazonosító: gyakori minták (pl. UGY-12345, UGYFEL-123, #12345)
    return PatternRecognizer(
        supported_entity=ENTITY_CUSTOMER_ID,
        patterns=[
            _pattern("customer_ugy", r"\b(?:UGY|UGYFEL|CLIENT)[\- ]?\d{4,10}\b", 0.8),
            _pattern("customer_hash", r"\#\d{4,12}\b", 0.6),
        ],
        supported_language=lang,
    )


def _contract_number_recognizer(lang: str) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=ENTITY_CONTRACT_NUMBER,
        patterns=[
            _pattern("contract_sz", r"\b(?:SZ|Szerz\.?|Szerződés)[\- ]?\d{4,12}\b", 0.8),
            _pattern("contract_num", r"\b(?:CONTRACT|CONT)[\- ]?\d{4,12}\b", 0.75),
        ],
        supported_language=lang,
    )


def _ticket_id_recognizer(lang: str) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=ENTITY_TICKET_ID,
        patterns=[
            _pattern("ticket", r"\b(?:TKT|TICKET|JIRA)[\- ]?\d{4,10}\b", 0.8),
            _pattern("ticket_hash", r"\b(?:#[A-Z]+-?\d+)\b", 0.65),
        ],
        supported_language=lang,
    )


def _date_recognizer(lang: str) -> PatternRecognizer:
    # Dátum: év.hónap.nap, nap.hónap.év, szóközös magyar (1992. 03. 14.), születési dátum kontextus
    return PatternRecognizer(
        supported_entity=ENTITY_DATE,
        patterns=[
            _pattern("date_iso", r"\b(?:19|20)\d{2}[.\-/](?:0[1-9]|1[0-2])[.\-/](?:0[1-9]|[12]\d|3[01])\b", 0.85),
            _pattern("date_eu", r"\b(?:0[1-9]|[12]\d|3[01])[.\-/](?:0[1-9]|1[0-2])[.\-/](?:19|20)\d{2}\b", 0.85),
            _pattern("date_hu_spaces", r"\b(?:19|20)\d{2}\.\s*(?:0[1-9]|1[0-2])\.\s*(?:0[1-9]|[12]\d|3[01])\.?", 0.85),
            _pattern("date_hu_spaces_rev", r"\b(?:0[1-9]|[12]\d|3[01])\.\s*(?:0[1-9]|1[0-2])\.\s*(?:19|20)\d{2}\.?", 0.85),
            _pattern("dob_context", r"(?i)(?:született|szül\.?|date of birth|dob)\s*:\s*(?:19|20)\d{2}[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:0[1-9]|[12]\d|3[01])\b", 0.9),
            _pattern("dob_context_eu", r"(?i)(?:született|szül\.?|date of birth|dob)\s*:\s*(?:0[1-9]|[12]\d|3[01])[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:19|20)\d{2}\b", 0.9),
        ],
        supported_language=lang,
    )
