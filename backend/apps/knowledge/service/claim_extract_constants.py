"""ClaimExtractorV1: nyelvfüggetlen konstansok és predikátum-span típus."""
from __future__ import annotations

import re

from apps.knowledge.service.claim_patterns_hu import (
    HU_USE_PREDICATE_FOLDS,
    TITLE_RELATION_PREDICATES as HU_TITLE_RELATION_PREDICATES,
    USE_HEAD_PHRASE_RE as HU_USE_HEAD_PHRASE_RE,
    WEAK_DUPLICATE_USE_PREDICATE_FOLDS as HU_WEAK_DUPLICATE_USE_FOLDS,
)

TRIM_CHARS = " ,;:-."
YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")
SUBJECT_TIME_PATTERNS = {
    "hu": ("jelenleg",),
    "en": ("currently",),
    "es": ("actualmente",),
}
TEMPORAL_TAIL_KEYWORDS = {
    "hu": ("jelenleg", "most", "még", "meg", "korabban", "korábban", "elotte", "előtte", "utana", "utána"),
    "en": ("currently", "now", "before", "earlier", "previously"),
    "es": ("actualmente", "ahora", "antes", "anteriormente"),
}
OBJECT_LEADING_FILLERS = {
    "hu": ("de", "viszont", "azonban", "jelenleg", "most", "korábban", "korabban"),
    "en": ("but", "however", "currently", "now"),
    "es": ("pero", "sin embargo", "actualmente", "ahora"),
}
UNCERTAINTY_MARKERS = {
    "hu": ("talán", "talan", "nem biztos"),
    "en": ("maybe", "not sure", "unclear"),
    "es": ("quizás", "quizas", "tal vez"),
}
TITLE_RELATION_PREDICATES = {
    "hu": set(HU_TITLE_RELATION_PREDICATES),
}
WEAK_DUPLICATE_USE_PREDICATES = {
    "hu": set(HU_WEAK_DUPLICATE_USE_FOLDS),
    "en": {"use", "uses"},
    "es": {"usa", "utiliza"},
}
USE_SUBJECT_MENTION_TYPES = {"module", "feature", "software", "product"}
USE_PREDICATE_FOLDS: dict[str, set[str]] = {
    "hu": set(HU_USE_PREDICATE_FOLDS),
    "en": {"use", "uses"},
    "es": {"usa", "utiliza"},
}
EN_RESPONSIBLE_COMPOUNDS: tuple[str, ...] = (
    "was previously responsible",
    "was responsible",
)
ES_RESPONSIBLE_COMPOUNDS: tuple[str, ...] = (
    "fue responsable anteriormente de",
    "fue responsable de",
)
WEAK_DUPLICATE_MODAL_PREDICATES = {
    "hu": {"kell", "kotelezo", "igenyel"},
    "en": {"must", "required", "requires"},
    "es": {"debe", "obligatorio"},
}
STATE_OBJECT_PRONOUNS = {
    "hu": {"ez", "az"},
    "en": {"it", "this", "that"},
    "es": {"esto", "eso"},
}
STATE_OBJECT_TEMPORAL_PREFIXES = {
    "hu": {"ma", "most", "jelenleg"},
    "en": {"in", "on", "at", "before", "after", "since", "currently", "now"},
    "es": {"en", "antes", "despues", "después", "desde", "actualmente", "ahora"},
}
MODAL_PREDICATES = {
    "hu": {"kell", "kotelezo", "igenyel", "tilos"},
    "en": {"must", "should", "required", "forbidden", "requires"},
    "es": {"debe", "deberia", "debería", "obligatorio", "prohibido"},
}
STATE_AUXILIARIES = {
    "en": {"is", "was"},
    "es": {"esta", "está", "estaba"},
}
STATE_COMPLEMENTS = {
    "en": {"active", "inactive"},
    "es": {"activa", "activo", "inactiva", "inactivo"},
}
MENTION_TYPE_PRIORITY = {
    "person": 0,
    "company": 1,
    "software": 2,
    "module": 3,
    "feature": 4,
    "policy": 5,
    "process": 6,
    "location": 7,
    "object": 8,
    "unknown": 9,
}
CLAUSE_BREAK_KEYWORDS = {
    "hu": ("de", "viszont", "azonban"),
    "en": ("but", "however"),
    "es": ("pero", "sin embargo"),
}


class PredicateMatch(tuple):
    @property
    def predicate(self) -> str:
        return self[0]

    @property
    def start(self) -> int:
        return self[1]

    @property
    def end(self) -> int:
        return self[2]
