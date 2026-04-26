from __future__ import annotations

from typing import Iterable

from .types import ParsedDoc, ParsedToken


ADMISSIBLE_POS = {"VERB", "AUX", "ADJ"}
POLICY_LEXICON: dict[str, set[str]] = {
    "hu": {"kell", "tilos", "nem szabad", "lehet", "engedélyezett", "tiltott"},
    "en": {"must", "may", "allowed", "forbidden", "prohibited", "required"},
    "es": {"debe", "puede", "prohibido", "permitido", "obligatorio"},
}
COPULA_LEMMAS: dict[str, set[str]] = {
    "hu": {"van", "lenni", "lesz"},
    "en": {"be", "is", "are", "was", "were"},
    "es": {"ser", "estar", "es", "son", "fue", "era"},
}


def _normalized_language_tag(doc: ParsedDoc) -> str:
    return (doc.language_tag or "").split("-")[0].lower() or "hu"


def _is_policy_predicate(token: ParsedToken, doc: ParsedDoc) -> bool:
    return token.lemma.lower() in POLICY_LEXICON.get(_normalized_language_tag(doc), set())


def _is_finite_verb(token: ParsedToken) -> bool:
    return token.pos == "VERB" and token.dep not in {"aux", "aux:pass"}


def _is_copula_candidate(token: ParsedToken, doc: ParsedDoc) -> bool:
    return token.pos in {"AUX", "VERB"} and token.lemma.lower() in COPULA_LEMMAS.get(
        _normalized_language_tag(doc),
        COPULA_LEMMAS["hu"],
    )


def find_predicate_heads(doc: ParsedDoc) -> list[ParsedToken]:
    """Return tokens that can act as claim predicate nuclei."""

    candidates: list[ParsedToken] = []
    for token in doc.tokens:
        if token.pos not in ADMISSIBLE_POS:
            continue
        if _is_finite_verb(token) or _is_policy_predicate(token, doc) or _is_copula_candidate(token, doc):
            candidates.append(token)
            continue
        if token.pos == "ADJ" and token.dep in {"ROOT", "acomp", "xcomp"}:
            candidates.append(token)
            continue
    return sorted(candidates, key=lambda tok: tok.idx)
