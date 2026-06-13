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


LANGUAGE_MARKERS: dict[SupportedLanguage, frozenset[str]] = {
    SupportedLanguage.HU: frozenset(
        {
            "az",
            "és",
            "hogy",
            "van",
            "egy",
            "ügyfél",
            "számlázás",
            "budapesten",
            "történik",
            "július",
            "irodában",
        }
    ),
    SupportedLanguage.EN: frozenset(
        {
            "the",
            "customer",
            "onboarding",
            "starts",
            "in",
            "london",
            "office",
            "invoice",
        }
    ),
    SupportedLanguage.ES: frozenset(
        {
            "la",
            "el",
            "de",
            "factura",
            "madrid",
            "cliente",
            "se",
            "crea",
            "oficina",
        }
    ),
}


def stopwords_for(language: SupportedLanguage) -> frozenset[str]:
    if language == SupportedLanguage.HU:
        return STOPWORDS_HU
    if language == SupportedLanguage.EN:
        return STOPWORDS_EN
    if language == SupportedLanguage.ES:
        return STOPWORDS_ES
    return STOPWORDS_HU | STOPWORDS_EN | STOPWORDS_ES


def keyword_hints_for(language: SupportedLanguage) -> frozenset[str]:
    if language == SupportedLanguage.HU:
        return KEYWORD_HINTS_HU
    if language == SupportedLanguage.EN:
        return KEYWORD_HINTS_EN
    if language == SupportedLanguage.ES:
        return KEYWORD_HINTS_ES
    return KEYWORD_HINTS_HU | KEYWORD_HINTS_EN | KEYWORD_HINTS_ES


def topic_rules_for(language: SupportedLanguage) -> dict[str, tuple[str, ...]]:
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
