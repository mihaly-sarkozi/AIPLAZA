"""ClaimExtractorV1 mag: adott ``language`` mellett predikátumok → claimek."""
from __future__ import annotations

import logging
from dataclasses import replace

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extract_mentions import find_best_mention_id
from apps.knowledge.service.claim_extract_normalize import sentence_text
from apps.knowledge.service.claim_extract_object_build import fallback_subject
from apps.knowledge.service.claim_extract_postprocess import drop_weak_duplicate_claims, should_reuse_split_subject
from apps.knowledge.service.claim_extract_predicates import (
    find_predicates,
    merge_compound_predicates,
    should_skip_predicate,
)
from apps.knowledge.service.claim_extract_single_claim import build_claim
from apps.knowledge.service.claim_extract_text_clean import build_claim_text, clean_subject_slice, is_valid_subject_text

logger = logging.getLogger(__name__)


def extract_claims_v1(sentence: Sentence, mentions: list[Mention], *, language: str) -> list[Claim]:
    text = sentence_text(sentence).strip()
    if not text:
        return []
    predicates = find_predicates(text, language=language)
    predicates = merge_compound_predicates(predicates, text, language=language)
    filtered_predicates = []
    for predicate_match in predicates:
        previous_predicate = filtered_predicates[-1] if filtered_predicates else None
        if should_skip_predicate(predicate_match, previous_predicate, text=text, language=language):
            continue
        filtered_predicates.append(predicate_match)
    predicates = filtered_predicates
    if not predicates:
        logger.debug("[CLAIM GATE] no predicate, no claim generated")
        return []

    base_subject = fallback_subject(text, predicates[0].start, language=language)
    base_subject = clean_subject_slice(base_subject, language=language)
    canonical_subject = base_subject if is_valid_subject_text(base_subject, language=language) else None
    claims: list[Claim] = []
    for index, predicate_match in enumerate(predicates):
        next_predicate_idx = predicates[index + 1].start if index + 1 < len(predicates) else None
        claim = build_claim(
            sentence,
            mentions=mentions,
            text=text,
            predicate=predicate_match.predicate,
            predicate_idx=predicate_match.start,
            predicate_end_idx=predicate_match.end,
            next_predicate_idx=next_predicate_idx,
            language=language,
            inherited_subject=canonical_subject,
        )
        if claim is None:
            continue
        subject_source = str((claim.metadata or {}).get("subject_source", ""))
        if index > 0 and should_reuse_split_subject(
            claim.subject_text,
            base_subject=canonical_subject,
            subject_source=subject_source,
        ):
            metadata = dict(claim.metadata or {})
            metadata["subject_source"] = "split_inherited"
            claim = replace(
                claim,
                subject_text=canonical_subject or "",
                subject_mention_id=find_best_mention_id(mentions, canonical_subject),
                metadata={
                    **metadata,
                    "claim_text": build_claim_text(text, canonical_subject or "", claim.predicate_text, claim.object_text),
                },
            )
        if index == 0 and is_valid_subject_text(claim.subject_text, language=language):
            canonical_subject = claim.subject_text
        claims.append(claim)
    return drop_weak_duplicate_claims(claims, language=language)


__all__ = ["extract_claims_v1"]
