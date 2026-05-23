from __future__ import annotations

import re
import unicodedata


_ARTICLES_BY_LANG: dict[str, frozenset[str]] = {
    "hu": frozenset({"a", "az", "egy"}),
    "en": frozenset({"the", "a", "an"}),
    "es": frozenset({"el", "la", "los", "las", "un", "una"}),
}

_TIME_WORDS: frozenset[str] = frozenset(
    {
        "jelenleg",
        "korábban",
        "currently",
        "previously",
        "actualmente",
        "anteriormente",
    }
)

_HU_SUFFIXES: tuple[str, ...] = (
    "nak",
    "nek",
    "ban",
    "ben",
    "nál",
    "nél",
)

_YEAR_TOKEN = re.compile(r"^[12]\d{3}$")
_CANONICAL_TOKEN_ALIASES: dict[str, str] = {
    "admin": "admin",
    "administrator": "admin",
    "administrador": "admin",
    "user": "user",
    "felhasznalo": "user",
    "felhasználó": "user",
    "usuario": "user",
    "legacy": "legacy",
    "regi": "legacy",
    "régi": "legacy",
    "helpdesk": "helpdesk",
    "import": "import",
    "deprecated": "deprecated",
    "megszunt": "deprecated",
    "megszűnt": "deprecated",
    "data": "data",
    "adatvedelmi": "data",
    "adatvédelmi": "data",
    "proteccion": "protection",
    "protección": "protection",
    "datos": "data",
    "de": "",
    "protection": "protection",
    "lead": "lead",
    "felelos": "lead",
    "felelős": "lead",
    "responsable": "lead",
    "support": "support",
    "soporte": "support",
    "module": "module",
    "modul": "module",
    "modulo": "module",
    "módulo": "module",
    "billing": "billing",
    "facturacion": "billing",
    "facturación": "billing",
    "service": "service",
    "servicio": "service",
    "account": "account",
    "cuenta": "account",
}
_CANONICAL_TOKEN_ORDER: dict[str, int] = {
    "admin": 10,
    "user": 20,
    "legacy": 30,
    "helpdesk": 40,
    "import": 50,
    "deprecated": 60,
    "data": 70,
    "protection": 80,
    "lead": 90,
    "support": 100,
    "module": 110,
    "billing": 120,
    "service": 130,
    "account": 140,
}


def _lang_prefix(language: str | None) -> str | None:
    if not language:
        return None
    return language.lower().split("-", 1)[0].strip() or None


def _articles_for_language(language: str | None) -> frozenset[str]:
    key = _lang_prefix(language)
    if key in _ARTICLES_BY_LANG:
        return _ARTICLES_BY_LANG[key]
    return frozenset.union(*_ARTICLES_BY_LANG.values())


def _strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _punctuation_to_space(text: str) -> str:
    return re.sub(r"[^\w\s-]+", " ", text, flags=re.UNICODE)


def _collapse_ws(text: str) -> str:
    return " ".join(text.split())


def _tokens(text: str) -> list[str]:
    return [t for t in text.split() if t]


def _strip_leading_articles(tokens: list[str], articles: frozenset[str]) -> list[str]:
    out = list(tokens)
    while out and out[0] in articles:
        out.pop(0)
    return out


def _strip_time_words(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in _TIME_WORDS]


def _strip_hu_suffix_token(token: str) -> str:
    if len(token) < 4:
        return token
    for suf in _HU_SUFFIXES:
        if token.endswith(suf) and len(token) > len(suf) + 2:
            return token[: -len(suf)]
    return token


def _apply_hu_suffixes(tokens: list[str]) -> list[str]:
    return [_strip_hu_suffix_token(t) for t in tokens]


def _minimal_en_es_cleanup(token: str) -> str:
    if len(token) > 3 and token.endswith("'s"):
        return token[:-2]
    return token


def _apply_en_es_light(tokens: list[str], language: str | None) -> list[str]:
    key = _lang_prefix(language)
    if key not in {"en", "es"}:
        return tokens
    return [_minimal_en_es_cleanup(t) for t in tokens]


def _is_year_token(t: str) -> bool:
    if not _YEAR_TOKEN.match(t):
        return False
    try:
        y = int(t)
    except ValueError:
        return False
    return 1000 <= y <= 2999


def _filter_year_tokens(tokens: list[str]) -> list[str]:
    if len(tokens) == 2 and _is_year_token(tokens[1]):
        return tokens
    return [t for t in tokens if not _is_year_token(t)]


def _canonicalize_tokens(tokens: list[str]) -> list[str]:
    canonical = [_CANONICAL_TOKEN_ALIASES.get(token, token) for token in tokens]
    canonical = [token for token in canonical if token]
    deduped = list(dict.fromkeys(canonical))
    return sorted(deduped, key=lambda item: (_CANONICAL_TOKEN_ORDER.get(item, 1000), item))


def normalize_entity_key(
    text: str,
    language: str | None = None,
    *,
    strip_accents: bool = False,
) -> str:
    """Entitáskulcs normalizálása determinisztikus szabályokkal (LLM nélkül).

    A ``strip_accents=False`` alapértelmezés megtartja az ékezeteket (pl. „márton”).
    ``strip_accents=True`` ASCII-közeli alakot ad (pl. „marton”).
    """
    raw = text.strip()
    if not raw:
        return ""

    normalized = unicodedata.normalize("NFC", raw)
    if strip_accents:
        normalized = _strip_accents(normalized)
    normalized = normalized.lower()

    normalized = _punctuation_to_space(normalized)
    normalized = _collapse_ws(normalized)
    tokens = _tokens(normalized)
    if not tokens:
        return ""

    articles = _articles_for_language(language)
    tokens = _strip_leading_articles(tokens, articles)
    tokens = _strip_time_words(tokens)
    tokens = _strip_leading_articles(tokens, articles)

    if _lang_prefix(language) == "hu":
        tokens = _apply_hu_suffixes(tokens)
    tokens = _apply_en_es_light(tokens, language)

    tokens = _filter_year_tokens(tokens)
    return " ".join(tokens)


def canonicalize_entity_key(
    text: str,
    language: str | None = None,
    *,
    strip_accents: bool = True,
) -> str:
    """Lightweight cross-language entity canonical form for deterministic matching."""
    normalized = normalize_entity_key(text, language=language, strip_accents=strip_accents)
    if not normalized:
        return ""
    tokens = _tokens(normalized)
    canonical_tokens = _canonicalize_tokens(tokens)
    if {"adatvedelmi", "felelos"} <= set(tokens) and "protection" not in canonical_tokens:
        canonical_tokens.append("protection")
        canonical_tokens = sorted(canonical_tokens, key=lambda item: (_CANONICAL_TOKEN_ORDER.get(item, 1000), item))
    return " ".join(canonical_tokens)


__all__ = ["canonicalize_entity_key", "normalize_entity_key"]
