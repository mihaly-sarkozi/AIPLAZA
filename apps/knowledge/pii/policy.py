# apps/knowledge/pii/policy.py
"""
Saját szabálymotor: mely entitástípust maszkoljuk, melyiket engedjük.
Nem jogi döntés – csak jelöltek; a policy eldönti: maszkolás / általánosítás / review.
Erősség szerint: weak = kevesebb típus, strong = minden érzékeny típus.
"""
from __future__ import annotations

from typing import List, Set

# weak: csak email, telefonszám
# medium: + IBAN, rendszám, dátum, ügyfélazonosító, szerződésszám, ticket_id, név, cím (legacy regex)
# strong: + szervezet, hely (NER)
WEAK_ENTITIES: Set[str] = {"email", "telefonszám"}
MEDIUM_ENTITIES: Set[str] = WEAK_ENTITIES | {
    "iban",
    "rendszám",
    "dátum",
    "ügyfélazonosító",
    "szerződésszám",
    "ticket_id",
    "név",
    "cím",
}
STRONG_ENTITIES: Set[str] = MEDIUM_ENTITIES | {"szervezet", "hely"}

# Presidio / spaCy / Stanza NER típusok → tárolt entitásnév (napló, placeholder)
NER_ENTITY_TO_TYPE: dict[str, str] = {
    "PERSON": "név",
    "PER": "név",
    "ORG": "szervezet",
    "ORGANIZATION": "szervezet",
    "GPE": "hely",
    "LOC": "hely",
    "LOCATION": "hely",
    "DATE": "dátum",
}


def entities_for_sensitivity(sensitivity: str) -> Set[str]:
    """Az adott erősséghez engedélyezett entitástípusok."""
    s = (sensitivity or "medium").lower()
    if s == "weak":
        return WEAK_ENTITIES
    if s == "strong":
        return STRONG_ENTITIES
    return MEDIUM_ENTITIES


def map_entity_type(presidio_entity: str) -> str:
    """Presidio/spaCy/Stanza entity típus → tárolt típusnév (név, szervezet, hely, dátum, stb.)."""
    key = (presidio_entity or "").strip().upper()
    return NER_ENTITY_TO_TYPE.get(key, presidio_entity)


def filter_by_policy(
    entity_type: str,
    sensitivity: str,
    _context: dict | None = None,
) -> bool:
    """
    Policy döntés: ez az entitás menjen maszkolásra az adott erősségnél?
    context később: céges email maradhat-e, stb.
    """
    allowed = entities_for_sensitivity(sensitivity)
    return entity_type.lower() in allowed


class PiiConfirmationRequiredError(Exception):
    """A tartalom személyes adatokat tartalmaz, megerősítés szükséges (with_confirmation mód)."""

    def __init__(self, detected_types: List[str]) -> None:
        self.detected_types = list(detected_types)
        super().__init__(f"Személyes adatok észlelve: {', '.join(self.detected_types)}")
