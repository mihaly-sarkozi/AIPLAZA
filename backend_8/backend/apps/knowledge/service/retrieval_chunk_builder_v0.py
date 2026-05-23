from __future__ import annotations

from typing import Any

from apps.knowledge.service.language_rules import fold_text


RETRIEVAL_CHUNK_BUILDER_VERSION = "retrieval_chunk_builder_v0"


def _claim_id(claim: dict[str, Any]) -> str:
    return str(claim.get("claim_id") or "").strip()


def _claim_status(claim: dict[str, Any]) -> str:
    return str(claim.get("claim_status") or claim.get("status") or "active").strip().lower()


def _is_visible_claim(claim: dict[str, Any]) -> bool:
    return _claim_status(claim) not in {"banned", "revoked", "withdrawn", "retracted", "deleted", "weakened"}


def _claim_time_dominant(claim: dict[str, Any]) -> str:
    return str(claim.get("time_dominant") or claim.get("time_mode") or claim.get("time_filter") or "").strip().lower()


def _is_historical_claim(claim: dict[str, Any]) -> bool:
    if _is_event_claim(claim):
        return False
    return _claim_time_dominant(claim) in {"historical", "bounded", "event"} or _claim_status(claim) == "historical"


def _is_current_claim(claim: dict[str, Any]) -> bool:
    if not _is_visible_claim(claim) or _is_historical_claim(claim) or _is_event_claim(claim):
        return False
    return _state_label(claim) is not None and _claim_status(claim) in {"active", "current"} and _claim_time_dominant(claim) in {"", "current"}


def _is_active_typed_claim(claim: dict[str, Any]) -> bool:
    return _is_visible_claim(claim) and not _is_historical_claim(claim) and _claim_status(claim) in {"active", "current", ""}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, list):
            for item in value:
                text = str(item or "").strip()
                if text:
                    return text
            continue
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _claim_predicate(claim: dict[str, Any]) -> str:
    return _first_text(claim.get("predicate"), claim.get("predicate_text"), claim.get("predicates"))


def _claim_object(claim: dict[str, Any]) -> str:
    return _first_text(claim.get("object"), claim.get("object_text"), claim.get("objects"))


def _claim_time_values(claim: dict[str, Any]) -> list[str]:
    values = claim.get("time_values")
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item or "").strip()]
    value = _first_text(claim.get("time_value"), claim.get("time_label"))
    return [value] if value else []


def _state_label(claim: dict[str, Any]) -> str | None:
    predicate = _claim_predicate(claim).lower()
    obj = _claim_object(claim).lower()
    text = f"{predicate} {obj}".strip()
    if "inactive" in text or "inaktív" in text or "inaktiv" in text or "inactivo" in text or obj in {"false", "no"}:
        return "inactive"
    if "active" in text or "aktív" in text or "aktiv" in text or "activo" in text or obj in {"true", "yes"}:
        return "active"
    return None


def _is_rule_claim(claim: dict[str, Any]) -> bool:
    claim_type = str(claim.get("claim_type") or "").strip().lower()
    claim_group = str(claim.get("claim_group") or "").strip().lower()
    predicate = _claim_predicate(claim).strip().lower()
    if claim_type in {"rule", "rule_procedure", "obligation"} or claim_group in {"rule", "obligation"}:
        return True
    return predicate in {"must", "should", "required", "kötelező", "kell", "debe"}


def _canonical_rule_action(claim: dict[str, Any]) -> str:
    predicate = fold_text(_claim_predicate(claim))
    if predicate in {"must", "required", "kotelezo", "kötelező", "kell", "debe"}:
        return "must"
    if predicate in {"should", "deberia", "debería"}:
        return "should"
    return predicate


def _canonical_rule_object(claim: dict[str, Any]) -> str:
    text = fold_text(" ".join([_claim_predicate(claim), _claim_object(claim), str(claim.get("claim_text") or "")]))
    has_two_factor = any(
        token in text
        for token in (
            "two-factor",
            "two factor",
            "twofactor",
            "dos factores",
            "ketfaktoros",
            "kétfaktoros",
        )
    )
    has_auth = any(token in text for token in ("authentication", "autenticacion", "autenticación", "azonositas", "azonosítás", "azonositast", "azonosítást"))
    if has_two_factor and has_auth:
        return "enable two-factor authentication"
    return _claim_object(claim).strip().lower()


