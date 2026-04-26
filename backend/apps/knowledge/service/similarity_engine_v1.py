"""Similarity Engine v1 for selected entity candidates.

Deterministic, evidence-based scoring only. This module never decides merge,
conflict resolution, or persistence.
"""
from __future__ import annotations

import re
from typing import Any

from apps.knowledge.domain.candidate_selection import EntityCandidate
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.domain.similarity_analysis import SIMILARITY_ENGINE_VERSION, SimilarityAnalysis
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key, normalize_entity_key
from apps.knowledge.service.language_rules import fold_text


_COMPATIBLE_TYPES = {
    frozenset({"software", "module"}),
    frozenset({"software", "system"}),
    frozenset({"module", "system"}),
}
_WEIGHTS = {
    "name_similarity": 0.32,
    "type_similarity": 0.18,
    "keyword_similarity": 0.18,
    "relation_similarity": 0.10,
    "object_similarity": 0.12,
    "time_similarity": 0.04,
    "space_similarity": 0.04,
    "evidence_overlap_similarity": 0.02,
}

_SEMANTIC_TOKEN_ALIASES = {
    "2fa": "twofactor",
    "two": "twofactor",
    "factor": "twofactor",
    "twofactor": "twofactor",
    "two-factor": "twofactor",
    "ketfaktoros": "twofactor",
    "kétfaktoros": "twofactor",
    "authentication": "authentication",
    "azonositast": "authentication",
    "azonosítást": "authentication",
    "azonositas": "authentication",
    "azonosítás": "authentication",
    "enable": "enable",
    "hasznalnia": "enable",
    "használnia": "enable",
    "user": "user",
    "felhasznalo": "user",
    "felhasználó": "user",
    "usuario": "user",
    "admin": "admin",
    "administrator": "admin",
    "administrador": "admin",
    "legacy": "legacy",
    "regi": "legacy",
    "régi": "legacy",
    "helpdesk": "helpdesk",
    "import": "import",
    "deprecated": "deprecated",
    "megszunt": "deprecated",
    "megszűnt": "deprecated",
    "payment": "payment",
    "payments": "payment",
    "card": "payment",
    "cards": "payment",
    "invoice": "payment",
    "invoices": "payment",
}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[\wÁÉÍÓÖŐÚÜŰáéíóöőúüűñÑ]+", fold_text(value), flags=re.UNICODE) if token}


def _semantic_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in _tokens(value.replace("-", " ")):
        tokens.add(_SEMANTIC_TOKEN_ALIASES.get(token, token))
    return tokens


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


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


def _profile_evidence(profile: SearchProfile) -> dict[str, Any]:
    claim_ids: list[str] = []
    sentence_ids: list[str] = []
    source_id = str(profile.source_id) if profile.source_id is not None else None
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
        if source_id is None and ref.get("source_id"):
            source_id = str(ref.get("source_id"))
    return {"claim_ids": claim_ids, "sentence_ids": sentence_ids, "source_id": source_id}


def _candidate_evidence(candidate: EntityCandidate) -> dict[str, Any]:
    evidence = dict(candidate.evidence or {})
    return {
        "claim_ids": [str(item) for item in evidence.get("claim_ids") or [] if item],
        "sentence_ids": [str(item) for item in evidence.get("sentence_ids") or [] if item],
        "source_id": evidence.get("source_id"),
    }


def _has_evidence(evidence: dict[str, Any]) -> bool:
    return bool(evidence.get("claim_ids") or evidence.get("sentence_ids"))


def _name_similarity(left: SearchProfile, right: SearchProfile) -> tuple[float, str]:
    left_key = normalize_entity_key(left.normalized_key or left.entity_name, strip_accents=True)
    right_key = normalize_entity_key(right.normalized_key or right.entity_name, strip_accents=True)
    if left_key and right_key and left_key == right_key:
        return 1.0, "name:normalized_exact"
    left_canonical = canonicalize_entity_key(left.normalized_key or left.entity_name)
    right_canonical = canonicalize_entity_key(right.normalized_key or right.entity_name)
    if left_canonical and right_canonical and left_canonical == right_canonical:
        return 1.0, "name:canonical_exact"
    token_score = _jaccard(_tokens(left_key or left.entity_name), _tokens(right_key or right.entity_name))
    semantic_score = max(
        _jaccard(_semantic_tokens(left_key or left.entity_name), _semantic_tokens(right_key or right.entity_name)),
        _jaccard(_tokens(left_canonical), _tokens(right_canonical)),
    )
    if semantic_score > token_score:
        return semantic_score, f"name:canonical_overlap:{semantic_score:.2f}"
    return token_score, f"name:token_overlap:{token_score:.2f}"


def _type_similarity(left: SearchProfile, right: SearchProfile) -> tuple[float, str]:
    left_type = fold_text(left.entity_type)
    right_type = fold_text(right.entity_type)
    if not left_type or not right_type or "unknown" in {left_type, right_type}:
        return 0.3, "type:unknown"
    if left_type == right_type:
        return 1.0, "type:match"
    if frozenset({left_type, right_type}) in _COMPATIBLE_TYPES:
        return 0.65, "type:compatible"
    return 0.0, "type:mismatch"


