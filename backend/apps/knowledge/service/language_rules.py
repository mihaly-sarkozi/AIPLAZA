from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata


class SupportedLanguage(str, Enum):
    HU = "hu"
    EN = "en"
    ES = "es"


SUPPORTED_LANGUAGES = [item.value for item in SupportedLanguage]


@dataclass(frozen=True)
class LanguageRuleSet:
    language: str
    detection_keywords: tuple[str, ...]
    stopwords: tuple[str, ...]
    article_stopwords: tuple[str, ...]
    filler_words: tuple[str, ...]
    conjunction_keywords: tuple[str, ...]
    company_keywords: tuple[str, ...]
    software_keywords: tuple[str, ...]
    module_keywords: tuple[str, ...]
    feature_keywords: tuple[str, ...]
    policy_keywords: tuple[str, ...]
    process_keywords: tuple[str, ...]
    location_keywords: tuple[str, ...]
    predicate_keywords: tuple[str, ...]
    month_keywords: tuple[str, ...]
    claim_type_keywords: dict[str, tuple[str, ...]]


LANGUAGE_RULES: dict[str, LanguageRuleSet] = {
    "hu": LanguageRuleSet(
        language="hu",
        detection_keywords=("a", "az", "kötelező", "használ", "igényel", "jelenleg", "frissült", "működik"),
        stopwords=("a", "az", "egy", "és", "hogy", "vagy", "de", "is", "nem"),
        article_stopwords=("a", "az", "egy"),
        filler_words=("jelenleg",),
        conjunction_keywords=("és", "de", "vagy"),
        company_keywords=("kft", "zrt", "bt"),
        software_keywords=("rendszer", "szolgáltatás"),
        module_keywords=("modul",),
        feature_keywords=("funkció",),
        policy_keywords=("szabályzat",),
        process_keywords=("folyamat", "eljárás", "azonosítás"),
        location_keywords=("iroda", "helyszín", "telephely"),
        predicate_keywords=(
            "használ",
            "használja",
            "használnia",
            "tartalmaz",
            "van",
            "kapcsolódik",
            "függ",
            "kell",
            "tilos",
            "kötelező",
            "igényel",
            "igényli",
            "készít",
            "létrejött",
            "módosult",
            "frissült",
            "felelt",
            "felhatalmazza",
            "megszűnt",
            "megmarad",
            "működik",
            "vezetője",
            "felelőse",
            "aktív",
            "inaktív",
        ),
        month_keywords=(
            "január",
            "február",
            "március",
            "április",
            "május",
            "június",
            "július",
            "augusztus",
            "szeptember",
            "október",
            "november",
            "december",
            "januar",
            "februar",
            "marcius",
            "aprilis",
            "majus",
            "junius",
            "julius",
            "oktober",
        ),
        claim_type_keywords={
            "identifier": ("azonosító", "id", "uuid", "neve"),
            "stable_descriptor": ("van", "tartalmaz", "használ", "használja", "használnia", "készít"),
            "state": ("aktív", "inaktív", "elérhető", "állapot", "működik", "megmarad"),
            "relation": (
                "kapcsolódik",
                "függ",
                "használ",
                "igényel",
                "igényli",
                "felelt",
                "felhatalmazza",
                "vezetője",
                "felelőse",
            ),
            "event": ("történt", "létrejött", "módosult", "frissült", "megszűnt"),
            "rule_procedure": ("kell", "tilos", "kötelező", "ha", "akkor", "igényel", "igényli", "felhatalmazza"),
            "opinion": ("jó", "rossz", "gyenge", "erős", "szerintem"),
        },
    ),
    "en": LanguageRuleSet(
        language="en",
        detection_keywords=("the", "must", "uses", "was", "created", "updated", "inactive"),
        stopwords=("the", "a", "an", "and", "or", "of", "to", "in", "is", "was"),
        article_stopwords=("the", "a", "an"),
        filler_words=("currently",),
        conjunction_keywords=("and", "but", "or"),
        company_keywords=("ltd", "inc", "llc", "corp"),
        software_keywords=("system", "service"),
        module_keywords=("module",),
        feature_keywords=("feature",),
        policy_keywords=("policy",),
        process_keywords=("process", "procedure", "authentication"),
        location_keywords=("office", "location", "site"),
        predicate_keywords=(
            "uses",
            "use",
            "contains",
            "has",
            "is",
            "was",
            "connects",
            "depends",
            "must",
            "should",
            "required",
            "forbidden",
            "requires",
            "created",
            "was created",
            "updated",
            "was updated",
            "is inactive",
            "is active",
            "was deprecated",
            "deprecated",
            "active",
            "inactive",
            "remain",
            "remains",
            "accept",
            "accepts",
            "responsible",
            "was responsible",
            "was previously responsible",
            "is currently active",
            "was inactive",
            "was previously inactive",
            "leader",
            "is the compliance lead at",
        ),
        month_keywords=(
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        claim_type_keywords={
            "identifier": ("id", "uuid", "called", "is named"),
            "stable_descriptor": ("has", "contains", "uses", "use", "supports", "remain"),
            "state": ("active", "inactive", "is active", "is inactive", "state", "available", "remains"),
            "relation": ("connects", "depends", "belongs to", "uses", "use", "leader", "lead", "responsible", "conflict with"),
            "event": ("created", "was created", "updated", "was updated", "modified", "occurred", "deprecated", "was deprecated"),
            "rule_procedure": ("must", "should", "forbidden", "required", "requires", "if", "then", "accept", "accepts"),
            "opinion": ("good", "bad", "weak", "strong", "i think", "opinion"),
        },
    ),
    "es": LanguageRuleSet(
        language="es",
        detection_keywords=("el", "la", "debe", "utiliza", "esta", "está", "fue", "creada", "actualizado"),
        stopwords=("el", "la", "los", "las", "un", "una", "y", "o", "de", "del", "en", "es", "fue"),
        article_stopwords=("el", "la", "los", "las", "un", "una"),
        filler_words=("actualmente",),
        conjunction_keywords=("y", "pero", "o"),
        company_keywords=("s.l.", "sociedad limitada", "s.a.", "empresa"),
        software_keywords=("sistema", "servicio"),
        module_keywords=("módulo", "modulo"),
        feature_keywords=("función", "funcion"),
        policy_keywords=("política", "politica"),
        process_keywords=("proceso", "procedimiento", "autenticación", "autenticacion"),
        location_keywords=("oficina", "ubicación", "ubicacion", "sede"),
        predicate_keywords=(
            "fue responsable anteriormente de",
            "está actualmente activa",
            "esta actualmente activa",
            "estaba inactiva",
            "estaba inactivo",
            "fue creado",
            "fue creada",
            "fue desactivado",
            "esta activa",
            "está activa",
            "actualizado",
            "actualizada",
            "debería",
            "deberia",
            "obligatorio",
            "prohibido",
            "permanecen",
            "utiliza",
            "contiene",
            "depende",
            "conecta",
            "aceptar",
            "acepta",
            "creado",
            "creada",
            "inactivo",
            "inactiva",
            "activo",
            "activa",
            "desactivado",
            "usa",
            "tiene",
            "estaba",
            "está",
            "esta",
            "debe",
            "fue",
            "es",
        ),
        month_keywords=(
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ),
        claim_type_keywords={
            "identifier": ("identificador", "id", "uuid", "se llama", "nombre"),
            "stable_descriptor": ("tiene", "contiene", "usa", "utiliza", "soporta"),
            "state": ("activo", "activa", "inactivo", "inactiva", "esta activa", "está activa", "estaba inactiva", "estado", "disponible", "permanecen"),
            "relation": ("conecta", "depende", "pertenece", "usa", "responsable", "lider"),
            "event": ("creado", "creada", "fue creado", "fue creada", "actualizado", "actualizada", "modificado", "ocurrió", "ocurrio", "desactivado", "fue desactivado"),
            "rule_procedure": ("debe", "debería", "deberia", "obligatorio", "prohibido", "si", "entonces", "aceptar", "acepta"),
            "opinion": ("bueno", "malo", "débil", "debil", "fuerte", "creo", "opinión", "opinion"),
        },
    ),
}


def fold_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    normalized = str(language).strip().lower().split("-")[0]
    return normalized if normalized in LANGUAGE_RULES else None


def _contains_keyword(text: str, keyword: str) -> bool:
    haystack = fold_text(text)
    needle = fold_text(keyword)
    pattern = r"\b" + re.escape(needle) + r"\b"
    return re.search(pattern, haystack, flags=re.IGNORECASE) is not None


def detect_language(text: str, preferred_language: str | None = None) -> str:
    preferred = normalize_language(preferred_language)
    lowered = fold_text((text or "").strip())
    if not lowered:
        return "unknown"
    if preferred is not None and preferred in LANGUAGE_RULES:
        preferred_score = sum(2 if _contains_keyword(lowered, keyword) else 0 for keyword in LANGUAGE_RULES[preferred].detection_keywords)
        if preferred_score > 0:
            return preferred
    scores: dict[str, int] = {}
    for language, rules in LANGUAGE_RULES.items():
        score = sum(2 for keyword in rules.detection_keywords if _contains_keyword(lowered, keyword))
        score += sum(1 for keyword in rules.predicate_keywords if _contains_keyword(lowered, keyword))
        score += sum(1 for keyword in rules.month_keywords if _contains_keyword(lowered, keyword))
        scores[language] = score
    best_language = max(scores, key=scores.get, default="unknown")
    return best_language if scores.get(best_language, 0) > 0 else "unknown"


def resolve_language(*, text: str | None = None, language: str | None = None) -> str:
    return normalize_language(language) or detect_language(text or "")


def get_language_rules(language: str | None) -> LanguageRuleSet:
    normalized = normalize_language(language) or "hu"
    return LANGUAGE_RULES.get(normalized, LANGUAGE_RULES["hu"])


def keyword_match(text: str, keywords: tuple[str, ...], *, language: str | None = None) -> bool:
    rules = get_language_rules(language)
    haystack = (text or "").lower()
    return any(_contains_keyword(haystack, keyword) for keyword in keywords or rules.detection_keywords)


__all__ = [
    "LANGUAGE_RULES",
    "SUPPORTED_LANGUAGES",
    "LanguageRuleSet",
    "SupportedLanguage",
    "detect_language",
    "fold_text",
    "get_language_rules",
    "keyword_match",
    "normalize_language",
    "resolve_language",
]
