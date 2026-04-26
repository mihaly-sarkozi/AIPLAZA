from __future__ import annotations

from apps.knowledge.domain.candidate_selection import EntityCandidate
from apps.knowledge.domain.decision_analysis import DECISION_ENGINE_VERSION, DecisionAnalysis
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.domain.similarity_analysis import SimilarityAnalysis
from apps.knowledge.domain.tension_analysis import TensionAnalysis
from apps.knowledge.service.entity_key_normalization import normalize_entity_key
from apps.knowledge.service.language_rules import fold_text


def _norm_key(profile: SearchProfile) -> str:
    return normalize_entity_key(profile.normalized_key or profile.entity_name, strip_accents=True)


def _candidate_entity_id(profile: SearchProfile) -> str:
    for value in (
        profile.technical_entity_id,
        profile.local_entity_id,
        profile.technical_memory_chunk_id,
        profile.search_profile_id,
    ):
        if value is not None:
            return str(value)
    return ""


def _candidate_evidence(candidate: EntityCandidate | None) -> dict[str, list[str]]:
    evidence = dict(getattr(candidate, "evidence", None) or {})
    return {
        "claim_ids": [str(item) for item in evidence.get("claim_ids") or [] if item],
        "sentence_ids": [str(item) for item in evidence.get("sentence_ids") or [] if item],
    }


def _profile_evidence(profile: SearchProfile) -> dict[str, list[str]]:
    claim_ids: list[str] = []
    sentence_ids: list[str] = []
    for ref in profile.evidence_refs or []:
        if not isinstance(ref, dict):
            continue
        for value in ref.get("claim_ids") or []:
            text = str(value or "").strip()
            if text and text not in claim_ids:
                claim_ids.append(text)
        for value in ref.get("sentence_ids") or []:
            text = str(value or "").strip()
            if text and text not in sentence_ids:
                sentence_ids.append(text)
        value = str(ref.get("claim_id") or "").strip()
        if value and value not in claim_ids:
            claim_ids.append(value)
        value = str(ref.get("sentence_id") or "").strip()
        if value and value not in sentence_ids:
            sentence_ids.append(value)
    return {"claim_ids": claim_ids, "sentence_ids": sentence_ids}


def _merge_evidence(*items: dict[str, list[str]]) -> dict[str, list[str]]:
    claim_ids: list[str] = []
    sentence_ids: list[str] = []
    for item in items:
        for value in item.get("claim_ids") or []:
            if value and value not in claim_ids:
                claim_ids.append(value)
        for value in item.get("sentence_ids") or []:
            if value and value not in sentence_ids:
                sentence_ids.append(value)
    return {"claim_ids": claim_ids, "sentence_ids": sentence_ids}


def _same_entity_name(new_profile: SearchProfile, candidate: EntityCandidate | None) -> bool:
    if candidate is None:
        return False
    left = _norm_key(new_profile)
    right = normalize_entity_key(candidate.candidate_name, strip_accents=True)
    return bool(left and right and left == right)


def _same_type(new_profile: SearchProfile, candidate: EntityCandidate | None) -> bool:
    return bool(candidate is not None and fold_text(new_profile.entity_type) == fold_text(candidate.candidate_type))


def _different_location_name(new_profile: SearchProfile, candidate: EntityCandidate | None) -> bool:
    if candidate is None:
        return False
    return (
        fold_text(new_profile.entity_type) == "location"
        and fold_text(candidate.candidate_type) == "location"
        and not _same_entity_name(new_profile, candidate)
    )