def _canonical_rule_text(claim: dict[str, Any]) -> str | None:
    action = _canonical_rule_action(claim)
    obj = _canonical_rule_object(claim)
    if action and obj:
        return f"{action} {obj}".strip()
    return None


def _is_relation_claim(claim: dict[str, Any]) -> bool:
    if _state_label(claim) or _is_rule_claim(claim):
        return False
    claim_group = str(claim.get("claim_group") or "").strip().lower()
    if claim_group == "relation" and _claim_object(claim).strip():
        return True
    predicate = _claim_predicate(claim).strip().lower()
    obj = _claim_object(claim).strip()
    return bool(obj and predicate in {"uses", "use", "használ", "hasznal", "utiliza", "usa", "integrates", "integrates with"})


def _display_relation_claim(claim: dict[str, Any]) -> str:
    predicate = _claim_predicate(claim).strip()
    obj = _claim_object(claim).strip()
    if predicate and obj:
        return f"{predicate} {obj}".strip()
    claim_text = str(claim.get("claim_text") or "").strip()
    if claim_text:
        return claim_text
    return _display_claim(claim)


def _display_rule_claim(claim: dict[str, Any]) -> str:
    canonical = _canonical_rule_text(claim)
    if canonical:
        return canonical
    predicate = _claim_predicate(claim).strip()
    obj = _claim_object(claim).strip()
    if predicate and obj:
        return f"{predicate} {obj}".strip()
    claim_text = str(claim.get("claim_text") or "").strip()
    if claim_text:
        return claim_text
    return _display_claim(claim)


def _is_descriptor_claim(claim: dict[str, Any]) -> bool:
    if _state_label(claim) or _is_relation_claim(claim) or _is_rule_claim(claim) or _is_event_claim(claim):
        return False
    claim_type = str(claim.get("claim_type") or "").strip().lower()
    claim_group = str(claim.get("claim_group") or "").strip().lower()
    return claim_type == "stable_descriptor" or claim_group == "descriptor"


def _is_event_claim(claim: dict[str, Any]) -> bool:
    claim_type = str(claim.get("claim_type") or "").strip().lower()
    claim_group = str(claim.get("claim_group") or "").strip().lower()
    return claim_type == "event" or claim_group == "event" or _claim_time_dominant(claim) == "event"


def _normalized_time_mode(claim: dict[str, Any]) -> str:
    mode = _claim_time_dominant(claim)
    if mode == "historical":
        return "bounded"
    return mode


def _dedupe_key(claim: dict[str, Any]) -> tuple[str, str, str, str]:
    state = _state_label(claim)
    subject = str(claim.get("subject") or "").strip().lower()
    if _is_rule_claim(claim):
        return (subject, _canonical_rule_action(claim), _canonical_rule_object(claim), "")
    normalized_state = state or _claim_predicate(claim).strip().lower()
    time_mode = _normalized_time_mode(claim)
    time_value = "|".join(_claim_time_values(claim)).lower()
    if not state:
        time_value = time_value or _claim_object(claim).strip().lower()
    return (subject, normalized_state, time_mode, time_value)


def _dedupe_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for claim in claims:
        key = _dedupe_key(claim)
        if key in seen:
            continue
        seen.add(key)
        out.append(claim)
    return out


def _display_claim(claim: dict[str, Any]) -> str:
    subject = str(claim.get("subject") or "").strip()
    state = _state_label(claim)
    if state:
        time_values = _claim_time_values(claim)
        if _is_historical_claim(claim):
            suffix = f" in {', '.join(time_values)}" if time_values else ""
            return f"{state}{suffix}".strip()
        return f"currently {state}"
    claim_text = str(claim.get("claim_text") or "").strip()
    if claim_text:
        return claim_text
    predicate = _claim_predicate(claim)
    obj = _claim_object(claim)
    if predicate and obj:
        return f"{subject} {predicate} {obj}".strip()
    if predicate:
        return f"{subject} {predicate}".strip()
    return subject


def _fact_block(title: str, claims: list[dict[str, Any]], display_fn=_display_claim) -> list[str]:
    parts = [display_fn(claim) for claim in claims]
    parts = [part for part in parts if part]
    if not parts:
        return []
    return [f"{title}:"] + [f"- {part}" for part in parts]


