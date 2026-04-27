from __future__ import annotations

import re
from typing import Any

from apps.knowledge.domain.decision_analysis import DecisionAnalysis
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key, normalize_entity_key


GLOBAL_PROFILE_BUILDER_VERSION = "global_profile_builder_v0"


def _global_profile_id(value: str) -> str:
    cleaned = normalize_entity_key(value, strip_accents=True).replace(" ", "-")
    return f"global-profile:{cleaned or 'unknown'}"


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


def _canonical_key(profile: SearchProfile | None, fallback: str = "") -> str:
    if profile is None:
        return canonicalize_entity_key(fallback) or normalize_entity_key(fallback, strip_accents=True)
    return (
        canonicalize_entity_key(profile.canonical_key or "")
        or canonicalize_entity_key(profile.normalized_key or profile.entity_name)
        or normalize_entity_key(profile.normalized_key or profile.entity_name, strip_accents=True)
    )


def _profile_evidence(profile: SearchProfile | None) -> dict[str, Any]:
    if profile is None:
        return {}
    claim_ids: list[str] = []
    sentence_ids: list[str] = []
    source_ids: list[str] = []
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
        for value in [ref.get("source_id"), *(ref.get("source_ids") or [])]:
            text = str(value or "").strip()
            if text and text not in source_ids:
                source_ids.append(text)
    out: dict[str, Any] = {"claim_ids": claim_ids, "sentence_ids": sentence_ids}
    if source_ids:
        out["source_ids"] = source_ids
        out["source_id"] = source_ids[0]
    return out


def _evidence(decision: DecisionAnalysis, profile: SearchProfile | None) -> dict[str, Any]:
    evidence = _profile_evidence(profile)
    if evidence.get("claim_ids") or evidence.get("sentence_ids"):
        return evidence
    return dict(decision.evidence or {})


def _claim_status(profile: SearchProfile | None) -> str:
    filters = dict(getattr(profile, "time_filters", None) or {})
    if filters.get("has_historical") or filters.get("dominant") in {"historical", "bounded"}:
        return "historical"
    return "active"


def _first_value(values: list[str], index: int) -> str:
    if index < len(values):
        return values[index]
    return values[-1] if values else ""


