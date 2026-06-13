from __future__ import annotations

from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage
from apps.kb.kb_discovery.languages.keywords_en import KEYWORD_HINTS_EN
from apps.kb.kb_discovery.languages.keywords_es import KEYWORD_HINTS_ES
from apps.kb.kb_discovery.languages.keywords_hu import KEYWORD_HINTS_HU
from apps.kb.kb_discovery.languages.stopwords_en import STOPWORDS_EN
from apps.kb.kb_discovery.languages.stopwords_es import STOPWORDS_ES
from apps.kb.kb_discovery.languages.stopwords_hu import STOPWORDS_HU
from apps.kb.kb_discovery.languages.topics_en import TOPIC_RULES_EN
from apps.kb.kb_discovery.languages.topics_es import TOPIC_RULES_ES
from apps.kb.kb_discovery.languages.topics_hu import TOPIC_RULES_HU

# Detektálási markerek: stopword alap + domain-specifikus gyakori szavak.
# A stopword listák bővítése automatikusan javítja a detektálást is.
_HU_MARKER_EXTRA = frozenset(
    {
        "ügyfél",
        "számlázás",
        "budapesten",
        "történik",
        "július",
        "irodában",
        "kft",
        "használ",
        "használja",
        "használják",
    }
)
_EN_MARKER_EXTRA = frozenset(
    {
        "customer",
        "onboarding",
        "london",
        "office",
        "invoice",
    }
)
_ES_MARKER_EXTRA = frozenset(
    {
        "factura",
        "madrid",
        "cliente",
        "oficina",
        "crea",
    }
)

LANGUAGE_MARKERS: dict[SupportedLanguage, frozenset[str]] = {
    SupportedLanguage.HU: STOPWORDS_HU | _HU_MARKER_EXTRA,
    SupportedLanguage.EN: STOPWORDS_EN | _EN_MARKER_EXTRA,
    SupportedLanguage.ES: STOPWORDS_ES | _ES_MARKER_EXTRA,
}


def stopwords_for(language: SupportedLanguage) -> frozenset[str]:
    if language in (SupportedLanguage.UNKNOWN, SupportedLanguage.MIXED):
        return STOPWORDS_HU | STOPWORDS_EN | STOPWORDS_ES
    if language == SupportedLanguage.HU:
        return STOPWORDS_HU
    if language == SupportedLanguage.EN:
        return STOPWORDS_EN
    if language == SupportedLanguage.ES:
        return STOPWORDS_ES
    return STOPWORDS_HU | STOPWORDS_EN | STOPWORDS_ES


def keyword_hints_for(language: SupportedLanguage) -> frozenset[str]:
    if language in (SupportedLanguage.UNKNOWN, SupportedLanguage.MIXED):
        return KEYWORD_HINTS_HU | KEYWORD_HINTS_EN | KEYWORD_HINTS_ES
    if language == SupportedLanguage.HU:
        return KEYWORD_HINTS_HU
    if language == SupportedLanguage.EN:
        return KEYWORD_HINTS_EN
    if language == SupportedLanguage.ES:
        return KEYWORD_HINTS_ES
    return KEYWORD_HINTS_HU | KEYWORD_HINTS_EN | KEYWORD_HINTS_ES


def topic_rules_for(language: SupportedLanguage) -> dict[str, tuple[str, ...]]:
    if language in (SupportedLanguage.UNKNOWN, SupportedLanguage.MIXED):
        return {**TOPIC_RULES_HU, **TOPIC_RULES_EN, **TOPIC_RULES_ES}
    if language == SupportedLanguage.HU:
        return TOPIC_RULES_HU
    if language == SupportedLanguage.EN:
        return TOPIC_RULES_EN
    if language == SupportedLanguage.ES:
        return TOPIC_RULES_ES
    return {**TOPIC_RULES_HU, **TOPIC_RULES_EN, **TOPIC_RULES_ES}


__all__ = [
    "LANGUAGE_MARKERS",
    "keyword_hints_for",
    "stopwords_for",
    "topic_rules_for",
]