class DecisionEngineV1:
    version: str = DECISION_ENGINE_VERSION

    def decide(
        self,
        new_profile: SearchProfile,
        *,
        candidate: EntityCandidate | None = None,
        similarity: SimilarityAnalysis | None = None,
        tension: TensionAnalysis | None = None,
    ) -> DecisionAnalysis:
        evidence = _merge_evidence(
            _profile_evidence(new_profile),
            _candidate_evidence(candidate),
            dict((tension.evidence if tension is not None else {}) or {}),
        )
        affected_claim_ids = list(evidence.get("claim_ids") or [])

        if candidate is None or similarity is None:
            return self._decision(
                new_profile,
                candidate,
                decision="create_new",
                confidence=0.8,
                reason="create_new:no_candidate",
                manual_review=False,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        tension_band = str(getattr(tension, "tension_band", "none") or "none")
        tension_type = str(getattr(tension, "tension_type", "unrelated") or "unrelated")
        similarity_band = str(similarity.similarity_band or "low")

        if tension_band == "high":
            return self._decision(
                new_profile,
                candidate,
                decision="mark_conflict",
                confidence=0.9,
                reason="mark_conflict:high_tension",
                manual_review=True,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        if _different_location_name(new_profile, candidate):
            return self._decision(
                new_profile,
                candidate,
                decision="keep_separate",
                confidence=0.9,
                reason="keep_separate:different_location_name",
                manual_review=False,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        if _same_entity_name(new_profile, candidate) and _same_type(new_profile, candidate) and tension_band in {"none", "low"}:
            return self._decision(
                new_profile,
                candidate,
                decision="attach_existing",
                confidence=0.95,
                reason="attach_existing:same_entity_name_same_type_low_tension",
                manual_review=False,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        if similarity_band == "high" and tension_band in {"none", "low"}:
            return self._decision(
                new_profile,
                candidate,
                decision="attach_existing",
                confidence=0.85,
                reason="attach_existing:high_similarity_low_tension",
                manual_review=False,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        if similarity_band == "medium" and tension_band in {"none", "low"}:
            return self._decision(
                new_profile,
                candidate,
                decision="needs_review",
                confidence=0.55,
                reason="needs_review:medium_similarity_low_tension",
                manual_review=True,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        if similarity_band == "low":
            decision = "keep_separate" if tension_type == "unrelated" else "create_new"
            return self._decision(
                new_profile,
                candidate,
                decision=decision,
                confidence=0.75,
                reason=f"{decision}:low_similarity",
                manual_review=False,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        return self._decision(
            new_profile,
            candidate,
            decision="needs_review",
            confidence=0.45,
            reason="needs_review:uncertain_similarity_tension",
            manual_review=True,
            affected_claim_ids=affected_claim_ids,
            evidence=evidence,
        )

    def decide_many(
        self,
        new_profiles: list[SearchProfile],
        candidates: list[EntityCandidate],
        similarities: list[SimilarityAnalysis],
        tensions: list[TensionAnalysis],
    ) -> list[DecisionAnalysis]:
        candidates_by_pair = {
            (str(candidate.search_profile_id), str(candidate.candidate_entity_id)): candidate
            for candidate in candidates
        }
        similarities_by_pair = {
            (str(item.search_profile_id), str(item.candidate_entity_id)): item
            for item in similarities
        }
        tensions_by_pair = {
            (str(item.search_profile_id_a), str(item.technical_entity_id_b)): item
            for item in tensions
        }
        decisions: list[DecisionAnalysis] = []
        seen_profiles: set[str] = set()
        for key, similarity in similarities_by_pair.items():
            profile_id, candidate_entity_id = key
            profile = next((item for item in new_profiles if str(item.search_profile_id) == profile_id), None)
            if profile is None:
                continue
            candidate = candidates_by_pair.get(key)
            tension = tensions_by_pair.get((profile_id, candidate_entity_id))
            decisions.append(self.decide(profile, candidate=candidate, similarity=similarity, tension=tension))
            seen_profiles.add(profile_id)
        for profile in new_profiles:
            if str(profile.search_profile_id) not in seen_profiles:
                decisions.append(self.decide(profile))
        return decisions

    def _decision(
        self,
        new_profile: SearchProfile,
        candidate: EntityCandidate | None,
        *,
        decision: str,
        confidence: float,
        reason: str,
        manual_review: bool,
        affected_claim_ids: list[str],
        evidence: dict[str, list[str]],
    ) -> DecisionAnalysis:
        return DecisionAnalysis(
            search_profile_id=new_profile.search_profile_id,
            technical_entity_id=new_profile.technical_entity_id,
            local_entity_id=new_profile.local_entity_id,
            candidate_entity_id=str(candidate.candidate_entity_id if candidate is not None else ""),
            candidate_name=str(candidate.candidate_name if candidate is not None else ""),
            candidate_type=str(candidate.candidate_type if candidate is not None else "unknown"),
            decision=decision,
            decision_confidence=round(max(0.0, min(1.0, confidence)), 4),
            decision_reason=reason,
            manual_review_required=manual_review,
            affected_claim_ids=affected_claim_ids,
            evidence=evidence,
            builder_version=self.version,
        )


__all__ = ["DecisionEngineV1"]
