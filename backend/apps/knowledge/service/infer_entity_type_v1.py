"""Claim subject + mention lista → lokális entitástípus (v1, determinisztikus, DB nélkül).

A ``local_resolver_v1`` pipeline része. **Tiltások** (globális profil, Qdrant, cross-document / cross-language
merge, LLM, fuzzy matching, similarity/tension engine): lásd a ``local_resolver_v1`` modul docstringjét.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from apps.knowledge.domain.claim import ClaimType
from apps.knowledge.domain.local_entity_cluster import LocalEntityType
from apps.knowledge.domain.mention import MentionType
from apps.knowledge.service.local_entity_text_norm import mention_normalized_text, norm_for_overlap

ENTITY_TYPE_SOURCE_MENTION_MATCH = "mention_match"
ENTITY_TYPE_SOURCE_KEYWORD = "normalizer"
ENTITY_TYPE_SOURCE_FALLBACK = "fallback"

__all__ = [
    "ENTITY_TYPE_SOURCE_FALLBACK",
    "ENTITY_TYPE_SOURCE_KEYWORD",
    "ENTITY_TYPE_SOURCE_MENTION_MATCH",
    "infer_entity_type",
    "infer_entity_type_and_source",
]


def _mention_type_to_local_entity(mention_type: str) -> str:
    mapping: dict[str, str] = {
        MentionType.PERSON.value: LocalEntityType.PERSON.value,
        MentionType.COMPANY.value: LocalEntityType.COMPANY.value,
        MentionType.SOFTWARE.value: LocalEntityType.SOFTWARE.value,
        MentionType.MODULE.value: LocalEntityType.MODULE.value,
        MentionType.FEATURE.value: LocalEntityType.FEATURE.value,
        MentionType.POLICY.value: LocalEntityType.POLICY.value,
        MentionType.PROCESS.value: LocalEntityType.PROCESS.value,
        MentionType.LOCATION.value: LocalEntityType.LOCATION.value,
        MentionType.OBJECT.value: LocalEntityType.OBJECT.value,
        MentionType.EVENT.value: LocalEntityType.UNKNOWN.value,
        MentionType.UNKNOWN.value: LocalEntityType.UNKNOWN.value,
    }
    return mapping.get(mention_type, LocalEntityType.UNKNOWN.value)


def _fold_for_keywords(s: str) -> str:
    raw = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")


def _keyword_in_folded(folded: str, kw: str) -> bool:
    if len(kw) <= 3:
        return bool(re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", folded))
    return kw in folded


_KEYWORD_ENTITY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Spec: "import" → module mert a regression korpuszban "legacy helpdesk import" /
    # "régi Helpdesk import" tipikus integráció-modul; megelőzi a generikus "module"-t.
    (LocalEntityType.MODULE.value, ("import", "modul", "module", "modulo")),
    (LocalEntityType.PROCESS.value, ("workflow", "process", "folyamat", "flujo de trabajo", "proceso")),
    (LocalEntityType.SOFTWARE.value, ("helpdesk", "software", "szoftver")),
    (LocalEntityType.SYSTEM.value, ("rendszer", "system", "sistema")),
    (LocalEntityType.LOCATION.value, ("office", "iroda", "oficina")),
    (LocalEntityType.USER.value, ("user", "felhasznalo", "usuario")),
    (LocalEntityType.ACCOUNT.value, ("account", "cuenta")),
    (LocalEntityType.CHECKLIST.value, ("checklist", "ellenorzolista", "ellenőrzőlista", "lista de verificacion", "lista de verificación")),
    (LocalEntityType.POLICY.value, ("policy", "szabalyzat", "politica")),
    (LocalEntityType.DOCUMENT.value, ("document", "dokumentum", "documento")),
    # Spec: "ticket"/"tickets" lokális objektum (nem felhasználó / nem rendszer);
    # így a "Historical tickets" entity is normalizált típust kap.
    (LocalEntityType.OBJECT.value, ("ticket", "tickets", "claim")),
)


_BLOCKLIST_TWO_WORD_PERSON: frozenset[str] = frozenset(
    {
        "office",
        "iroda",
        "oficina",
        "system",
        "rendszer",
        "sistema",
        "module",
        "modul",
        "modulo",
        "user",
        "usuario",
        "account",
        "cuenta",
        "policy",
        "document",
        "documento",
        "dokumentum",
        "claim",
        "software",
        "szoftver",
        "manager",
        "director",
        "lead",
        "team",
        "department",
        "division",
        "head",
        "corp",
        "corporation",
        "ltd",
        "llc",
        "inc",
        "gmbh",
        "plc",
    }
)


def _is_two_word_capitalized_person(subject: str) -> bool:
    s = (subject or "").strip()
    parts = s.split()
    if len(parts) != 2:
        return False
    a_raw, b_raw = parts[0].strip(".,;:!?"), parts[1].strip(".,;:!?")
    if not a_raw or not b_raw:
        return False

    def _is_name_token(w: str) -> bool:
        if not w[0].isupper():
            return False
        for ch in w[1:]:
            if ch in "'-":
                continue
            cat = unicodedata.category(ch)
            if cat not in ("Ll", "Lu", "Lt", "Lm", "Lo", "Mc", "Mn"):
                return False
        return True

    if not _is_name_token(a_raw) or not _is_name_token(b_raw):
        return False
    a_fold = _fold_for_keywords(a_raw)
    b_fold = _fold_for_keywords(b_raw)
    if a_fold in _BLOCKLIST_TWO_WORD_PERSON or b_fold in _BLOCKLIST_TWO_WORD_PERSON:
        return False
    return True


def _is_brand_plus_number_company(subject: str) -> bool:
    s = (subject or "").strip()
    parts = s.split()
    if len(parts) != 2:
        return False
    name, num = parts[0].strip(".,;:!?"), parts[1].strip(".,;:!?")
    if not name or not num:
        return False
    if not re.fullmatch(r"\d+", num):
        return False
    if not name[0].isupper():
        return False
    return all(ch.isalpha() or ch in "'-" for ch in name)


def _pick_mention_overlapping_subject(claim: Any, mentions: list[Any]) -> Any | None:
    """Csak akkor ad mentiont, ha a claim ``subject_mention_id``-ja egyezik a mention ``id``-jával."""
    linked = str(getattr(claim, "subject_mention_id", "") or "")
    if not linked:
        return None
    chosen: Any | None = None
    for m in mentions:
        if str(getattr(m, "id", "") or "") != linked:
            continue
        chosen = m
        break
    if chosen is None:
        return None
    s_norm = norm_for_overlap(str(getattr(claim, "subject_text", "") or ""))
    if not s_norm:
        return None
    m_norm = norm_for_overlap(mention_normalized_text(chosen))
    if not m_norm:
        return None
    if len(m_norm) < 2 and m_norm != s_norm:
        return None
    if m_norm != s_norm and m_norm not in s_norm:
        return None
    return chosen


def infer_entity_type_and_source(claim: Any, mentions: list[Any]) -> tuple[str, str]:
    """Visszaadja az entitástípust és a forrást: ``mention_match`` | ``keyword`` | ``fallback``.

    ``mention_match`` csak akkor, ha a claim ``subject_mention_id`` megegyezik egy mention ``id``-jával
    és a mention szövege illeszkedik a subjecthez. Ha a mention típusa ``unknown`` (ide tartozik a
    ``MentionType.EVENT`` is, lásd ``_mention_type_to_local_entity``), akkor inkább a kulcsszavas
    fallback-et próbáljuk — különben minden ismeretlen mention beszennyezné az entity típust.
    """
    subject = str(getattr(claim, "subject_text", "") or "").strip()

    overlap = _pick_mention_overlapping_subject(claim, mentions)
    if overlap is not None:
        mtype = str(getattr(overlap, "mention_type", MentionType.UNKNOWN.value))
        mapped = _mention_type_to_local_entity(mtype)
        if mapped != LocalEntityType.UNKNOWN.value:
            return mapped, ENTITY_TYPE_SOURCE_MENTION_MATCH

    folded = _fold_for_keywords(subject)
    for entity, keywords in _KEYWORD_ENTITY_RULES:
        if any(_keyword_in_folded(folded, kw) for kw in keywords):
            return entity, ENTITY_TYPE_SOURCE_KEYWORD

    if _is_two_word_capitalized_person(subject):
        return LocalEntityType.PERSON.value, ENTITY_TYPE_SOURCE_KEYWORD

    if _is_brand_plus_number_company(subject):
        return LocalEntityType.COMPANY.value, ENTITY_TYPE_SOURCE_KEYWORD

    ctype = str(getattr(claim, "claim_type", "") or "")
    if ctype == ClaimType.RULE_PROCEDURE.value:
        return LocalEntityType.POLICY.value, ENTITY_TYPE_SOURCE_KEYWORD

    return LocalEntityType.UNKNOWN.value, ENTITY_TYPE_SOURCE_FALLBACK


def infer_entity_type(claim: Any, mentions: list[Any]) -> str:
    """Entitástípus következtetése mention-overlap, kulcsszavak és minták alapján."""
    return infer_entity_type_and_source(claim, mentions)[0]
