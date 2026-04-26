"""Knowledge: mondat → elfogadott claim lista. Lépések (sorrend).

1. **Nyelv** – a hívó (``KnowledgeFacade``) oldja fel (meta, dokumentum, detektálás).
2. **Quality gate: mondat** – ``ClaimQualityGate.try_sentence_screening`` (kérdés, zaj, fragment);
   ha elutasít, nincs extract.
3. **Extraktor** – jelenleg egy ``ClaimExtractorV1`` (HU/EN/ES szabályok a modulon belül);
   később itt választható nyelvspecifikus implementáció.
4. **Nyers claim jelöltek** – ``ClaimExtractorV1.extract`` (subject/predicate/object + beépített típusozás).
5. **Sanitizer** – ``sanitize_claim_candidates`` → ``claim_sanitizer`` (subject/object/predicate normalizálás).
6. **Claim typing config** – az extract végén ``apply_claim_type_config`` (nem külön lépés a facade-ban).
7. **Quality gate: claim** – ``filter_claims_with_diagnostics(..., assume_sentence_prevalidated=True)``.
8. **Max claim / mondat** – a gate végén (esemény vs. vegyes limit).
9. **Assertion mode (v1)** – mondatszintű multilingual negation jelölés a claim-eken.
10. **Visszaadás** – ``(claims, quality_diagnostics)``.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.claim_sanitizer import normalize_claim_text, sanitize_object, sanitize_subject


_NEGATION_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "hu": (
        re.compile(r"\bnem\s+\w", re.IGNORECASE),
        re.compile(r"\bnincs\b", re.IGNORECASE),
        re.compile(r"\btilos\b", re.IGNORECASE),
        re.compile(r"\btagadja\b", re.IGNORECASE),
    ),
    "en": (
        re.compile(r"\b(?:is|are|was|were|do|does|did|has|have|had|will|would|can|could|should|must|may)\s+not\b", re.IGNORECASE),
        re.compile(r"\bn['’]t\b", re.IGNORECASE),
        re.compile(r"\bnever\b", re.IGNORECASE),
        re.compile(r"\bno\s+longer\b", re.IGNORECASE),
        re.compile(r"\bnot\s+\w", re.IGNORECASE),
    ),
    "es": (
        re.compile(r"\bno\s+(?:debe|deben|puede|pueden|es|son|está|están|estuvo|fue|ha|han|hay)\b", re.IGNORECASE),
        re.compile(r"\bnunca\b", re.IGNORECASE),
        re.compile(r"\btampoco\b", re.IGNORECASE),
        re.compile(r"\bno\s+\w", re.IGNORECASE),
    ),
}


def detect_sentence_negation(text: str, *, language: str) -> bool:
    """Mondatszintű negation detektor (HU + EN + ES, determinisztikus regex)."""
    if not text:
        return False
    lang = (language or "").lower()
    patterns = _NEGATION_PATTERNS.get(lang)
    if patterns is None:
        return False
    return any(pat.search(text) for pat in patterns)


def sanitize_claim_candidates(claims: list[Claim], *, default_language: str = "en") -> list[Claim]:
    """5. lépés: subject/object közös tisztítás (``claim_sanitizer``)."""
    out: list[Claim] = []
    for claim in claims:
        lang = str((claim.metadata or {}).get("language") or default_language)
        subj = sanitize_subject(claim.subject_text, language=lang)
        obj_raw = claim.object_text
        obj = sanitize_object(obj_raw, language=lang) if obj_raw is not None else None
        if obj == "":
            obj = None
        pred = normalize_claim_text(claim.predicate_text)
        meta = {**dict(claim.metadata or {}), "sanitizer_applied": True}
        out.append(
            replace(
                claim,
                subject_text=subj,
                predicate_text=pred or claim.predicate_text,
                object_text=obj,
                metadata=meta,
            )
        )
    return out


def run_v1_sentence_claim_pipeline(
    *,
    sentence: Sentence,
    mentions: list[Mention],
    resolved_language: str,
    extractor: ClaimExtractorV1,
    quality_gate: ClaimQualityGate,
) -> tuple[list[Claim], dict[str, Any]]:
    """v1 út: mondat gate → extract → sanitize → claim gate (+ limit)."""
    early = quality_gate.try_sentence_screening(sentence, resolved_language=resolved_language)
    if early is not None:
        if early.get("sentence_reason") == "sentence_is_explicit_noise":
            early = {
                **early,
                "raw_sentence_reason": early.get("sentence_reason"),
                "sentence_reason": "noise_sentence",
            }
        return [], early

    raw_claims = [
        replace(
            claim,
            metadata={
                **dict(claim.metadata or {}),
                "language": resolved_language,
            },
        )
        for claim in extractor.extract_raw(sentence, mentions, language=resolved_language)
    ]
    raw_claims = sanitize_claim_candidates(raw_claims)
    kept, diagnostics = quality_gate.filter_claims_with_diagnostics(
        sentence,
        raw_claims,
        language=resolved_language,
        assume_sentence_prevalidated=True,
    )
    sentence_text = str(getattr(sentence, "text_content", "") or "")
    if detect_sentence_negation(sentence_text, language=resolved_language) and kept:
        kept = [replace(item, assertion_mode="negation") for item in kept]
    return kept, diagnostics


__all__ = [
    "detect_sentence_negation",
    "run_v1_sentence_claim_pipeline",
    "sanitize_claim_candidates",
]
