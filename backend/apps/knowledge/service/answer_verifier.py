from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerVerification:
    is_grounded: bool
    has_evidence: bool
    mentions_conflict: bool
    invented_terms: list[str]


def verify_answer(answer_text: str, evidence_blocks: list[dict], *, forbidden_terms: list[str] | None = None) -> AnswerVerification:
    forbidden = forbidden_terms or []
    lowered = answer_text.lower()
    invented = [term for term in forbidden if term.lower() in lowered]
    has_evidence = bool(evidence_blocks)
    has_conflict = any(int(block.get("conflict_count") or 0) > 0 for block in evidence_blocks)
    mentions_conflict = not has_conflict or any(
        token in lowered for token in ("ellentmond", "conflict", "conflicto", "vitatott", "disputed")
    )
    return AnswerVerification(
        is_grounded=has_evidence and not invented and mentions_conflict,
        has_evidence=has_evidence,
        mentions_conflict=mentions_conflict,
        invented_terms=invented,
    )


__all__ = ["AnswerVerification", "verify_answer"]
