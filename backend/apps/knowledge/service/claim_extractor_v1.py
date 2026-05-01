"""ClaimExtractorV1: nyelvi minta-extraktorok + beépített quality gate."""
from __future__ import annotations

import logging
from dataclasses import replace
import re

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extract_debug import debug_print
from apps.knowledge.service.claim_extract_normalize import sentence_text
from apps.knowledge.service.claim_extract_v1_core import extract_claims_v1
from apps.knowledge.service.claim_patterns_en import EnglishClaimPatternExtractor
from apps.knowledge.service.claim_patterns_es import SpanishClaimPatternExtractor
from apps.knowledge.service.claim_patterns_hu import HungarianClaimPatternExtractor
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.claim_typing import apply_claim_type_config
from apps.knowledge.service.language_rules import detect_language, resolve_language

logger = logging.getLogger(__name__)


_NEGATED_STATE_RE = {
    "hu": re.compile(r"^(?:a|az)?\s*(?P<subject>.+?)\s+nem\s+(?:aktív|aktiv|inaktív|inaktiv)\b", re.IGNORECASE),
    "en": re.compile(r"\bis\s+not\s+(?:active|inactive)\b", re.IGNORECASE),
    "es": re.compile(r"\bno\s+debe\b", re.IGNORECASE),
}


def _apply_negation_polarity(claims: list[Claim], *, sentence_text: str, language: str) -> list[Claim]:
    if not claims:
        return claims
    pattern = _NEGATED_STATE_RE.get(language)
    if pattern is None or not pattern.search(sentence_text or ""):
        return claims

    updated: list[Claim] = []
    for claim in claims:
        predicate = claim.predicate_text
        object_text = claim.object_text
        subject_text = claim.subject_text
        metadata = dict(claim.metadata or {})
        changed = False

        if language == "hu":
            match = pattern.search(sentence_text or "")
            if match is not None:
                subject_text = str(match.group("subject") or "").strip(" ,;:-.")
                predicate = "aktív"
                object_text = "false"
                changed = True

        if language == "en" and object_text in {None, "not"}:
            lowered_pred = predicate.lower()
            if lowered_pred in {"active", "inactive", "is active", "is inactive"}:
                predicate = "active"
                object_text = "false"
                changed = True

        if language in {"hu", "en"} and object_text is None:
            lowered_pred = predicate.lower()
            if language == "hu" and lowered_pred in {"aktív", "aktiv", "inaktív", "inaktiv"}:
                predicate = "aktív"
                object_text = "false"
                changed = True
            if language == "en" and lowered_pred in {"active", "inactive", "is active", "is inactive"}:
                predicate = "active"
                object_text = "false"
                changed = True

        if language == "es" and predicate.lower() == "debe":
            metadata["polarity"] = "negative"
            updated.append(replace(claim, metadata=metadata))
            continue

        if changed:
            metadata["polarity"] = "negative"
            updated.append(
                replace(
                    claim,
                    subject_text=subject_text,
                    predicate_text=predicate,
                    object_text=object_text,
                    metadata=metadata,
                )
            )
            continue

        updated.append(claim)
    return updated


class ClaimExtractorV1:
    def __init__(self, *, quality_gate: ClaimQualityGate | None = None) -> None:
        self.quality_gate = quality_gate or ClaimQualityGate()
        self.patterns = {
            "hu": HungarianClaimPatternExtractor(),
            "en": EnglishClaimPatternExtractor(),
            "es": SpanishClaimPatternExtractor(),
        }

    def debug_skip(self, sentence: Sentence, reason: str | None) -> None:
        logger.debug(
            "[CLAIM EXTRACTOR SKIP] sentence_id=%s reason=%s text=%.200s",
            getattr(sentence, "id", ""),
            reason,
            sentence_text(sentence),
        )

    def build_claim_from_candidate(self, candidate: Claim, sentence: Sentence, mentions: list[Mention]) -> Claim:
        """Claim jelölt szövegazonosítók és meta összekötése a mondatttal (``mentions``: API-kompatibilitás)."""
        _ = mentions
        sid = getattr(sentence, "id", None) or candidate.sentence_id
        meta = {**dict(candidate.metadata or {}), "extractor": (candidate.metadata or {}).get("extractor", "ClaimExtractorV1")}
        return replace(
            candidate,
            sentence_id=sid or candidate.sentence_id,
            metadata=meta,
        )

    def extract_raw(
        self, sentence: Sentence, mentions: list[Mention], language: str | None = None
    ) -> list[Claim]:
        """Quality-gate **nélküli** kandidáns extraction (``run_v1_sentence_claim_pipeline``-nak),
        hogy a quality-gate diagnosztika (rejected_claims) a pipeline-szintű hívásban
        keletkezzen, és a ``weak_auxiliary``/``duplicate_weak`` counterek aggregálhatók
        legyenek (regresszió v1: A/B/C csoport).
        """
        st = sentence_text(sentence).strip()
        if not st:
            return []

        resolved_language = detect_language(
            st,
            preferred_language=resolve_language(
                text=st,
                language=sentence.metadata.get("language") or sentence.metadata.get("language_tag") or language,
            ),
        )

        should_process, reason = self.quality_gate.should_process_sentence(st, resolved_language)
        if not should_process:
            self.debug_skip(sentence, reason)
            return []

        extractor = self.patterns.get(resolved_language) or self.patterns["hu"]
        pattern_candidates = extractor.extract_claim_candidates(sentence, mentions)

        claims: list[Claim] = []
        for pc in pattern_candidates:
            claim = self.build_claim_from_candidate(pc.claim(), sentence, mentions)
            claim = apply_claim_type_config(claim)
            claims.append(claim)
        return claims

    def extract(self, sentence: Sentence, mentions: list[Mention], language: str | None = None) -> list[Claim]:
        claims = self.extract_raw(sentence, mentions, language=language)
        if not claims:
            return []
        st = sentence_text(claims[0].metadata.get("sentence_text") if False else sentence).strip()
        resolved_language = detect_language(
            st,
            preferred_language=resolve_language(
                text=st,
                language=sentence.metadata.get("language") or sentence.metadata.get("language_tag") or language,
            ),
        )
        kept, _ = self.quality_gate.filter_claims_for_sentence(
            claims,
            st,
            language=resolved_language,
            sentence=sentence,
        )
        return _apply_negation_polarity(kept, sentence_text=st, language=resolved_language)

    @staticmethod
    def debug_print(sentence: Sentence, claims: list[Claim], language: str | None = None) -> None:
        debug_print(sentence, claims, language=language)


__all__ = ["ClaimExtractorV1", "debug_print", "extract_claims_v1"]
