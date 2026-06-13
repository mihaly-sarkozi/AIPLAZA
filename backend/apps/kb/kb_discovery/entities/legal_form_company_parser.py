from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_CHAR = r"\wÁÉÍÓÖŐÚÜŰáéíóöőúüű"

_BOUNDARY_TOKENS: dict[str, frozenset[str]] = {
    "global": frozenset(),
    "hu": frozenset(
        {
            "a",
            "az",
            "és",
            "vagy",
            "hogy",
            "ha",
            "mert",
            "ügyfél",
            "partner",
            "szerződés",
            "szerződését",
            "számla",
            "kapcsolat",
            "által",
            "részére",
            "felé",
        }
    ),
    "en": frozenset(
        {
            "the",
            "a",
            "an",
            "and",
            "or",
            "with",
            "by",
            "for",
            "from",
            "to",
            "in",
            "on",
            "of",
            "was",
            "is",
            "are",
            "signed",
            "policy",
            "contract",
            "customer",
            "client",
            "partner",
        }
    ),
    "es": frozenset(
        {
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
            "y",
            "o",
            "con",
            "de",
            "del",
            "para",
            "por",
            "en",
            "contrato",
            "cliente",
            "socio",
            "empresa",
        }
    ),
}

_MAX_COMPANY_TOKENS = 4
_TOKEN_SPLIT = re.compile(r"\S+")


@dataclass(frozen=True)
class CompanyNameMatch:
    name: str
    start_offset: int
    end_offset: int
    legal_form: str
    company_name_tokens: tuple[str, ...]
    boundary_stop: str | None
    matched_suffix: str


def collect_company_name_before_suffix(
    text: str,
    suffix_start: int,
    suffix_end: int,
    *,
    language_code: str | None,
    legal_form: str,
    matched_suffix: str,
    max_tokens: int = _MAX_COMPANY_TOKENS,
    known_names: frozenset[str] | None = None,
) -> CompanyNameMatch | None:
    left_text = text[:suffix_start].rstrip()
    comma_before_suffix = left_text.endswith(",")
    if comma_before_suffix:
        left_text = left_text[:-1].rstrip()

    tokens = _TOKEN_SPLIT.findall(left_text)
    if not tokens:
        return None

    collected: list[str] = []
    boundary_stop: str | None = None
    for token in reversed(tokens[-(max_tokens * 3) :]):
        if len(collected) >= max_tokens:
            break
        if _is_boundary_token(token, language_code):
            boundary_stop = token.strip(".,;:\"'()[]")
            break
        if _is_valid_company_token(token, known_names=known_names):
            collected.insert(0, token)
            continue
        break

    if not collected:
        return None

    prefix = _join_company_tokens(collected, comma_before_suffix=comma_before_suffix)
    suffix = text[suffix_start:suffix_end]
    company_name = f"{prefix}, {suffix}" if comma_before_suffix else f"{prefix} {suffix}".strip()
    name_start = _find_name_start(text, collected[0], suffix_start)
    if name_start < 0:
        return None

    return CompanyNameMatch(
        name=company_name,
        start_offset=name_start,
        end_offset=suffix_end,
        legal_form=legal_form,
        company_name_tokens=tuple(token.strip(".,;:\"'()[]") for token in collected),
        boundary_stop=boundary_stop,
        matched_suffix=matched_suffix,
    )


def _join_company_tokens(tokens: list[str], *, comma_before_suffix: bool) -> str:
    cleaned = [token.rstrip(",") if comma_before_suffix and index == len(tokens) - 1 else token for index, token in enumerate(tokens)]
    return " ".join(cleaned)


def _find_name_start(text: str, first_token: str, suffix_start: int) -> int:
    probe = first_token.rstrip(",")
    search_end = suffix_start
    idx = text.rfind(probe, 0, search_end)
    if idx >= 0:
        return idx
    idx = text.rfind(first_token, 0, search_end)
    return idx


def _boundary_tokens_for(language_code: str | None) -> frozenset[str]:
    code = (language_code or "en").strip().lower()
    return _BOUNDARY_TOKENS["global"] | _BOUNDARY_TOKENS.get(code, _BOUNDARY_TOKENS["en"])


def _is_boundary_token(token: str, language_code: str | None) -> bool:
    clean = token.strip(".,;:\"'()[]")
    if not clean:
        return True
    lowered = clean.casefold()
    if lowered == "empresa" and clean[0].isupper():
        return False
    return lowered in _boundary_tokens_for(language_code)


def _is_valid_company_token(token: str, *, known_names: frozenset[str] | None = None) -> bool:
    clean = token.strip(".,;:\"'()[]")
    if not clean or len(clean) > 40:
        return False
    if known_names and clean in known_names:
        return True
    if clean[0].isupper():
        return True
    if any(char.isdigit() for char in clean):
        return True
    if clean.isupper() and len(clean) <= 8:
        return True
    if re.search(r"[.\-]", clean):
        return True
    return False


def suffix_match_is_valid(text: str, start: int, end: int) -> bool:
    matched = text[start:end]
    if not matched:
        return False
    if re.search(r"[.\-]", matched):
        return True
    if matched.isupper():
        return True
    return matched[0].isupper()


__all__ = [
    "CompanyNameMatch",
    "collect_company_name_before_suffix",
    "suffix_match_is_valid",
]
