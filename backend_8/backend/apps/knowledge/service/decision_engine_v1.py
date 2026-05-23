from __future__ import annotations

from apps.knowledge.domain.candidate_selection import EntityCandidate
from apps.knowledge.domain.decision_analysis import DECISION_ENGINE_VERSION, DecisionAnalysis
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.domain.similarity_analysis import SimilarityAnalysis
from apps.knowledge.domain.tension_analysis import TensionAnalysis
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key, normalize_entity_key
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


def _candidate_canonical_key(candidate: EntityCandidate | None) -> str:
    if candidate is None:
        return ""
    explicit = canonicalize_entity_key(getattr(candidate, "candidate_canonical_key", "") or "")
    if explicit:
        return explicit
    return canonicalize_entity_key(candidate.candidate_name) or normalize_entity_key(
        candidate.candidate_name,
        strip_accents=True,
    )


def _similarity_score(similarity: SimilarityAnalysis | None) -> float:
    if similarity is None:
        return 0.0
    return float(getattr(similarity, "total_similarity_score", 0.0) or 0.0)


def _candidate_score(candidate: EntityCandidate | None) -> float:
    if candidate is None:
        return 0.0
    return float(getattr(candidate, "score", 0.0) or 0.0)


def _merge_group(candidate: EntityCandidate | None) -> dict[str, object]:
    group = dict(getattr(candidate, "merge_candidate_group", None) or {})
    if group:
        return group
    canonical_key = _candidate_canonical_key(candidate)
    return {
        "canonical_key": canonical_key,
        "group_size": 1 if candidate is not None else 0,
        "duplicate_memory_profile_count": 0,
        "candidate_entity_ids": [candidate.candidate_entity_id] if candidate is not None else [],
        "candidate_names": [candidate.candidate_name] if candidate is not None else [],
        "selected_candidate_entity_id": candidate.candidate_entity_id if candidate is not None else "",
    }


def _candidate_group_size(candidate: EntityCandidate | None) -> int:
    group = _merge_group(candidate)
    try:
        return int(group.get("group_size") or 0)
    except (TypeError, ValueError):
        return 0


def _global_profile_id(value: str) -> str:
    cleaned = normalize_entity_key(value, strip_accents=True).replace(" ", "-")
    return f"global-profile:{cleaned or 'unknown'}"


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
        )
        affected_claim_ids = list(evidence.get("claim_ids") or [])

        if candidate is None or similarity is None:
            return self._decision(
                new_profile,
                candidate,
                decision="create_new_profile",
                confidence=0.8,
                reason="create_new_profile:no_candidate_above_threshold",
                manual_review=False,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        score = _similarity_score(similarity)
        group_size = _candidate_group_size(candidate)

        if score >= 0.75 and group_size > 1:
            return self._decision(
                new_profile,
                candidate,
                decision="merge_required",
                confidence=0.8,
                reason="merge_required:multiple_high_similarity_candidates_same_canonical_group",
                manual_review=True,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        if score >= 0.75:
            return self._decision(
                new_profile,
                candidate,
                decision="attach_existing",
                confidence=max(0.75, min(0.98, score)),
                manual_review=False,
                affected_claim_ids=affected_claim_ids,
                reason="attach_existing:single_high_similarity_candidate",
                evidence=evidence,
            )

        if 0.4 <= score < 0.75:
            return self._decision(
                new_profile,
                candidate,
                decision="uncertain_match",
                confidence=max(0.4, min(0.74, score)),
                reason="uncertain_match:medium_similarity",
                manual_review=True,
                affected_claim_ids=affected_claim_ids,
                evidence=evidence,
            )

        return self._decision(
            new_profile,
            candidate,
            decision="create_new_profile",
            confidence=0.75,
            reason="create_new_profile:no_candidate_above_threshold",
            manual_review=False,
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
        decisions: list[DecisionAnalysis] = []
        seen_profiles: set[str] = set()
        best_similarity_by_profile: dict[str, SimilarityAnalysis] = {}
        for similarity in similarities:
            profile_id = str(similarity.search_profile_id)
            current = best_similarity_by_profile.get(profile_id)
            if current is None or _similarity_score(similarity) > _similarity_score(current):
                best_similarity_by_profile[profile_id] = similarity
        for profile_id, similarity in best_similarity_by_profile.items():
            candidate_entity_id = str(similarity.candidate_entity_id)
            profile = next((item for item in new_profiles if str(item.search_profile_id) == profile_id), None)
            if profile is None:
                continue
            candidate = candidates_by_pair.get((profile_id, candidate_entity_id))
            decisions.append(self.decide(profile, candidate=candidate, similarity=similarity, tension=None))
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
        candidate_id = str(candidate.candidate_entity_id if candidate is not None else "")
        technical_entity_id = str(new_profile.technical_entity_id or "")
        selected_profile_id = _global_profile_id(candidate_id) if decision == "attach_existing" and candidate_id else None
        created_profile_id = (
            _global_profile_id(technical_entity_id) if decision == "create_new_profile" and technical_entity_id else None
        )
        merge_group = _merge_group(candidate) if candidate is not None else {}
        group_size = _candidate_group_size(candidate)
        return DecisionAnalysis(
            search_profile_id=new_profile.search_profile_id,
            technical_entity_id=new_profile.technical_entity_id,
            local_entity_id=new_profile.local_entity_id,
            candidate_entity_id=candidate_id,
            candidate_name=str(candidate.candidate_name if candidate is not None else ""),
            candidate_type=str(candidate.candidate_type if candidate is not None else "unknown"),
            decision=decision,
            decision_type=decision,
            selected_candidate_id=candidate_id or None,
            selected_candidate_score=round(_candidate_score(candidate), 4),
            attach_to=candidate_id if decision == "attach_existing" and candidate_id else None,
            decision_confidence=round(max(0.0, min(1.0, confidence)), 4),
            selected_profile_id=selected_profile_id,
            created_profile_id=created_profile_id,
            decision_reason=reason,
            candidate_group_size=group_size,
            competing_candidates_count=max(0, group_size - 1),
            merge_candidate_group=merge_group if decision == "merge_required" else {},
            manual_review_required=manual_review,
            affected_claim_ids=affected_claim_ids,
            evidence=evidence,
            builder_version=self.version,
        )


__all__ = ["DecisionEngineV1"]