def _rule_block(claims: list[dict[str, Any]]) -> list[str]:
    parts = [_display_rule_claim(claim) for claim in claims]
    parts = [part for part in parts if part]
    if not parts:
        return []
    return ["Rules:"] + [f"- {part}" for part in parts]


def _descriptor_block(claims: list[dict[str, Any]]) -> list[str]:
    parts = [
        f"{_claim_predicate(claim)} {_claim_object(claim)}".strip()
        if _claim_predicate(claim) and _claim_object(claim)
        else _display_claim(claim)
        for claim in claims
    ]
    parts = [part for part in parts if part]
    if not parts:
        return []
    return ["Descriptors:"] + [f"- {part}" for part in parts]


def _event_block(claims: list[dict[str, Any]]) -> list[str]:
    parts = [_display_event_claim(claim) for claim in claims]
    parts = [part for part in parts if part]
    if not parts:
        return []
    return ["Events:"] + [f"- {part}" for part in parts]


def _display_event_claim(claim: dict[str, Any]) -> str:
    predicate = _claim_predicate(claim).strip()
    obj = _claim_object(claim).strip()
    if predicate and obj:
        predicate = predicate.removeprefix("was ").strip()
        return f"{predicate} {obj}".strip()
    return _display_claim(claim)


def _relation_block(claims: list[dict[str, Any]]) -> list[str]:
    parts = [_display_relation_claim(claim) for claim in claims]
    parts = [part for part in parts if part]
    if not parts:
        return []
    return ["Relation facts:"] + [f"- {part}" for part in parts]


def _join_blocks(blocks: list[list[str]]) -> str:
    lines: list[str] = []
    for block in blocks:
        if not block:
            continue
        if lines:
            lines.append("")
        lines.extend(block)
    return "\n".join(line for line in lines if line is not None).strip()


