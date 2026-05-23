from __future__ import annotations

from apps.knowledge.domain.tension_analysis import TENSION_ENGINE_VERSION, TensionAnalysis
from apps.knowledge.domain.similarity_analysis import SimilarityAnalysis
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.entity_key_normalization import normalize_entity_key
from apps.knowledge.service.language_rules import fold_text


_COMPATIBLE_TYPES = {
    frozenset({"software", "module"}),
    frozenset({"software", "system"}),
    frozenset({"module", "system"}),
}

_CONTRADICTION_PAIRS = {
    frozenset({fold_text("active"), fold_text("inactive")}),
    frozenset({fold_text("aktív"), fold_text("inaktív")}),
    frozenset({fold_text("activo"), fold_text("inactivo")}),
    frozenset({fold_text("activa"), fold_text("inactiva")}),
    frozenset({fold_text("enabled"), fold_text("disabled")}),
    frozenset({fold_text("required"), fold_text("not required")}),
    frozenset({fold_text("kötelező"), fold_text("nem kötelező")}),
    frozenset({fold_text("uses"), fold_text("does not use")}),
    frozenset({fold_text("uses"), fold_text("not uses")}),
    frozenset({fold_text("használ"), fold_text("nem használ")}),
    frozenset({fold_text("használja"), fold_text("nem használja")}),
}
_STATE_TOKENS = {
    fold_text("active"),
    fold_text("inactive"),
    fold_text("aktív"),
    fold_text("inaktív"),
    fold_text("activo"),
    fold_text("activa"),
    fold_text("inactivo"),
    fold_text("inactiva"),
    fold_text("enabled"),
    fold_text("disabled"),
}
_CURRENT_TIME_TOKENS = {fold_text(item) for item in ("current", "currently", "jelenleg", "most", "actualmente")}
_USE_PREDICATE_TOKENS = {fold_text(item) for item in ("uses", "use", "használ", "használja", "utiliza", "usa")}
_PREDICATE_CLASSES = {
    "uses": "uses_or_integrates",
    "use": "uses_or_integrates",
    "hasznal": "uses_or_integrates",
    "használ": "uses_or_integrates",
    "hasznalja": "uses_or_integrates",
    "használja": "uses_or_integrates",
    "utiliza": "uses_or_integrates",
    "usa": "uses_or_integrates",
    "integrates": "uses_or_integrates",
    "integrates with": "uses_or_integrates",
    "active": "state",
    "inactive": "state",
    "closed": "state",
    "responsible": "ownership",
    "owns": "ownership",
}
_EXCLUSIVE_OBJECT_GROUPS = (
    {fold_text("stripe"), fold_text("manual"), fold_text("manual invoicing")},
)


def _norm_key(profile: SearchProfile) -> str:
    return normalize_entity_key(profile.normalized_key or profile.entity_name, strip_accents=True)


def _split_folded_words(value: str) -> set[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in fold_text(value))
    return {part for part in cleaned.split() if part}


