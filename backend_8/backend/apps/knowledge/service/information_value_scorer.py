# backend/apps/knowledge/service/information_value_scorer.py
# Scores sentence/claim information density and claim-refinement eligibility.

from __future__ import annotations

import re
from typing import Any

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.service.facade_helpers import SentenceCandidate


class InformationValueScorer:
    _CLAIM_FINE_SPLIT_ALLOWED_BLOCK_TYPES = {"paragraph", "list_item"}
    _CLAIM_FINE_SPLIT_MIN_WORDS = 12
    _CLAIM_FINE_SPLIT_MIN_SIGNAL_SCORE = 2
    _CLAIM_FINE_SPLIT_MAX_BLOCKS_PER_DOCUMENT = 80
    _CLAIM_FINE_SPLIT_MAX_BLOCK_RATIO = 0.15
    _CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS = 24
    _CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE = 2
    _CLAIM_FINE_SPLIT_CONNECTOR_PATTERN = re.compile(
        r"\b(?:és|vagy|illetve|valamint|továbbá|azonban|viszont|ha|amennyiben|kivéve|feltéve)\b",
        flags=re.IGNORECASE,
    )
    _CLAIM_FINE_SPLIT_PREDICATE_PATTERN = re.compile(
        r"\b(?:kell|köteles|jogosult|lehet|van|minősül|alkalmazandó|teljesít(?:hető)?|fizet|"
        r"biztosít|nyújt|történ(?:ik|jen)|áll|érvényes|megszűnik|létrejön|köt|értesít|küld|visel)\b",
        flags=re.IGNORECASE,
    )

    @staticmethod
    def sentence_word_count(value: str) -> int:
        return len(re.findall(r"\b\w+\b", value, flags=re.UNICODE))

    @classmethod
    def build_claim_refinement_budget(cls, total_blocks: int) -> int:
        if total_blocks <= 0:
            return 0
        ratio_budget = max(1, int(total_blocks * cls._CLAIM_FINE_SPLIT_MAX_BLOCK_RATIO))
        return min(cls._CLAIM_FINE_SPLIT_MAX_BLOCKS_PER_DOCUMENT, ratio_budget)

    @classmethod
    def count_claim_refinement_signals(cls, text: str) -> dict[str, int]:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        lowered = normalized.lower()
        comma_count = normalized.count(",")
        connector_count = len(cls._CLAIM_FINE_SPLIT_CONNECTOR_PATTERN.findall(lowered))
        predicate_count = len(cls._CLAIM_FINE_SPLIT_PREDICATE_PATTERN.findall(lowered))
        punctuation_signal_count = int(";" in normalized) + int(":" in normalized) + int(comma_count >= 2)
        signal_score = punctuation_signal_count
        if connector_count >= 2:
            signal_score += 1
        if predicate_count >= 2:
            signal_score += 1
        if (" ha " in f" {lowered} " or "amennyiben" in lowered) and connector_count >= 1:
            signal_score += 1
        return {
            "word_count": cls.sentence_word_count(normalized),
            "connector_count": connector_count,
            "predicate_count": predicate_count,
            "punctuation_signal_count": punctuation_signal_count,
            "signal_score": signal_score,
        }

    @classmethod
    def should_attempt_claim_refinement(
        cls,
        candidate: SentenceCandidate,
        *,
        block_type: str,
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, int]]:
        signals = cls.count_claim_refinement_signals(candidate.text)
        if block_type not in cls._CLAIM_FINE_SPLIT_ALLOWED_BLOCK_TYPES:
            return False, "unsupported_block_type", signals
        if signals["word_count"] < cls._CLAIM_FINE_SPLIT_MIN_WORDS:
            return False, "too_short", signals
        if signals["predicate_count"] == 0:
            return False, "no_predicate_signal", signals
        if signals["signal_score"] < cls._CLAIM_FINE_SPLIT_MIN_SIGNAL_SCORE:
            return False, "low_signal_score", signals
        if refinement_state is not None:
            attempted_blocks = int(refinement_state.get("attempted_blocks") or 0)
            hit_blocks = int(refinement_state.get("hit_blocks") or 0)
            budget_blocks = int(refinement_state.get("budget_blocks") or 0)
            if budget_blocks >= 0 and attempted_blocks >= budget_blocks:
                return False, "budget_exhausted", signals
            early_stop_after_blocks = int(
                refinement_state.get("early_stop_after_blocks") or cls._CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS
            )
            min_hit_blocks_to_continue = int(
                refinement_state.get("min_hit_blocks_to_continue") or cls._CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE
            )
            if attempted_blocks >= early_stop_after_blocks and hit_blocks < min_hit_blocks_to_continue:
                return False, "low_yield_early_stop", signals
        return True, "eligible", signals

    @staticmethod
    def score_information_value(
        *,
        sentence: Sentence,
        mentions: list[Mention],
        claim: Claim | None,
        interpretation: SentenceInterpretation,
    ) -> tuple[float, str, str]:
        text = sentence.text_content.strip()
        lowered = text.lower()
        tokens = [token for token in re.findall(r"\b\w+\b", text, flags=re.UNICODE) if token]
        token_count = len(tokens)
        score = 0.5
        reasons: list[str] = []
        block_type = str(sentence.metadata.get("block_type") or "")
        header_context_text = str(sentence.metadata.get("header_context_text") or "").strip()
        metadata_kind = str(sentence.metadata.get("metadata_kind") or "").strip()

        if block_type == "heading":
            score = 8.0 if token_count >= 2 else 6.5
            reasons.append("szakasz_fejlec_kontextus")
            if mentions:
                score += min(0.8, 0.3 + len(mentions) * 0.2)
                reasons.append("fejlecben_van_mention")
            score = max(0.0, min(10.0, round(score, 2)))
            return score, "context_strong", "header_context_without_direct_claim"
        if block_type == "metadata":
            if metadata_kind == "table_of_contents":
                return 0.0, "discard_candidate", "table_of_contents_not_interpreted"
            return 1.0, "discard_candidate", "metadata_not_interpreted"
        if block_type == "noise":
            return 0.0, "discard_candidate", "noise_not_interpreted"

        has_subject = bool(claim and claim.subject_text and claim.subject_text.strip())
        has_predicate = bool(claim and claim.predicate_text and claim.predicate_text.strip())
        has_object = bool(claim and claim.object_text and str(claim.object_text).strip())
        if has_subject:
            score += 2.0
            reasons.append("van_subject")
        if has_predicate:
            score += 2.0
            reasons.append("van_predicate")
        if has_object:
            score += 1.5
            reasons.append("van_object")
        if mentions:
            score += min(1.5, 0.6 + len(mentions) * 0.25)
            reasons.append("van_mention")
        if interpretation.claim_type != "other":
            score += 1.0
            reasons.append("tipizalhato_claim")
        if interpretation.assertion_mode in {"rule", "fact", "negation"}:
            score += 0.8
            reasons.append("egyertelmu_allitasmod")
        if interpretation.time_mode != "unknown":
            score += 0.5
            reasons.append("van_idokeret")
        if interpretation.space_mode not in {"unknown", "location_independent"}:
            score += 0.5
            reasons.append("van_terkeret")
        if token_count >= 8:
            score += 0.8
            reasons.append("eleg_hosszu")
        if header_context_text:
            score += 1.2
            reasons.append("fejlec_kontextus")

        fragment_leads = (
            "és ",
            "valamint ",
            "illetve ",
            "vagy ",
            "de ",
            "azonban ",
            "amely ",
            "amelyet ",
            "mely ",
            "melyet ",
            "hogy ",
            "így ",
            "továbbá ",
            "részére ",
            "az alábbiak szerint",
        )
        starts_like_fragment = lowered.startswith(fragment_leads)
        if token_count < 3:
            score -= 3.0
            reasons.append("nagyon_rovid")
        elif token_count < 5:
            score -= 1.5
            reasons.append("rovid")
        if starts_like_fragment:
            score -= 2.2
            reasons.append("toredekes_kezdete")
            if token_count <= 4 and not header_context_text:
                score -= 1.8
                reasons.append("rovid_kontextusfuggo_toredek")
        if not has_predicate:
            score -= 2.4
            reasons.append("nincs_onallo_predicate")
        if not has_object and token_count < 6:
            score -= 1.0
            reasons.append("gyenge_allitasmag")
        if block_type in {"heading", "metadata", "noise", "footer"}:
            score -= 2.5
            reasons.append("nem_tudaselem_blokk")
        if re.fullmatch(r"[\d.\-() /]+", text):
            score -= 4.0
            reasons.append("puszta_hivatkozas")
        if re.match(r"^\s*\d+(?:\.\d+){0,5}\.?\s*$", text):
            score -= 3.5
            reasons.append("csak_sorszam")

        score = max(0.0, min(10.0, round(score, 2)))
        if score < 3.0:
            status = "merge_with_previous" if starts_like_fragment or token_count < 5 else "discard_candidate"
        elif score < 5.0:
            status = "weak"
        elif score < 7.5:
            status = "usable"
        else:
            status = "strong"

        if score < 3.0 and starts_like_fragment:
            reason = "fragment_without_independent_predicate"
        elif score < 3.0:
            reason = "low_information_density"
        elif score < 5.0:
            reason = "partial_claim_with_context_dependency"
        elif score < 7.5:
            reason = "usable_claim"
        else:
            reason = "high_information_claim"
        return score, status, reason


__all__ = ["InformationValueScorer"]