def _evidence_ids(claims: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for claim in claims:
        claim_id = _claim_id(claim)
        if claim_id and claim_id not in ids:
            ids.append(claim_id)
        for sentence_id in claim.get("sentence_ids") or []:
            text = str(sentence_id or "").strip()
            if text and text not in ids:
                ids.append(text)
    return ids


def _source_ids(claims: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for claim in claims:
        evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
        for value in [claim.get("source_id"), evidence.get("source_id"), *(claim.get("source_ids") or []), *(evidence.get("source_ids") or [])]:
            text = str(value or "").strip()
            if text and text not in ids:
                ids.append(text)
    return ids


def _profile_tensions(profile: dict[str, Any], tension_analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profile_id = str(profile.get("profile_id") or "")
    claim_ids = {_claim_id(claim) for claim in profile.get("claims") or [] if isinstance(claim, dict)}
    out: list[dict[str, Any]] = []
    for tension in tension_analyses:
        evidence = tension.get("evidence") if isinstance(tension.get("evidence"), dict) else {}
        if profile_id and str(evidence.get("profile_id") or "") == profile_id:
            out.append(tension)
            continue
        conflicting = {str(item or "") for item in tension.get("conflicting_claim_ids") or []}
        if claim_ids & conflicting:
            out.append(tension)
            continue
        evidence_claim_ids = {str(item or "") for item in evidence.get("claim_ids") or []}
        if claim_ids & evidence_claim_ids:
            out.append(tension)
    return out


def _has_tension(tensions: list[dict[str, Any]], tension_type: str) -> bool:
    return any(str(item.get("tension_type") or "") == tension_type for item in tensions)


def _has_conflict_tension(tensions: list[dict[str, Any]]) -> bool:
    return any(str(item.get("tension_type") or "") in {"contradiction", "hard_conflict"} for item in tensions)


def _conflicting_claim_ids(tensions: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for tension in tensions:
        if str(tension.get("tension_type") or "") not in {"contradiction", "hard_conflict"}:
            continue
        ids.update(str(item or "") for item in tension.get("conflicting_claim_ids") or [] if item)
    return ids


def _has_current_state_conflict(claims: list[dict[str, Any]]) -> bool:
    states = {
        state
        for claim in claims
        for state in [_state_label(claim)]
        if state and not _is_historical_claim(claim)
    }
    return {"active", "inactive"}.issubset(states)


class RetrievalChunkBuilderV0:
    version = RETRIEVAL_CHUNK_BUILDER_VERSION

    def build_many(
        self,
        global_profiles: list[dict[str, Any]],
        tension_analyses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            chunk
            for profile in global_profiles
            if isinstance(profile, dict)
            for chunk in [self.build(profile, tension_analyses)]
            if chunk is not None
        ]

    def build(self, global_profile: dict[str, Any], tension_analyses: list[dict[str, Any]]) -> dict[str, Any] | None:
        claims = [dict(item) for item in global_profile.get("claims") or [] if isinstance(item, dict)]
        if not claims:
            return None

        tensions = _profile_tensions(global_profile, tension_analyses)
        visible_claims = [claim for claim in claims if _is_visible_claim(claim)]
        active_claims = [claim for claim in visible_claims if _is_active_typed_claim(claim)]
        current_claims = _dedupe_claims([claim for claim in active_claims if _is_current_claim(claim)])
        historical_claims = _dedupe_claims([claim for claim in visible_claims if _is_historical_claim(claim)])
        descriptor_claims = _dedupe_claims([claim for claim in active_claims if _is_descriptor_claim(claim)])
        event_claims = _dedupe_claims([claim for claim in visible_claims if _is_event_claim(claim)])
        relation_claims = _dedupe_claims([claim for claim in active_claims if _is_relation_claim(claim)])
        rule_claims = _dedupe_claims([claim for claim in active_claims if _is_rule_claim(claim)])
        conflict_ids = _conflicting_claim_ids(tensions)
        conflict_claims = _dedupe_claims([claim for claim in visible_claims if _claim_id(claim) in conflict_ids or _claim_status(claim) == "disputed"])
        if not conflict_claims and _has_current_state_conflict(current_claims):
            conflict_claims = list(current_claims)

        selected_claims = [*current_claims, *descriptor_claims, *event_claims, *relation_claims, *rule_claims]
        if conflict_claims:
            for claim in conflict_claims:
                if _claim_id(claim) not in {_claim_id(item) for item in selected_claims}:
                    selected_claims.append(claim)
        if not selected_claims and historical_claims:
            selected_claims = list(historical_claims[:1])

        name = str(global_profile.get("entity_name") or global_profile.get("canonical_key") or "Unknown profile")
        retrieval_chunk_text = _join_blocks(
            [
                [f"{name} ({global_profile.get('entity_type') or 'unknown'})"],
                _fact_block("Current facts", current_claims),
                _fact_block("Historical facts", historical_claims),
                _relation_block(relation_claims),
                _rule_block(rule_claims),
                _descriptor_block(descriptor_claims),
                _event_block(event_claims),
                _fact_block("Conflicts", conflict_claims),
            ]
        )

        evidence_claims = [
            *current_claims,
            *historical_claims,
            *relation_claims,
            *rule_claims,
            *descriptor_claims,
            *event_claims,
            *conflict_claims,
        ]
        confidence = float(global_profile.get("decision_confidence") or 0.75)
        has_conflict_tension = _has_conflict_tension(tensions)
        if conflict_claims or has_conflict_tension:
            confidence = min(confidence, 0.65)

        return {
            "retrieval_chunk_id": f"retrieval_chunk:{global_profile.get('profile_id')}",
            "profile_id": global_profile.get("profile_id"),
            "entity_name": name,
            "entity_type": global_profile.get("entity_type"),
            "canonical_key": global_profile.get("canonical_key"),
            "parent_ids": [str(global_profile.get("profile_id") or "")] if global_profile.get("profile_id") else [],
            "child_ids": [],
            "retrieval_chunk_text": retrieval_chunk_text,
            "structured_facts": {
                "current": current_claims,
                "active": current_claims,
                "conflicts": conflict_claims,
                "historical": historical_claims,
                "descriptors": descriptor_claims,
                "events": event_claims,
                "relations": relation_claims,
                "rules": rule_claims,
                "tension_types": [str(item.get("tension_type") or "") for item in tensions if item.get("tension_detected")],
            },
            "evidence_ids": _evidence_ids(evidence_claims),
            "source_ids": _source_ids(evidence_claims),
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
            "conflicting": bool(conflict_claims or has_conflict_tension),
            "temporal_context_included": bool(historical_claims),
            "builder_version": self.version,
        }


__all__ = ["RETRIEVAL_CHUNK_BUILDER_VERSION", "RetrievalChunkBuilderV0"]