def _fold_tokens(values: list[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        folded = fold_text(str(value or "")).strip()
        if folded:
            tokens.add(folded)
            tokens.update(_split_folded_words(folded))
    return tokens


def _semantic_predicate(value: str) -> str:
    folded = fold_text(str(value or "")).strip()
    return _PREDICATE_CLASSES.get(folded, folded)


def _claim_subject(claim: dict[str, object], fallback: str = "") -> str:
    return normalize_entity_key(str(claim.get("subject") or claim.get("subject_text") or fallback), strip_accents=True)


def _claim_predicate(claim: dict[str, object]) -> str:
    predicates = claim.get("predicates")
    if isinstance(predicates, list) and predicates:
        return str(predicates[0] or "")
    return str(claim.get("predicate") or claim.get("predicate_text") or "")


def _claim_object(claim: dict[str, object]) -> str:
    objects = claim.get("objects")
    if isinstance(objects, list) and objects:
        return normalize_entity_key(str(objects[0] or ""), strip_accents=True)
    return normalize_entity_key(str(claim.get("object") or claim.get("object_text") or ""), strip_accents=True)


def _claim_time_values(claim: dict[str, object]) -> set[str]:
    values = claim.get("time_values")
    if isinstance(values, list):
        return {fold_text(str(value or "")) for value in values if value}
    value = str(claim.get("time_value") or "").strip()
    return {fold_text(value)} if value else set()


def _claim_time_mode(claim: dict[str, object]) -> str:
    return fold_text(str(claim.get("time_dominant") or claim.get("time_mode") or "current"))


def _same_claim_time(left: dict[str, object], right: dict[str, object]) -> bool:
    left_values = _claim_time_values(left)
    right_values = _claim_time_values(right)
    if left_values or right_values:
        return left_values == right_values
    return _claim_time_mode(left) == _claim_time_mode(right)


def _different_claim_time(left: dict[str, object], right: dict[str, object]) -> bool:
    left_values = _claim_time_values(left)
    right_values = _claim_time_values(right)
    if left_values and right_values:
        return left_values != right_values
    return _claim_time_mode(left) != _claim_time_mode(right)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _types_compatible(type_a: str, type_b: str) -> bool:
    folded_a = fold_text(type_a)
    folded_b = fold_text(type_b)
    return bool(folded_a and folded_b and (folded_a == folded_b or frozenset({folded_a, folded_b}) in _COMPATIBLE_TYPES))


def _has_contradiction(predicates_a: list[str], predicates_b: list[str]) -> bool:
    folded_a = {fold_text(str(value or "")).strip() for value in predicates_a if value}
    folded_b = {fold_text(str(value or "")).strip() for value in predicates_b if value}
    for left in folded_a:
        for right in folded_b:
            if left != right and frozenset({left, right}) in _CONTRADICTION_PAIRS:
                return True
    return False


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


def _extract_evidence(profile: SearchProfile) -> dict[str, list[str]]:
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


def _has_evidence(evidence_a: dict[str, list[str]], evidence_b: dict[str, list[str]]) -> bool:
    return bool(
        evidence_a.get("claim_ids")
        or evidence_a.get("sentence_ids")
        or evidence_b.get("claim_ids")
        or evidence_b.get("sentence_ids")
    )


def _time_values(profile: SearchProfile) -> list[str]:
    filters = dict(profile.time_filters or {})
    return [str(value) for value in filters.get("values") or [] if value]


def _relation_predicates(profile: SearchProfile) -> list[str]:
    filters = dict(profile.relation_filters or {})
    return [str(value) for value in filters.get("predicates") or [] if value]


def _relation_objects(profile: SearchProfile) -> list[str]:
    filters = dict(profile.relation_filters or {})
    return [str(value) for value in filters.get("objects") or [] if value]


def _state_values(profile: SearchProfile) -> set[str]:
    tokens = _fold_tokens([profile.canonical_text or "", profile.search_text or "", *profile.keywords, *_relation_predicates(profile)])
    return {token for token in tokens if token in _STATE_TOKENS}


def _is_current(profile: SearchProfile) -> bool:
    filters = dict(profile.time_filters or {})
    values = {fold_text(str(value)) for value in filters.get("values") or [] if value}
    return bool(filters.get("has_current") or filters.get("dominant") == "current" or values & _CURRENT_TIME_TOKENS)


def _is_historical(profile: SearchProfile) -> bool:
    filters = dict(profile.time_filters or {})
    return bool(filters.get("has_historical") or filters.get("dominant") in {"historical", "bounded"})


def _same_time_context(profile_a: SearchProfile, profile_b: SearchProfile) -> bool:
    values_a = {fold_text(value) for value in _time_values(profile_a)}
    values_b = {fold_text(value) for value in _time_values(profile_b)}
    if values_a or values_b:
        return values_a == values_b
    return _is_current(profile_a) == _is_current(profile_b)


def _different_time_context(profile_a: SearchProfile, profile_b: SearchProfile) -> bool:
    values_a = {fold_text(value) for value in _time_values(profile_a)}
    values_b = {fold_text(value) for value in _time_values(profile_b)}
    if values_a and values_b and values_a != values_b:
        return True
    return _is_current(profile_a) != _is_current(profile_b) or _is_historical(profile_a) != _is_historical(profile_b)


def _has_use_predicate(profile: SearchProfile) -> bool:
    return bool(_fold_tokens(_relation_predicates(profile)) & _USE_PREDICATE_TOKENS)


def _exclusive_object_conflict(profile_a: SearchProfile, profile_b: SearchProfile) -> bool:
    objects_a = _fold_tokens(_relation_objects(profile_a))
    objects_b = _fold_tokens(_relation_objects(profile_b))
    for group in _EXCLUSIVE_OBJECT_GROUPS:
        if objects_a & group and objects_b & group and not (objects_a & objects_b & group):
            return True
    return False


def _band(score: float) -> str:
    if score <= 0:
        return "none"
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _conflict_type_for_tension(tension_type: str, reasons: list[str]) -> str:
    normalized = fold_text(tension_type)
    reason_text = " ".join(reasons)
    if normalized in {"contradiction", "hard_conflict"}:
        return "direct_contradiction"
    if normalized == "temporal_change":
        return "temporal_change"
    if normalized == "soft_conflict":
        return "refinement"
    if "source_disagreement" in reason_text:
        return "source_disagreement"
    if "scope_difference" in reason_text:
        return "scope_difference"
    return "unknown"


class TensionEngineV1:
    version: str = TENSION_ENGINE_VERSION

    def analyze(
        self,
        profile_a: SearchProfile,
        profile_b: SearchProfile,
        *,
        similarity: SimilarityAnalysis | None = None,
    ) -> TensionAnalysis:
        key_a = _norm_key(profile_a)
        key_b = _norm_key(profile_b)
        type_compatible = _types_compatible(profile_a.entity_type, profile_b.entity_type)
        evidence_a = _extract_evidence(profile_a)
        evidence_b = _extract_evidence(profile_b)
        has_evidence = _has_evidence(evidence_a, evidence_b)

        if fold_text(profile_a.entity_type) == "location" and key_a != key_b:
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="unrelated",
                tension_score=0.0,
                tension_reasons=["unrelated:different_location_name"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
            )

        if key_a != key_b and not type_compatible:
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="unrelated",
                tension_score=0.0,
                tension_reasons=["unrelated:name_and_type_differ"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
            )

        keyword_overlap = _jaccard(_fold_tokens(profile_a.keywords), _fold_tokens(profile_b.keywords))
        state_a = _state_values(profile_a)
        state_b = _state_values(profile_b)
        if key_a == key_b and state_a and state_b and any(frozenset({left, right}) in _CONTRADICTION_PAIRS for left in state_a for right in state_b):
            if _different_time_context(profile_a, profile_b):
                return self._analysis(
                    profile_a,
                    profile_b,
                    tension_type="temporal_change",
                    tension_score=0.25,
                    tension_reasons=["temporal_change:opposite_state_different_time_context"],
                    evidence_a=evidence_a,
                    evidence_b=evidence_b,
                )
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="contradiction",
                tension_score=0.9 if has_evidence else 0.69,
                tension_reasons=["contradiction:opposite_state_same_current_time"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
                conflicting_claim_ids=[*evidence_a["claim_ids"], *evidence_b["claim_ids"]] if has_evidence else [],
            )

        if (similarity is not None and similarity.total_similarity_score >= 0.85 and keyword_overlap >= 0.8) or (
            key_a == key_b and keyword_overlap >= 0.8 and not state_a and not state_b
        ):
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="duplicate",
                tension_score=0.1,
                tension_reasons=[f"duplicate:high_similarity_or_keyword_overlap:{keyword_overlap:.2f}"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
            )

        if key_a == key_b and _different_time_context(profile_a, profile_b):
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="temporal_change",
                tension_score=0.2,
                tension_reasons=["temporal_change:different_time_values"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
            )

        if _has_contradiction(_relation_predicates(profile_a), _relation_predicates(profile_b)):
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="contradiction",
                tension_score=0.9 if has_evidence else 0.69,
                tension_reasons=["contradiction:opposite_predicates_same_time_context"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
                conflicting_claim_ids=[*evidence_a["claim_ids"], *evidence_b["claim_ids"]] if has_evidence else [],
            )

        if key_a == key_b and _has_use_predicate(profile_a) and _has_use_predicate(profile_b) and _same_time_context(profile_a, profile_b) and _exclusive_object_conflict(profile_a, profile_b):
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="contradiction",
                tension_score=0.65 if has_evidence else 0.39,
                tension_reasons=["contradiction:exclusive_descriptor_object_same_current_time"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
                conflicting_claim_ids=[*evidence_a["claim_ids"], *evidence_b["claim_ids"]] if has_evidence else [],
            )

        name_overlap = _jaccard(_fold_tokens([key_a]), _fold_tokens([key_b]))
        if key_a == key_b or name_overlap >= 0.5:
            return self._analysis(
                profile_a,
                profile_b,
                tension_type="additive",
                tension_score=0.05,
                tension_reasons=[f"additive:same_or_similar_entity_no_contradiction:{name_overlap:.2f}"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
            )

        return self._analysis(
            profile_a,
            profile_b,
            tension_type="uncertain",
            tension_score=0.3,
            tension_reasons=["uncertain:related_type_without_clear_tension"],
            evidence_a=evidence_a,
            evidence_b=evidence_b,
        )

    def analyze_many(
        self,
        new_profiles: list[SearchProfile],
        similarity_analyses: list[SimilarityAnalysis],
        candidate_profiles: list[SearchProfile],
    ) -> list[TensionAnalysis]:
        new_by_profile_id = {str(profile.search_profile_id): profile for profile in new_profiles}
        candidates_by_entity_id = {_candidate_entity_id(profile): profile for profile in candidate_profiles}
        analyses: list[TensionAnalysis] = []
        for similarity in similarity_analyses:
            left = new_by_profile_id.get(str(similarity.search_profile_id))
            right = candidates_by_entity_id.get(str(similarity.candidate_entity_id))
            if left is None or right is None:
                continue
            analyses.append(self.analyze(left, right, similarity=similarity))
        return analyses

    def analyze_global_profiles(self, global_profiles: list[dict[str, object]]) -> list[TensionAnalysis]:
        analyses: list[TensionAnalysis] = []
        for profile in global_profiles:
            if str(profile.get("operation") or "") != "update":
                if str(profile.get("operation") or "") != "review":
                    continue
            claims = [dict(item) for item in profile.get("claims") or [] if isinstance(item, dict)]
            new_claim_ids = {str(item or "") for item in profile.get("new_claim_ids") or [] if item}
            if not claims:
                continue
            seen_pairs: set[tuple[str, str, str]] = set()
            for index, left in enumerate(claims):
                left_id = str(left.get("claim_id") or "")
                for right in claims[index + 1 :]:
                    right_id = str(right.get("claim_id") or "")
                    if new_claim_ids and left_id not in new_claim_ids and right_id not in new_claim_ids:
                        # Historical profile conflicts should remain visible on review chunks,
                        # but update noise is bounded by requiring at least one new claim.
                        if str(profile.get("operation") or "") == "update":
                            continue
                    incoming, existing = (right, left) if right_id in new_claim_ids and left_id not in new_claim_ids else (left, right)
                    incoming_id = str(incoming.get("claim_id") or "")
                    existing_id = str(existing.get("claim_id") or "")
                    analysis = self._analyze_claim_pair(profile, incoming, existing)
                    if not analysis.tension_detected:
                        continue
                    pair_key = tuple(sorted((incoming_id, existing_id))) + (analysis.tension_type,)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    analyses.append(analysis)
        return analyses

    def _analyze_claim_pair(
        self,
        profile: dict[str, object],
        incoming: dict[str, object],
        existing: dict[str, object],
    ) -> TensionAnalysis:
        profile_name = str(profile.get("entity_name") or profile.get("canonical_key") or "")
        subject_new = _claim_subject(incoming, profile_name)
        subject_existing = _claim_subject(existing, profile_name)
        predicate_new = _claim_predicate(incoming)
        predicate_existing = _claim_predicate(existing)
        predicate_new_folded = fold_text(predicate_new)
        predicate_existing_folded = fold_text(predicate_existing)
        object_new = _claim_object(incoming)
        object_existing = _claim_object(existing)
        claim_ids = [str(existing.get("claim_id") or ""), str(incoming.get("claim_id") or "")]
        claim_ids = [claim_id for claim_id in claim_ids if claim_id]
        evidence = {
            "claim_ids": claim_ids,
            "sentence_ids": [
                *[str(value) for value in existing.get("sentence_ids") or [] if value],
                *[str(value) for value in incoming.get("sentence_ids") or [] if value],
            ],
            "profile_id": profile.get("profile_id"),
        }

        if (
            subject_new
            and subject_existing
            and subject_new == subject_existing
            and predicate_new_folded
            and predicate_new_folded == predicate_existing_folded
            and object_new
            and object_existing
            and object_new != object_existing
            and _same_claim_time(incoming, existing)
        ):
            return self._claim_analysis(
                profile,
                "hard_conflict",
                0.9,
                "hard_conflict:same_subject_predicate_different_object_same_time",
                claim_ids,
                evidence,
            )

        if subject_new and subject_existing and subject_new == subject_existing and _different_claim_time(incoming, existing):
            return self._claim_analysis(
                profile,
                "temporal_change",
                0.45,
                "temporal_change:same_subject_different_time_frame",
                claim_ids,
                evidence,
            )

        new_class = _semantic_predicate(predicate_new)
        existing_class = _semantic_predicate(predicate_existing)
        if (
            subject_new
            and subject_existing
            and subject_new == subject_existing
            and predicate_new_folded
            and predicate_existing_folded
            and predicate_new_folded != predicate_existing_folded
            and new_class
            and new_class == existing_class
        ):
            return self._claim_analysis(
                profile,
                "soft_conflict",
                0.55,
                "soft_conflict:semantically_related_predicates",
                claim_ids,
                evidence,
            )

        return self._claim_analysis(profile, "none", 0.0, "none:no_structured_tension", [], evidence)

    def _claim_analysis(
        self,
        profile: dict[str, object],
        tension_type: str,
        tension_score: float,
        reason: str,
        conflicting_claim_ids: list[str],
        evidence: dict[str, object],
    ) -> TensionAnalysis:
        clean_score = round(max(0.0, min(1.0, tension_score)), 4)
        return TensionAnalysis(
            candidate_name_a=str(profile.get("entity_name") or ""),
            candidate_name_b=str(profile.get("entity_name") or ""),
            tension_detected=clean_score > 0,
            tension_score=clean_score,
            tension_band=_band(clean_score),
            tension_type=tension_type,
            conflict_type=_conflict_type_for_tension(tension_type, [reason]),
            tension_reason=reason,
            tension_reasons=[reason],
            conflicting_claim_ids=conflicting_claim_ids,
            evidence=evidence,
            builder_version=self.version,
        )

    def _analysis(
        self,
        profile_a: SearchProfile,
        profile_b: SearchProfile,
        *,
        tension_type: str,
        tension_score: float,
        tension_reasons: list[str],
        evidence_a: dict[str, list[str]],
        evidence_b: dict[str, list[str]],
        conflicting_claim_ids: list[str] | None = None,
    ) -> TensionAnalysis:
        clean_score = round(max(0.0, min(1.0, tension_score)), 4)
        reasons = [reason for reason in tension_reasons if reason]
        return TensionAnalysis(
            search_profile_id_a=profile_a.search_profile_id,
            search_profile_id_b=profile_b.search_profile_id,
            technical_entity_id_a=profile_a.technical_entity_id,
            technical_entity_id_b=profile_b.technical_entity_id,
            candidate_name_a=profile_a.entity_name,
            candidate_name_b=profile_b.entity_name,
            tension_detected=clean_score > 0,
            tension_score=clean_score,
            tension_band=_band(clean_score),
            tension_type=tension_type,
            conflict_type=_conflict_type_for_tension(tension_type, reasons),
            tension_reason=reasons[0] if reasons else "",
            tension_reasons=reasons,
            conflicting_claim_ids=conflicting_claim_ids or [],
            evidence={
                "claim_ids": [*evidence_a.get("claim_ids", []), *evidence_b.get("claim_ids", [])],
                "sentence_ids": [*evidence_a.get("sentence_ids", []), *evidence_b.get("sentence_ids", [])],
                "claim_ids_a": list(evidence_a.get("claim_ids", [])),
                "claim_ids_b": list(evidence_b.get("claim_ids", [])),
                "sentence_ids_a": list(evidence_a.get("sentence_ids", [])),
                "sentence_ids_b": list(evidence_b.get("sentence_ids", [])),
            },
            builder_version=self.version,
        )


__all__ = ["TensionEngineV1"]