def _value_overlap(left_values: list[str], right_values: list[str], label: str) -> tuple[float, str]:
    score = _jaccard({fold_text(v) for v in left_values if v}, {fold_text(v) for v in right_values if v})
    return score, f"{label}:overlap:{score:.2f}"


def _semantic_value_overlap(left_values: list[str], right_values: list[str], label: str) -> tuple[float, str]:
    left_tokens: set[str] = set()
    right_tokens: set[str] = set()
    for value in left_values:
        left_tokens.update(_semantic_tokens(value))
    for value in right_values:
        right_tokens.update(_semantic_tokens(value))
    score = _jaccard(left_tokens, right_tokens)
    return score, f"{label}:semantic_overlap:{score:.2f}"


def _location_name_conflict(left: SearchProfile, right: SearchProfile, name_score: float) -> bool:
    if fold_text(left.entity_type) != "location" or fold_text(right.entity_type) != "location":
        return False
    left_tokens = _tokens(left.normalized_key or left.entity_name)
    right_tokens = _tokens(right.normalized_key or right.entity_name)
    if not left_tokens or not right_tokens:
        return False
    overlap = left_tokens & right_tokens
    return bool(overlap) and left_tokens != right_tokens and name_score < 0.75


def _time_similarity(left: SearchProfile, right: SearchProfile) -> tuple[float, str]:
    left_filter = dict(left.time_filters or {})
    right_filter = dict(right.time_filters or {})
    left_values = [str(v) for v in left_filter.get("values") or [] if v]
    right_values = [str(v) for v in right_filter.get("values") or [] if v]
    if left_values or right_values:
        score, _reason = _value_overlap(left_values, right_values, "time")
        return score, f"time:value_overlap:{score:.2f}"
    if left_filter.get("dominant") and left_filter.get("dominant") == right_filter.get("dominant"):
        return 1.0, "time:mode_match"
    return 0.0, "time:unknown"


def _space_similarity(left: SearchProfile, right: SearchProfile) -> tuple[float, str]:
    left_filter = dict(left.space_filters or {})
    right_filter = dict(right.space_filters or {})
    left_values = [str(v) for v in left_filter.get("values") or [] if v]
    right_values = [str(v) for v in right_filter.get("values") or [] if v]
    if left_values or right_values:
        score, _reason = _value_overlap(left_values, right_values, "space")
        return score, f"space:value_overlap:{score:.2f}"
    if left_filter.get("dominant") and left_filter.get("dominant") == right_filter.get("dominant"):
        return 1.0, "space:mode_match"
    return 0.0, "space:unknown"


def _evidence_overlap_similarity(left_evidence: dict[str, Any], right_evidence: dict[str, Any]) -> tuple[float, str]:
    left = {*(str(v) for v in left_evidence.get("claim_ids") or []), *(str(v) for v in left_evidence.get("sentence_ids") or [])}
    right = {*(str(v) for v in right_evidence.get("claim_ids") or []), *(str(v) for v in right_evidence.get("sentence_ids") or [])}
    score = _jaccard(left, right)
    return score, f"evidence:overlap:{score:.2f}"


def _band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