def _state_fact_rows(profile: SearchProfile, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    text = f"{profile.canonical_text} | {profile.search_text}"
    claim_ids = [str(item) for item in evidence.get("claim_ids") or [] if item]
    sentence_ids = [str(item) for item in evidence.get("sentence_ids") or [] if item]
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_fact(*, state: str, time_mode: str, time_value: str, predicate: str) -> None:
        key = (state, time_mode, time_value)
        if key in seen:
            return
        seen.add(key)
        facts.append(
            {
                "state": state,
                "time_mode": time_mode,
                "time_value": time_value,
                "predicate": predicate,
            }
        )

    for match in re.finditer(r"\bis currently\s+(active|inactive)\b", text, flags=re.IGNORECASE):
        state = match.group(1).lower()
        add_fact(state=state, time_mode="current", time_value="currently", predicate=f"is currently {state}")
    for match in re.finditer(
        r"\bwas\s+(active|inactive)\b(?:\s*(?:→|->)?\s*(?:in\s+)?)?((?:19|20|21)\d{2})?",
        text,
        flags=re.IGNORECASE,
    ):
        state = match.group(1).lower()
        year = str(match.group(2) or "").strip()
        add_fact(state=state, time_mode="bounded", time_value=year, predicate=f"was {state}")

    if not facts:
        return []

    rows: list[dict[str, Any]] = []
    for index, fact in enumerate(facts):
        claim_id = _first_value(claim_ids, index)
        if not claim_id:
            continue
        time_value = str(fact["time_value"] or "").strip()
        rows.append(
            {
                "claim_id": claim_id,
                "subject": profile.entity_name,
                "predicate": "active",
                "predicate_text": fact["predicate"],
                "predicates": ["active"],
                "object": "false" if fact["state"] == "inactive" else "true",
                "objects": ["false" if fact["state"] == "inactive" else "true"],
                "time_dominant": fact["time_mode"],
                "time_mode": fact["time_mode"],
                "time_values": [time_value] if time_value else [],
                "status": "historical" if fact["time_mode"] in {"bounded", "historical"} else "active",
                "sentence_ids": [_first_value(sentence_ids, index)] if _first_value(sentence_ids, index) else sentence_ids,
                "evidence": dict(evidence),
            }
        )
    return rows


def _rule_fact_rows(profile: SearchProfile, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    text = f"{profile.canonical_text} | {profile.search_text}"
    match = re.search(
        r"\b(must|should|required|kötelező|kell|debe)\b\s*(?:→|->|:)?\s*([^.|;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    predicate = match.group(1).strip()
    obj = match.group(2).strip()
    claim_ids = [str(item) for item in evidence.get("claim_ids") or [] if item]
    sentence_ids = [str(item) for item in evidence.get("sentence_ids") or [] if item]
    if not claim_ids:
        return []
    claim_text = " ".join(part for part in [profile.entity_name, predicate, obj] if part).strip()
    return [
        {
            "claim_id": claim_ids[0],
            "subject": profile.entity_name,
            "claim_text": claim_text,
            "predicate": predicate,
            "predicate_text": predicate,
            "predicates": [predicate],
            "object": obj,
            "object_text": obj,
            "objects": [obj],
            "claim_type": "rule_procedure",
            "claim_group": "rule",
            "time_dominant": "timeless",
            "time_mode": "timeless",
            "time_values": [],
            "status": "active",
            "sentence_ids": sentence_ids,
            "evidence": dict(evidence),
        }
    ]


def _dominant_claim_group(profile: SearchProfile) -> str:
    signals = {str(key): int(value or 0) for key, value in (profile.claim_group_signals or {}).items()}
    for group in ("relation", "rule", "state", "event", "descriptor"):
        if signals.get(group, 0) > 0:
            return group
    return "other"


def _claim_type_for_group(group: str) -> str:
    return {
        "descriptor": "stable_descriptor",
        "event": "event",
        "relation": "relation",
        "rule": "rule_procedure",
        "state": "state",
    }.get(group, "other")


def _fact_pair_from_profile(profile: SearchProfile, group: str) -> tuple[str, str]:
    text = f"{profile.canonical_text} | {profile.search_text}"
    if group == "event":
        match = re.search(
            r"\b(was\s+(?:created|updated|completed|deprecated|replaced|migrated)|created|updated|completed|deprecated|replaced|migrated)\b\s*((?:on|in)\s+[^.|;]+)?",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            predicate = match.group(1).strip()
            if predicate in {"created", "updated", "completed", "deprecated", "replaced", "migrated"}:
                predicate = f"was {predicate}"
            obj = (match.group(2) or "").strip()
            return predicate, obj
    if group == "descriptor":
        match = re.search(
            r"\b(is\s+the\s+compliance\s+lead\s+at|is\s+compliance\s+lead\s+at)\b\s*(?:→|->|:)?\s*([^.|;]+)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip(), match.group(2).strip()
        match = re.search(
            r"\b(applies\s+to|apply\s+to|has|contains|supports|includes|is(?:\s+the)?|uses|use)\b\s*(?:→|->|:)?\s*([^.|;]+)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return "", ""


def _claim_rows(profile: SearchProfile | None, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    if profile is None:
        return []
    state_rows = _state_fact_rows(profile, evidence)
    if state_rows:
        return state_rows
    rule_rows = _rule_fact_rows(profile, evidence)
    if rule_rows:
        return rule_rows
    status = _claim_status(profile)
    sentence_ids = [str(item) for item in evidence.get("sentence_ids") or [] if item]
    claim_group = _dominant_claim_group(profile)
    predicates = [str(item) for item in (profile.relation_filters or {}).get("predicates") or [] if item]
    objects = [str(item) for item in (profile.relation_filters or {}).get("objects") or [] if item]
    if not predicates or not objects:
        text = f"{profile.canonical_text} | {profile.search_text}"
        match = re.search(r"\b(uses|use|haszn[aá]l(?:ja)?|utiliza|usa|integrates with)\b\s*(?:→|->|:)?\s*([^.|]+)", text, flags=re.IGNORECASE)
        if match:
            if not predicates:
                predicates = [match.group(1).strip()]
            if not objects:
                objects = [match.group(2).strip()]
    if (not predicates or not objects) and claim_group in {"descriptor", "event"}:
        predicate, obj = _fact_pair_from_profile(profile, claim_group)
        if predicate and not predicates:
            predicates = [predicate]
        if obj and not objects:
            objects = [obj]
    state_text = f"{profile.canonical_text} | {profile.search_text}".lower()
    if not predicates and any(token in state_text for token in ("active", "inactive", "aktív", "inaktív", "activo", "inactivo")):
        predicates = ["active"]
        objects = ["false"] if any(token in state_text for token in ("inactive", "inaktív", "inaktiv", "inactivo")) else ["true"]
    time_filters = dict(profile.time_filters or {})
    time_values = [str(item) for item in time_filters.get("values") or [] if item]
    rows: list[dict[str, Any]] = []
    for claim_id in evidence.get("claim_ids") or []:
        text = str(claim_id or "").strip()
        if not text:
            continue
        claim_text = " ".join(part for part in [profile.entity_name, predicates[0] if predicates else "", objects[0] if objects else ""] if part).strip()
        time_dominant = str(time_filters.get("dominant") or "current")
        if claim_group == "event":
            time_dominant = "event"
            status = "historical"
        rows.append(
            {
                "claim_id": text,
                "subject": profile.entity_name,
                "claim_text": claim_text,
                "predicate": predicates[0] if predicates else "",
                "predicate_text": predicates[0] if predicates else "",
                "predicates": predicates,
                "object": objects[0] if objects else "",
                "object_text": objects[0] if objects else "",
                "objects": objects,
                "claim_type": _claim_type_for_group(claim_group),
                "claim_group": claim_group,
                "time_dominant": time_dominant,
                "time_mode": time_dominant,
                "time_values": time_values,
                "status": status,
                "sentence_ids": sentence_ids,
                "evidence": dict(evidence),
            }
        )
    return rows


def _merge_evidence(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("claim_ids", "sentence_ids", "source_ids"):
        values: list[str] = []
        for source in (left, right):
            for value in source.get(key) or []:
                text = str(value or "").strip()
                if text and text not in values:
                    values.append(text)
        if values or key in {"claim_ids", "sentence_ids"}:
            out[key] = values
    source_id = left.get("source_id") or right.get("source_id") or (out.get("source_ids") or [None])[0]
    if source_id:
        out["source_id"] = source_id
    return out


def _merge_claims(existing_claims: list[dict[str, Any]], incoming_claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    merged: list[dict[str, Any]] = [dict(item) for item in existing_claims if isinstance(item, dict)]
    existing_ids = {str(item.get("claim_id") or "") for item in merged}
    added = 0
    deduped = 0
    for claim in incoming_claims:
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id:
            continue
        if claim_id in existing_ids:
            deduped += 1
            continue
        merged.append(dict(claim))
        existing_ids.add(claim_id)
        added += 1
    return merged, added, deduped


def _claim_subject_key(claim: dict[str, Any], fallback: str) -> str:
    subject = str(claim.get("subject") or claim.get("entity_name") or fallback or "").strip()
    return canonicalize_entity_key(subject) or normalize_entity_key(subject, strip_accents=True)


def _claim_subject_name(claim: dict[str, Any], fallback: str) -> str:
    return str(claim.get("subject") or claim.get("entity_name") or fallback or "").strip()


def _profile_merge_key(profile: dict[str, Any]) -> tuple[str, str]:
    key = canonicalize_entity_key(str(profile.get("canonical_key") or profile.get("entity_name") or ""))
    if not key:
        key = normalize_entity_key(str(profile.get("entity_name") or ""), strip_accents=True)
    entity_type = normalize_entity_key(str(profile.get("entity_type") or "unknown"), strip_accents=True)
    return key, entity_type


def _claim_signature(claim: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        normalize_entity_key(str(claim.get("subject") or ""), strip_accents=True),
        normalize_entity_key(str(claim.get("predicate") or claim.get("predicate_text") or ""), strip_accents=True),
        normalize_entity_key(str(claim.get("object") or claim.get("object_text") or ""), strip_accents=True),
        "|".join(str(item) for item in claim.get("time_values") or [] if item),
    )


def _merge_claims_by_identity(existing_claims: list[dict[str, Any]], incoming_claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    merged = [dict(item) for item in existing_claims if isinstance(item, dict)]
    seen_ids = {str(item.get("claim_id") or "") for item in merged if str(item.get("claim_id") or "")}
    seen_signatures = {_claim_signature(item) for item in merged}
    deduped = 0
    for claim in incoming_claims:
        claim_id = str(claim.get("claim_id") or "")
        signature = _claim_signature(claim)
        if (claim_id and claim_id in seen_ids) or signature in seen_signatures:
            deduped += 1
            continue
        merged.append(dict(claim))
        if claim_id:
            seen_ids.add(claim_id)
        seen_signatures.add(signature)
    return merged, deduped


def _evidence_from_claims(claims: list[dict[str, Any]]) -> dict[str, Any]:
    evidence: dict[str, Any] = {"claim_ids": [], "sentence_ids": []}
    source_ids: list[str] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "").strip()
        if claim_id and claim_id not in evidence["claim_ids"]:
            evidence["claim_ids"].append(claim_id)
        claim_evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
        for value in [*(claim.get("sentence_ids") or []), *(claim_evidence.get("sentence_ids") or [])]:
            text = str(value or "").strip()
            if text and text not in evidence["sentence_ids"]:
                evidence["sentence_ids"].append(text)
        for value in [claim.get("source_id"), *(claim.get("source_ids") or []), claim_evidence.get("source_id"), *(claim_evidence.get("source_ids") or [])]:
            text = str(value or "").strip()
            if text and text not in source_ids:
                source_ids.append(text)
    if source_ids:
        evidence["source_ids"] = source_ids
        evidence["source_id"] = source_ids[0]
    return evidence


def _profile_has_high_internal_tension(profile: dict[str, Any]) -> bool:
    for item in profile.get("tension_analyses") or []:
        if not isinstance(item, dict):
            continue
        score = float(item.get("tension_score") or 0.0)
        if score >= 0.7 and item.get("tension_type") in {"hard_conflict", "contradiction"}:
            return True
    return False


def _split_profile_if_needed(profile: dict[str, Any]) -> list[dict[str, Any]]:
    claims = [dict(item) for item in profile.get("claims") or [] if isinstance(item, dict)]
    if len(claims) < 2:
        return [profile]
    fallback_name = str(profile.get("entity_name") or profile.get("canonical_key") or "").strip()
    groups: dict[str, list[dict[str, Any]]] = {}
    group_names: dict[str, str] = {}
    for claim in claims:
        key = _claim_subject_key(claim, fallback_name)
        if not key:
            key = _profile_merge_key(profile)[0]
        groups.setdefault(key, []).append(claim)
        group_names.setdefault(key, _claim_subject_name(claim, fallback_name))
    if len(groups) <= 1:
        return [profile]
    if not (_profile_has_high_internal_tension(profile) or len(groups) > 1):
        return [profile]
    rows: list[dict[str, Any]] = []
    primary_key = _profile_merge_key(profile)[0]
    ordered_keys = sorted(groups.keys(), key=lambda key: (key != primary_key, key))
    source_profile_id = str(profile.get("profile_id") or "")
    for index, key in enumerate(ordered_keys):
        claims_for_group = groups[key]
        evidence = _evidence_from_claims(claims_for_group)
        profile_id = source_profile_id if index == 0 else _global_profile_id(key)
        row = {
            **profile,
            "profile_id": profile_id,
            "entity_name": group_names.get(key) or profile.get("entity_name"),
            "canonical_key": key,
            "claims": claims_for_group,
            "evidence": evidence,
            "new_claim_ids": [claim["claim_id"] for claim in claims_for_group if claim.get("claim_id")],
            "operation": profile.get("operation") if index == 0 else "split_create",
            "profile_split": True,
            "split_source_profile_id": source_profile_id or None,
            "split_group_key": key,
            "profile_update_reason": "split_profile:multiple_entity_signals",
        }
        row["claim_added_count"] = len(claims_for_group)
        row["claim_deduplicated_count"] = 0
        rows.append(row)
    return rows


def _merge_duplicate_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    for profile in profiles:
        key = _profile_merge_key(profile)
        if not key[0]:
            out.append(profile)
            continue
        existing = merged_by_key.get(key)
        if existing is None:
            merged_by_key[key] = profile
            out.append(profile)
            continue
        previous_count = len(existing.get("claims") or [])
        claims, deduped = _merge_claims_by_identity(list(existing.get("claims") or []), list(profile.get("claims") or []))
        existing["claims"] = claims
        existing["evidence"] = _merge_evidence(dict(existing.get("evidence") or {}), _evidence_from_claims(list(profile.get("claims") or [])))
        existing["claim_added_count"] = int(existing.get("claim_added_count") or 0) + max(0, len(claims) - previous_count)
        existing["claim_deduplicated_count"] = int(existing.get("claim_deduplicated_count") or 0) + deduped
        affected = [str(item) for item in existing.get("affected_profile_ids") or [] if item]
        profile_id = str(profile.get("profile_id") or "")
        if profile_id and profile_id not in affected:
            affected.append(profile_id)
        existing["affected_profile_ids"] = affected
        existing["profile_merged"] = True
        existing["merged_profile_ids"] = [*existing.get("merged_profile_ids", []), profile_id]
        existing["profile_update_reason"] = "merge_profile:high_similarity_low_tension"
    return out


def _lineage_ids_for_profile(profile_id: str, claims: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, list[str]]:
    claim_ids = [str(claim.get("claim_id") or "") for claim in claims if str(claim.get("claim_id") or "").strip()]
    sentence_ids = [str(item) for item in evidence.get("sentence_ids") or [] if item]
    source_ids = [str(item) for item in evidence.get("source_ids") or [] if item]
    return {
        "parent_ids": [*claim_ids, *sentence_ids, *source_ids],
        "child_ids": [f"retrieval_chunk:{profile_id}"] if profile_id else [],
    }


def _attach_claim_lineage(claims: list[dict[str, Any]], technical_entity_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in claims:
        claim = dict(item)
        evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
        parent_ids: list[str] = []
        sentence_ids = claim.get("sentence_ids") or evidence.get("sentence_ids") or []
        source_ids = claim.get("source_ids") or ([claim.get("source_id")] if claim.get("source_id") else []) or evidence.get("source_ids") or []
        for value in sentence_ids:
            text = str(value or "").strip()
            if text and text not in parent_ids:
                parent_ids.append(text)
        for value in [*source_ids, evidence.get("source_id")]:
            text = str(value or "").strip()
            if text and text not in parent_ids:
                parent_ids.append(text)
        claim.setdefault("parent_ids", parent_ids)
        claim.setdefault("child_ids", [technical_entity_id] if technical_entity_id else [])
        out.append(claim)
    return out


def _existing_profile_matches(row: dict[str, Any], candidate_id: str, candidate_profile: SearchProfile | None) -> bool:
    if not candidate_id:
        return False
    if candidate_id in {
        str(row.get("profile_id") or ""),
        str(row.get("selected_candidate_id") or ""),
        str(row.get("source_candidate_entity_id") or ""),
    }:
        return True
    if candidate_profile is None:
        return False
    key = _canonical_key(candidate_profile)
    return bool(key and key == str(row.get("canonical_key") or ""))


class GlobalProfileBuilderV0:
    version = GLOBAL_PROFILE_BUILDER_VERSION

    def build_many(
        self,
        decisions: list[DecisionAnalysis],
        profiles: list[SearchProfile],
        candidate_profiles: list[SearchProfile] | None = None,
        existing_global_profiles: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        profiles_by_id = {str(profile.search_profile_id): profile for profile in profiles}
        candidate_profiles_by_entity_id = {
            _candidate_entity_id(profile): profile
            for profile in (candidate_profiles or [])
            if _candidate_entity_id(profile)
        }
        existing_profiles = [dict(item) for item in existing_global_profiles or [] if isinstance(item, dict)]
        updates: list[dict[str, Any]] = []
        for decision in decisions:
            profile = profiles_by_id.get(str(decision.search_profile_id or ""))
            decision_type = decision.decision_type or decision.decision
            candidate_id = str(decision.selected_candidate_id or decision.candidate_entity_id or "")
            candidate_profile = candidate_profiles_by_entity_id.get(candidate_id)
            evidence = _evidence(decision, profile)
            incoming_claims = _claim_rows(profile, evidence)

            if decision_type == "uncertain_match":
                updates.append(
                    {
                        "profile_id": None,
                        "operation": "review",
                        "decision": decision.decision,
                        "decision_type": decision_type,
                        "selected_candidate_id": candidate_id or None,
                        "entity_name": profile.entity_name if profile is not None else decision.candidate_name,
                        "entity_type": profile.entity_type if profile is not None else decision.candidate_type,
                        "canonical_key": _canonical_key(profile, decision.candidate_name),
                        "manual_review_required": True,
                        "affected_profile_ids": [],
                        "profile_update_reason": "review_required:uncertain_match",
                        "claim_added_count": 0,
                        "claim_deduplicated_count": 0,
                        "claims": [],
                        "evidence": evidence,
                        "builder_version": self.version,
                    }
                )
                continue

            if decision_type == "merge_required":
                existing = next(
                    (
                        row
                        for row in existing_profiles
                        if _existing_profile_matches(row, candidate_id, candidate_profile)
                    ),
                    {},
                )
                base_profile = candidate_profile or profile
                profile_id = str(existing.get("profile_id") or decision.selected_profile_id or _global_profile_id(_canonical_key(base_profile)))
                claims, _added_count, _deduped_count = _merge_claims(list(existing.get("claims") or []), incoming_claims)
                updates.append(
                    {
                        **existing,
                        "profile_id": profile_id,
                        "operation": "review",
                        "decision": decision.decision,
                        "decision_type": decision_type,
                        "source_decision_id": str(decision.decision_analysis_id),
                        "selected_candidate_id": candidate_id or None,
                        "selected_profile_id": decision.selected_profile_id,
                        "entity_name": existing.get("entity_name")
                        or (base_profile.entity_name if base_profile is not None else decision.candidate_name),
                        "entity_type": existing.get("entity_type")
                        or (base_profile.entity_type if base_profile is not None else decision.candidate_type),
                        "canonical_key": existing.get("canonical_key") or _canonical_key(base_profile, decision.candidate_name),
                        "decision_confidence": decision.decision_confidence,
                        "decision_reason": decision.decision_reason,
                        "manual_review_required": True,
                        "affected_profile_ids": [profile_id],
                        "profile_update_reason": "review_required:merge_required",
                        "claim_added_count": 0,
                        "claim_deduplicated_count": 0,
                        "new_claim_ids": [claim["claim_id"] for claim in incoming_claims],
                        "claims": claims,
                        "evidence": _merge_evidence(dict(existing.get("evidence") or {}), evidence),
                        "builder_version": self.version,
                    }
                )
                continue

            if decision_type == "attach_existing":
                existing = next(
                    (
                        row
                        for row in existing_profiles
                        if _existing_profile_matches(row, candidate_id, candidate_profile)
                    ),
                    {},
                )
                base_profile = candidate_profile or profile
                profile_id = str(existing.get("profile_id") or decision.selected_profile_id or _global_profile_id(_canonical_key(base_profile)))
                claims, added_count, deduped_count = _merge_claims(list(existing.get("claims") or []), incoming_claims)
                existing_evidence = dict(existing.get("evidence") or {})
                updates.append(
                    {
                        **existing,
                        "profile_id": profile_id,
                        "operation": "update",
                        "decision": decision.decision,
                        "decision_type": decision_type,
                        "source_decision_id": str(decision.decision_analysis_id),
                        "selected_candidate_id": candidate_id or None,
                        "selected_profile_id": decision.selected_profile_id,
                        "entity_name": existing.get("entity_name")
                        or (base_profile.entity_name if base_profile is not None else decision.candidate_name),
                        "entity_type": existing.get("entity_type")
                        or (base_profile.entity_type if base_profile is not None else decision.candidate_type),
                        "canonical_key": existing.get("canonical_key") or _canonical_key(base_profile, decision.candidate_name),
                        "decision_confidence": decision.decision_confidence,
                        "decision_reason": decision.decision_reason,
                        "manual_review_required": False,
                        "affected_profile_ids": [profile_id],
                        "profile_update_reason": "attach_existing:add_claims",
                        "claim_added_count": added_count,
                        "claim_deduplicated_count": deduped_count,
                        "new_claim_ids": [claim["claim_id"] for claim in incoming_claims],
                        "claims": claims,
                        "evidence": _merge_evidence(existing_evidence, evidence),
                        "builder_version": self.version,
                    }
                )
                continue

            if decision_type == "create_new_profile":
                canonical_key = _canonical_key(profile, decision.candidate_name)
                profile_id = decision.created_profile_id or _global_profile_id(canonical_key)
                updates.append(
                    {
                        "profile_id": profile_id,
                        "operation": "create",
                        "decision": decision.decision,
                        "decision_type": decision_type,
                        "source_decision_id": str(decision.decision_analysis_id),
                        "selected_candidate_id": None,
                        "created_profile_id": profile_id,
                        "entity_name": profile.entity_name if profile is not None else decision.candidate_name,
                        "entity_type": profile.entity_type if profile is not None else decision.candidate_type,
                        "canonical_key": canonical_key,
                        "decision_confidence": decision.decision_confidence,
                        "decision_reason": decision.decision_reason,
                        "manual_review_required": False,
                        "affected_profile_ids": [profile_id],
                        "profile_update_reason": "create_new_profile:canonical_key",
                        "claim_added_count": len(incoming_claims),
                        "claim_deduplicated_count": 0,
                        "new_claim_ids": [claim["claim_id"] for claim in incoming_claims],
                        "claims": incoming_claims,
                        "evidence": evidence,
                        "builder_version": self.version,
                    }
                )
        split_updates: list[dict[str, Any]] = []
        for row in updates:
            split_updates.extend(_split_profile_if_needed(row))
        updates = _merge_duplicate_profiles(split_updates)
        for row in updates:
            profile_id = str(row.get("profile_id") or "")
            technical_entity_id = (
                str(row.get("selected_candidate_id") or "")
                or str(row.get("source_candidate_entity_id") or "")
                or f"technical_entity:{profile_id}"
            )
            row["claims"] = _attach_claim_lineage(list(row.get("claims") or []), technical_entity_id)
            lineage = _lineage_ids_for_profile(profile_id, list(row.get("claims") or []), dict(row.get("evidence") or {}))
            row.setdefault("parent_ids", lineage["parent_ids"])
            row.setdefault("child_ids", lineage["child_ids"])
        return updates


__all__ = ["GLOBAL_PROFILE_BUILDER_VERSION", "GlobalProfileBuilderV0"]
