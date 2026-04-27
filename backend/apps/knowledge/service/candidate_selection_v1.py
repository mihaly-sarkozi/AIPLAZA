"""SearchProfile candidate selection (v1).

Deterministic, local, traceable candidate selection only. No merge decision,
LLM, parser, Qdrant indexing, or similarity engine.
"""
from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from apps.knowledge.domain.candidate_selection import CANDIDATE_SELECTION_BUILDER_VERSION, EntityCandidate
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key, normalize_entity_key
from apps.knowledge.service.language_rules import fold_text


_MIN_CANDIDATE_SCORE = 0.2
_COMPATIBLE_TYPES = {
    frozenset({"software", "module"}),
    frozenset({"software", "system"}),
    frozenset({"module", "system"}),
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
    "data": "data",
    "adatvedelmi": "data",
    "adatvédelmi": "data",
    "proteccion": "protection",
    "protección": "protection",
    "datos": "data",
    "protection": "protection",
    "lead": "lead",
    "felelos": "lead",
    "felelős": "lead",
    "responsable": "lead",
    "support": "support",
    "soporte": "support",
    "module": "module",
    "modul": "module",
    "modulo": "module",
    "módulo": "module",
    "billing": "billing",
    "facturacion": "billing",
    "facturación": "billing",
    "service": "service",
    "servicio": "service",
    "account": "account",
    "cuenta": "account",
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


def _append_reason(reasons: list[str], reason: str, value: float) -> None:
    if value <= 0:
        return
    reasons.append(f"{reason}:{value:.2f}")


def candidate_selection_attempt_count(new_profiles: list[SearchProfile], existing_profiles: list[SearchProfile] | None = None) -> int:
    pool = list(existing_profiles if existing_profiles is not None else new_profiles)
    return sum(1 for profile in new_profiles for existing in pool if existing.search_profile_id != profile.search_profile_id)


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


def _candidate_canonical_key(profile: SearchProfile) -> str:
    explicit = canonicalize_entity_key(getattr(profile, "canonical_key", "") or "")
    if explicit:
        return explicit
    fallback = canonicalize_entity_key(profile.normalized_key or profile.entity_name)
    if fallback:
        return fallback
    return normalize_entity_key(profile.normalized_key or profile.entity_name, strip_accents=True)


def _evidence(profile: SearchProfile) -> dict[str, Any]:
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


def _has_evidence(profile: SearchProfile) -> bool:
    evidence = _evidence(profile)
    return bool(evidence.get("claim_ids") or evidence.get("sentence_ids"))


def _type_score(new: SearchProfile, candidate: SearchProfile) -> tuple[float, str]:
    left = fold_text(new.entity_type)
    right = fold_text(candidate.entity_type)
    if not left or not right or "unknown" in {left, right}:
        return 0.0, "entity_type_unknown"
    if left == right:
        return 0.2, "entity_type_match"
    if frozenset({left, right}) in _COMPATIBLE_TYPES:
        return 0.1, "entity_type_compatible"
    return -0.1, "entity_type_mismatch"


def _name_score(new: SearchProfile, candidate: SearchProfile) -> tuple[float, str]:
    left_explicit_canonical = normalize_entity_key(getattr(new, "canonical_key", "") or "", strip_accents=True)
    right_explicit_canonical = normalize_entity_key(getattr(candidate, "canonical_key", "") or "", strip_accents=True)
    if left_explicit_canonical and right_explicit_canonical and left_explicit_canonical == right_explicit_canonical:
        return 0.46, "canonical_key_match"
    left_key = normalize_entity_key(new.normalized_key or new.entity_name, strip_accents=True)
    right_key = normalize_entity_key(candidate.normalized_key or candidate.entity_name, strip_accents=True)
    if left_key and right_key and left_key == right_key:
        return 0.4, "normalized_name_match"
    left_canonical = canonicalize_entity_key(new.normalized_key or new.entity_name)
    right_canonical = canonicalize_entity_key(candidate.normalized_key or candidate.entity_name)
    if left_canonical and right_canonical and left_canonical == right_canonical:
        return 0.42, "canonical_name_match"
    overlap = _jaccard(_tokens(left_key or new.entity_name), _tokens(right_key or candidate.entity_name))
    semantic_overlap = max(
        _jaccard(_semantic_tokens(left_key or new.entity_name), _semantic_tokens(right_key or candidate.entity_name)),
        _jaccard(_tokens(left_canonical), _tokens(right_canonical)),
    )
    if semantic_overlap > overlap:
        return min(0.38, semantic_overlap * 0.38), "canonical_name_overlap"
    if overlap <= 0:
        return 0.0, "normalized_name_no_overlap"
    return min(0.3, overlap * 0.3), "normalized_name_token_overlap"


def _overlap_score(left_values: list[str], right_values: list[str], weight: float, reason: str) -> tuple[float, str]:
    overlap = _jaccard({fold_text(v) for v in left_values if v}, {fold_text(v) for v in right_values if v})
    return min(weight, overlap * weight), reason


def _semantic_overlap_score(
    left_values: list[str],
    right_values: list[str],
    weight: float,
    reason: str,
) -> tuple[float, str]:
    left_tokens: set[str] = set()
    right_tokens: set[str] = set()
    for value in left_values:
        left_tokens.update(_semantic_tokens(value))
    for value in right_values:
        right_tokens.update(_semantic_tokens(value))
    overlap = _jaccard(left_tokens, right_tokens)
    return min(weight, overlap * weight), reason


def _time_score(new: SearchProfile, candidate: SearchProfile) -> tuple[float, str]:
    left = dict(new.time_filters or {})
    right = dict(candidate.time_filters or {})
    left_values = {fold_text(v) for v in left.get("values") or [] if v}
    right_values = {fold_text(v) for v in right.get("values") or [] if v}
    if left_values and right_values:
        return (0.05, "time_value_overlap") if left_values & right_values else (0.0, "time_value_differs")
    if left.get("dominant") and left.get("dominant") == right.get("dominant"):
        return 0.03, "time_mode_compatible"
    return 0.0, "time_unknown"


def _space_score(new: SearchProfile, candidate: SearchProfile) -> tuple[float, str]:
    left = dict(new.space_filters or {})
    right = dict(candidate.space_filters or {})
    left_values = {fold_text(v) for v in left.get("values") or [] if v}
    right_values = {fold_text(v) for v in right.get("values") or [] if v}
    if left_values and right_values:
        return (0.05, "space_value_overlap") if left_values & right_values else (0.0, "space_value_differs")
    if left.get("dominant") and left.get("dominant") == right.get("dominant"):
        return 0.03, "space_mode_compatible"
    return 0.0, "space_unknown"


class CandidateSelectionV1:
    version: str = CANDIDATE_SELECTION_BUILDER_VERSION

    def select_for_profile(
        self,
        new_profile: SearchProfile,
        existing_profiles: list[SearchProfile],
        *,
        limit: int = 5,
        candidate_source: str = "existing_memory",
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for existing in existing_profiles:
            if existing.search_profile_id == new_profile.search_profile_id:
                continue
            candidate = self._score_pair(new_profile, existing, candidate_source=candidate_source)
            if candidate is not None:
                candidates.append(candidate)
        candidates = self._dedupe_candidates(candidates)
        if not candidates and any(existing.search_profile_id != new_profile.search_profile_id for existing in existing_profiles):
            fallback_candidates: list[EntityCandidate] = []
            for existing in existing_profiles:
                if existing.search_profile_id == new_profile.search_profile_id:
                    continue
                candidate = self._score_pair(new_profile, existing, candidate_source=candidate_source, min_score=0.0)
                if candidate is not None and candidate.score > 0:
                    fallback_candidates.append(candidate)
            candidates = self._dedupe_candidates(fallback_candidates)
        candidates = self._dedupe_by_canonical_key(candidates)
        return sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]

    def select_many(
        self,
        new_profiles: list[SearchProfile],
        existing_profiles: list[SearchProfile] | None = None,
        *,
        limit_per_profile: int = 5,
    ) -> list[EntityCandidate]:
        pool = list(existing_profiles if existing_profiles is not None else new_profiles)
        candidate_source = "existing_memory" if existing_profiles is not None else "batch_fallback"
        selected: list[EntityCandidate] = []
        for profile in new_profiles:
            selected.extend(
                self.select_for_profile(
                    profile,
                    pool,
                    limit=limit_per_profile,
                    candidate_source=candidate_source,
                )
            )
        return selected

    def _score_pair(
        self,
        new_profile: SearchProfile,
        candidate_profile: SearchProfile,
        *,
        candidate_source: str,
        min_score: float = _MIN_CANDIDATE_SCORE,
    ) -> EntityCandidate | None:
        if not _has_evidence(candidate_profile):
            return None

        reasons: list[str] = []
        score = 0.0

        value, reason = _name_score(new_profile, candidate_profile)
        score += value
        _append_reason(reasons, reason, value)

        value, reason = _type_score(new_profile, candidate_profile)
        score += value
        if value < 0:
            reasons.append(f"{reason}:{value:.2f}")
        else:
            _append_reason(reasons, reason, value)

        value, reason = _overlap_score(new_profile.keywords, candidate_profile.keywords, 0.15, "keyword_overlap")
        semantic_value, semantic_reason = _semantic_overlap_score(
            new_profile.keywords,
            candidate_profile.keywords,
            0.15,
            "keyword_semantic_overlap",
        )
        if semantic_value > value:
            value, reason = semantic_value, semantic_reason
        score += value
        _append_reason(reasons, reason, value)

        value, reason = _overlap_score(
            list((new_profile.relation_filters or {}).get("predicates") or []),
            list((candidate_profile.relation_filters or {}).get("predicates") or []),
            0.1,
            "relation_predicate_overlap",
        )
        score += value
        _append_reason(reasons, reason, value)

        value, reason = _overlap_score(
            list((new_profile.relation_filters or {}).get("objects") or []),
            list((candidate_profile.relation_filters or {}).get("objects") or []),
            0.1,
            "relation_object_overlap",
        )
        semantic_value, semantic_reason = _semantic_overlap_score(
            list((new_profile.relation_filters or {}).get("objects") or []),
            list((candidate_profile.relation_filters or {}).get("objects") or []),
            0.1,
            "relation_object_semantic_overlap",
        )
        if semantic_value > value:
            value, reason = semantic_value, semantic_reason
        score += value
        _append_reason(reasons, reason, value)

        value, reason = _time_score(new_profile, candidate_profile)
        score += value
        _append_reason(reasons, reason, value)

        value, reason = _space_score(new_profile, candidate_profile)
        score += value
        _append_reason(reasons, reason, value)

        score = max(0.0, min(1.0, round(score, 4)))
        if score < min_score:
            return None

        return EntityCandidate(
            search_profile_id=new_profile.search_profile_id,
            technical_memory_chunk_id=new_profile.technical_memory_chunk_id,
            technical_entity_id=new_profile.technical_entity_id,
            local_entity_id=new_profile.local_entity_id,
            candidate_entity_id=_candidate_entity_id(candidate_profile),
            candidate_name=candidate_profile.entity_name,
            candidate_type=candidate_profile.entity_type,
            candidate_canonical_key=_candidate_canonical_key(candidate_profile),
            candidate_source=candidate_source,
            score=score,
            reasons=reasons,
            evidence=_evidence(candidate_profile),
            builder_version=self.version,
        )

    @staticmethod
    def _dedupe_candidates(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
        by_entity_id: dict[str, EntityCandidate] = {}
        for candidate in candidates:
            key = str(candidate.candidate_entity_id or "")
            if not key:
                key = f"fallback:{candidate.candidate_name}:{candidate.candidate_type}"
            current = by_entity_id.get(key)
            if current is None or float(candidate.score) > float(current.score):
                by_entity_id[key] = candidate
        return list(by_entity_id.values())

    @staticmethod
    def _dedupe_by_canonical_key(candidates: list[EntityCandidate]) -> list[EntityCandidate]:
        grouped: dict[str, list[EntityCandidate]] = {}
        passthrough: list[EntityCandidate] = []
        for candidate in candidates:
            key = str(candidate.candidate_canonical_key or "").strip()
            if not key:
                passthrough.append(candidate)
                continue
            grouped.setdefault(key, []).append(candidate)

        selected: list[EntityCandidate] = list(passthrough)
        for canonical_key, group in grouped.items():
            best = max(group, key=lambda item: float(item.score))
            if len(group) == 1:
                selected.append(best)
                continue
            selected.append(
                replace(
                    best,
                    best_candidate_selected=True,
                    merge_candidate_group={
                        "canonical_key": canonical_key,
                        "group_size": len(group),
                        "duplicate_memory_profile_count": len(group) - 1,
                        "candidate_entity_ids": [item.candidate_entity_id for item in group],
                        "candidate_names": [item.candidate_name for item in group],
                        "selected_candidate_entity_id": best.candidate_entity_id,
                    },
                )
            )
        return selected


__all__ = ["CandidateSelectionV1", "candidate_selection_attempt_count"]