class SimilarityEngineV1:
    version: str = SIMILARITY_ENGINE_VERSION

    def analyze_for_profile(
        self,
        new_profile: SearchProfile,
        candidates: list[EntityCandidate],
        candidate_profiles: list[SearchProfile],
    ) -> list[SimilarityAnalysis]:
        profiles_by_id = {_candidate_entity_id(profile): profile for profile in candidate_profiles}
        analyses: list[SimilarityAnalysis] = []
        for candidate in candidates:
            profile = profiles_by_id.get(candidate.candidate_entity_id)
            if profile is None:
                continue
            analyses.append(self._analyze_pair(new_profile, candidate, profile))
        return sorted(analyses, key=lambda item: item.total_similarity_score, reverse=True)

    def analyze_many(
        self,
        new_profiles: list[SearchProfile],
        candidates: list[EntityCandidate],
        candidate_profiles: list[SearchProfile],
    ) -> list[SimilarityAnalysis]:
        candidates_by_profile_id: dict[str, list[EntityCandidate]] = {}
        for candidate in candidates:
            candidates_by_profile_id.setdefault(str(candidate.search_profile_id), []).append(candidate)
        analyses: list[SimilarityAnalysis] = []
        for profile in new_profiles:
            analyses.extend(
                self.analyze_for_profile(
                    profile,
                    candidates_by_profile_id.get(str(profile.search_profile_id), []),
                    candidate_profiles,
                )
            )
        return analyses

    def _analyze_pair(
        self,
        new_profile: SearchProfile,
        candidate: EntityCandidate,
        candidate_profile: SearchProfile,
    ) -> SimilarityAnalysis:
        new_evidence = _profile_evidence(new_profile)
        candidate_evidence = _candidate_evidence(candidate)
        reasons: list[str] = []

        component_values = {
            "name_similarity": _name_similarity(new_profile, candidate_profile),
            "type_similarity": _type_similarity(new_profile, candidate_profile),
            "keyword_similarity": _value_overlap(new_profile.keywords, candidate_profile.keywords, "keyword"),
            "relation_similarity": _value_overlap(
                list((new_profile.relation_filters or {}).get("predicates") or []),
                list((candidate_profile.relation_filters or {}).get("predicates") or []),
                "relation_predicate",
            ),
            "object_similarity": _value_overlap(
                list((new_profile.relation_filters or {}).get("objects") or []),
                list((candidate_profile.relation_filters or {}).get("objects") or []),
                "relation_object",
            ),
            "time_similarity": _time_similarity(new_profile, candidate_profile),
            "space_similarity": _space_similarity(new_profile, candidate_profile),
            "evidence_overlap_similarity": _evidence_overlap_similarity(new_evidence, candidate_evidence),
        }
        component_scores: dict[str, float] = {}
        total = 0.0
        for key, (score, reason) in component_values.items():
            clean_score = max(0.0, min(1.0, float(score)))
            component_scores[key] = round(clean_score, 4)
            total += clean_score * _WEIGHTS[key]
            reasons.append(reason)

        semantic_keyword_score, semantic_keyword_reason = _semantic_value_overlap(
            new_profile.keywords,
            candidate_profile.keywords,
            "keyword",
        )
        if semantic_keyword_score > component_scores["keyword_similarity"]:
            component_scores["keyword_similarity"] = round(semantic_keyword_score, 4)
            total += (semantic_keyword_score - float(component_values["keyword_similarity"][0])) * _WEIGHTS[
                "keyword_similarity"
            ]
            reasons.append(semantic_keyword_reason)

        object_values_left = list((new_profile.relation_filters or {}).get("objects") or [])
        object_values_right = list((candidate_profile.relation_filters or {}).get("objects") or [])
        semantic_object_score, semantic_object_reason = _semantic_value_overlap(
            object_values_left,
            object_values_right,
            "relation_object",
        )
        if semantic_object_score > component_scores["object_similarity"]:
            component_scores["object_similarity"] = round(semantic_object_score, 4)
            total += (semantic_object_score - float(component_values["object_similarity"][0])) * _WEIGHTS["object_similarity"]
            reasons.append(semantic_object_reason)

        if _location_name_conflict(new_profile, candidate_profile, component_scores["name_similarity"]):
            total *= 0.55
            reasons.append("location:name_conflict_penalty")

        # Ne kapjon medium band-et pusztán szerkezeti egyezésből:
        # ha csak type + time/space (és esetleg evidence) egyezik, de név/keyword/relation/object
        # oldalról nincs érdemi jel, maradjon low.
        if (
            component_scores["name_similarity"] < 0.25
            and component_scores["keyword_similarity"] == 0.0
            and component_scores["relation_similarity"] == 0.0
            and component_scores["object_similarity"] == 0.0
        ):
            total = min(total, 0.39)
            reasons.append("structural_only_similarity_cap")

        # Same-entity boost: ha a normalized name és a type is pontos egyezés, a re-ingest
        # detektálható legyen a high band-ben. Kis boost (+0.05), 1.0-ra cap-elve. Ezzel a
        # konzisztens evidence-szel rendelkező duplikátumok stabilan high similarity-t kapnak.
        if (
            ("name:normalized_exact" in reasons or "name:canonical_exact" in reasons)
            and "type:match" in reasons
            and not _location_name_conflict(new_profile, candidate_profile, component_scores["name_similarity"])
        ):
            total = min(1.0, total + 0.05)
            reasons.append("same_entity_name_boost")

        if (
            component_scores["type_similarity"] == 1.0
            and component_scores["name_similarity"] >= 0.75
            and component_scores["keyword_similarity"] >= 0.5
            and not _location_name_conflict(new_profile, candidate_profile, component_scores["name_similarity"])
        ):
            total = min(1.0, total + 0.08)
            reasons.append("same_type_strong_lexical_overlap_boost")

        evidence = {
            "claim_ids": candidate_evidence.get("claim_ids") or [],
            "sentence_ids": candidate_evidence.get("sentence_ids") or [],
            "source_id": candidate_evidence.get("source_id"),
            "new_claim_ids": new_evidence.get("claim_ids") or [],
            "new_sentence_ids": new_evidence.get("sentence_ids") or [],
        }
        if not _has_evidence(candidate_evidence):
            total = min(total, 0.69)
            reasons.append("evidence:missing_high_cap")

        total = round(max(0.0, min(1.0, total)), 4)
        return SimilarityAnalysis(
            search_profile_id=new_profile.search_profile_id,
            technical_memory_chunk_id=new_profile.technical_memory_chunk_id,
            technical_entity_id=new_profile.technical_entity_id,
            local_entity_id=new_profile.local_entity_id,
            candidate_entity_id=candidate.candidate_entity_id,
            candidate_name=candidate.candidate_name,
            candidate_type=candidate.candidate_type,
            total_similarity_score=total,
            similarity_band=_band(total),
            component_scores=component_scores,
            similarity_reasons=reasons,
            evidence=evidence,
            builder_version=self.version,
        )


__all__ = ["SimilarityEngineV1"]
