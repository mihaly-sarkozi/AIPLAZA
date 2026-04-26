from __future__ import annotations

from .types import ClaimCandidate, ComplementHints, ParsedToken, TokenSpan


def score_claim(
    span: TokenSpan,
    predicate: ParsedToken,
    subject: ParsedToken | None,
    complements: ComplementHints,
) -> float:
    """Confidence score based on presence of subject/object and predicate strength."""

    score = 0.25
    if subject is not None:
        score += 0.3
    if complements.objects:
        score += 0.2
    if complements.attributes:
        score += 0.1
    if predicate.pos == "VERB":
        score += 0.1
    return min(score, 1.0)


def collect_reasons(
    predicate: ParsedToken,
    subject: ParsedToken | None,
    complements: ComplementHints,
) -> list[str]:
    reasons = []
    reasons.append(f"predicate:{predicate.pos}")
    if subject:
        reasons.append(f"subject:{subject.dep}")
    if complements.objects:
        reasons.append("has_object")
    if complements.attributes:
        reasons.append("has_attribute")
    if complements.modifiers:
        reasons.append("has_modifier")
    return reasons
