from __future__ import annotations

from typing import Any

from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key
from apps.knowledge.service.language_rules import fold_text


QUERY_AWARE_RETRIEVAL_VERSION = "query_aware_retrieval_v0"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _profile_id(row: dict[str, Any]) -> str:
    return _text(row.get("profile_id"))


def _claim_id(row: dict[str, Any]) -> str:
    return _text(row.get("claim_id"))


def _claim_status(row: dict[str, Any]) -> str:
    return _text(row.get("claim_status") or row.get("status") or "active").lower()


def _claim_time(row: dict[str, Any]) -> str:
    return _text(row.get("time_dominant") or row.get("time_mode")).lower()


def _is_event(row: dict[str, Any]) -> bool:
    return _text(row.get("fact_bucket")).lower() == "events" or _text(row.get("claim_group")).lower() == "event" or _claim_time(row) == "event"


def _is_historical(row: dict[str, Any]) -> bool:
    if _is_event(row):
        return False
    return _claim_status(row) == "historical" or _claim_time(row) in {"historical", "bounded"}


def _claim_time_filter(row: dict[str, Any]) -> str:
    if _is_event(row):
        return "event_time"
    return "historical" if _is_historical(row) else "current"


def _claim_state(row: dict[str, Any]) -> str | None:
    predicate = fold_text(_text(row.get("predicate")))
    obj = fold_text(_text(row.get("object")))
    haystack = fold_text(" ".join([_text(row.get("subject")), predicate, obj]))
    if predicate == "active":
        if obj in {"false", "no", "inactive", "inaktiv", "inaktív", "inactivo"}:
            return "inactive"
        if obj in {"true", "yes", "active", "aktiv", "aktív", "activo"}:
            return "active"
    if "inactive" in haystack or "inaktiv" in haystack or "inaktív" in haystack or "inactivo" in haystack:
        return "inactive"
    if "active" in haystack or "aktiv" in haystack or "aktív" in haystack or "activo" in haystack:
        return "active"
    return None


def _claim_predicate(row: dict[str, Any]) -> str:
    values = row.get("predicates")
    if isinstance(values, list):
        for item in values:
            text = _text(item)
            if text:
                return text
    return _text(row.get("predicate") or row.get("predicate_text"))


def _claim_object(row: dict[str, Any]) -> str:
    values = row.get("objects")
    if isinstance(values, list):
        for item in values:
            text = _text(item)
            if text:
                return text
    return _text(row.get("object") or row.get("object_text"))


def _claim_haystack(row: dict[str, Any]) -> str:
    return fold_text(
        " ".join(
            [
                _text(row.get("subject")),
                _claim_predicate(row),
                _claim_object(row),
                _text(row.get("claim_text")),
                _text(row.get("canonical_claim_text")),
                _text(row.get("display_claim_text")),
            ]
        )
    )


def _canonical_rule_action(row: dict[str, Any]) -> str:
    predicate = fold_text(_claim_predicate(row))
    if predicate in {"must", "required", "kotelezo", "kötelező", "kell", "debe"}:
        return "must"
    if predicate in {"should", "deberia", "debería"}:
        return "should"
    return predicate


def _canonical_rule_object(row: dict[str, Any]) -> str:
    text = fold_text(" ".join([_claim_predicate(row), _claim_object(row), _text(row.get("claim_text"))]))
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
    has_auth = any(
        token in text
        for token in (
            "authentication",
            "autenticacion",
            "autenticación",
            "azonositas",
            "azonosítás",
            "azonositast",
            "azonosítást",
        )
    )
    if has_two_factor and has_auth:
        return "enable two-factor authentication"
    return _claim_object(row).strip().lower()


def _is_relation_claim(row: dict[str, Any]) -> bool:
    predicate = fold_text(_claim_predicate(row))
    if predicate in {"uses", "use", "hasznal", "használ", "utiliza", "usa", "integrates", "integrates with"}:
        return True
    return bool(_text(row.get("fact_bucket")) == "relations")


def _claim_semantic_type(row: dict[str, Any]) -> str:
    bucket = _claim_bucket(row)
    group = _text(row.get("claim_group")).lower()
    if bucket == "events" or group == "event" or _is_event(row):
        return "event"
    if _claim_state(row) is not None or fold_text(_claim_predicate(row)) == "active":
        return "state"
    if _is_relation_claim(row):
        return "relation"
    return "descriptor"


def _claim_contains_location_info(row: dict[str, Any]) -> bool:
    predicate = fold_text(_claim_predicate(row))
    obj = _claim_object(row)
    haystack = _claim_haystack(row)
    if predicate in {
        "address",
        "at",
        "based in",
        "city",
        "country",
        "in",
        "located",
        "located at",
        "located in",
        "located_in",
        "location",
        "site",
        "where",
    } and bool(obj):
        return True
    return any(
        token in haystack
        for token in (
            "address",
            "based in",
            "city",
            "country",
            "located",
            "location",
            "office in",
            "site in",
            "talalhato",
            "található",
            "varos",
            "város",
        )
    )


def _claim_contains_time_info(row: dict[str, Any]) -> bool:
    if _claim_time_values(row):
        return True
    haystack = _claim_haystack(row)
    return bool(
        _is_event(row)
        or _is_historical(row)
        or _text(row.get("time_value") or row.get("time_label") or row.get("valid_from") or row.get("valid_to"))
        or any(token in haystack for token in ("completed on", "created on", "updated on", "on 20", "in 20", "in 19"))
    )


def _claim_contains_person_info(row: dict[str, Any]) -> bool:
    predicate = fold_text(_claim_predicate(row))
    obj = _claim_object(row)
    if predicate in {"lead", "owner", "responsible", "responsible for", "created by", "maintained by", "contact"} and obj:
        return True
    haystack = _claim_haystack(row)
    return any(token in haystack for token in (" by ", " lead", " owner", " responsible", "contact", "person", "user"))


def _claim_contains_object_info(row: dict[str, Any]) -> bool:
    return bool(_claim_object(row)) and _claim_semantic_type(row) in {"descriptor", "event", "relation"}


def _claim_contains_explanation_info(row: dict[str, Any]) -> bool:
    haystack = _claim_haystack(row)
    return any(token in haystack for token in ("because", "due to", "reason", "why", "mert", "amiatt", "azert", "azért"))


def _claim_matches_expected_answer_type(claim: dict[str, Any], expected_answer_type: str | None) -> bool:
    expected = _text(expected_answer_type).lower()
    if not expected:
        return True
    if expected == "location":
        return _claim_contains_location_info(claim)
    if expected == "time":
        return _claim_contains_time_info(claim)
    if expected == "person":
        return _claim_contains_person_info(claim)
    if expected == "object":
        return _claim_contains_object_info(claim)
    if expected == "explanation":
        return _claim_contains_explanation_info(claim)
    return True


def _claim_bucket(row: dict[str, Any]) -> str:
    return _text(row.get("fact_bucket")).lower()


def _claim_matches_relation_object(claim: dict[str, Any], relation_object: str) -> bool:
    if not relation_object:
        return True
    return relation_object in fold_text(_claim_object(claim))


def _relation_predicate_matches(claim: dict[str, Any], relation_predicate: str) -> bool:
    if not relation_predicate:
        return True
    predicate = fold_text(_claim_predicate(claim))
    if predicate in {relation_predicate, relation_predicate.rstrip("s")}:
        return True
    uses_family = {"use", "uses", "using", "integrate", "integrates", "integrates with", "hasznal", "használ", "utiliza", "usa"}
    return predicate in uses_family and relation_predicate in uses_family


def _claim_matches_intent(claim: dict[str, Any], intent: str, relation_predicate: str, relation_object: str = "") -> bool:
    if intent == "relation":
        return _is_relation_claim(claim) and _relation_predicate_matches(claim, relation_predicate) and _claim_matches_relation_object(claim, relation_object)
    if intent == "rule":
        return _claim_bucket(claim) == "rules" or fold_text(_claim_predicate(claim)) in {"must", "should", "required", "kotelezo", "kötelező", "kell", "debe"}
    if intent == "event":
        return _claim_bucket(claim) == "events" or _text(claim.get("claim_group")).lower() == "event"
    if intent == "descriptor":
        predicate = fold_text(_claim_predicate(claim))
        return (
            _claim_bucket(claim) == "descriptors"
            or _text(claim.get("claim_group")).lower() == "descriptor"
            or (_is_relation_claim(claim) and any(token in predicate for token in ("lead", "responsible", "is the", "is")))
        )
    return True


def _claim_time_values(row: dict[str, Any]) -> list[str]:
    values = row.get("time_values")
    if isinstance(values, list):
        return [_text(item) for item in values if _text(item)]
    value = _text(row.get("time_value") or row.get("time_label"))
    return [value] if value else []


def _claim_sentence_ids(row: dict[str, Any]) -> list[str]:
    values = row.get("sentence_ids")
    if isinstance(values, list):
        return [_text(item) for item in values if _text(item)]
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    values = evidence.get("sentence_ids")
    if isinstance(values, list):
        return [_text(item) for item in values if _text(item)]
    return []


def _claim_source_ids(row: dict[str, Any]) -> list[str]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    values = [row.get("source_id"), evidence.get("source_id"), *(row.get("source_ids") or []), *(evidence.get("source_ids") or [])]
    out: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in out:
            out.append(text)
    return out


def _claims_from_chunk(chunk: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    facts = chunk.get("structured_facts") if isinstance(chunk.get("structured_facts"), dict) else {}
    claims: list[dict[str, Any]] = []
    for key in ("current", "active", "conflicts", "historical", "descriptors", "events", "relations", "rules"):
        for item in facts.get(key) or []:
            if isinstance(item, dict):
                claim = dict(item)
                claim.setdefault("fact_bucket", key)
                claims.append(claim)
    if not claims:
        claims = [dict(item) for item in profile.get("claims") or [] if isinstance(item, dict)]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for claim in claims:
        if _claim_status(claim) in {"weakened", "withdrawn"}:
            continue
        key = _claim_id(claim) or f"{claim.get('subject')}:{claim.get('predicate')}:{claim.get('object')}:{claim.get('status')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(claim)
    return out


def _conflict_claim_ids(chunk: dict[str, Any]) -> set[str]:
    facts = chunk.get("structured_facts") if isinstance(chunk.get("structured_facts"), dict) else {}
    return {
        _claim_id(item)
        for item in facts.get("conflicts") or []
        if isinstance(item, dict) and _claim_id(item)
    }


def _display_claim(claim: dict[str, Any]) -> str:
    state = _claim_state(claim)
    if state:
        if _is_historical(claim):
            values = _claim_time_values(claim)
            suffix = f" in {', '.join(values)}" if values else ""
            return f"{state}{suffix}".strip()
        return f"currently {state}"
    subject = _text(claim.get("subject"))
    predicate = _claim_predicate(claim)
    obj = _claim_object(claim)
    if _is_relation_claim(claim) and predicate and obj:
        return f"{subject} {predicate} {obj}".strip()
    bucket = _claim_bucket(claim)
    group = _text(claim.get("claim_group")).lower()
    if _claim_matches_intent(claim, "rule", "", ""):
        canonical = _canonical_claim_text(claim)
        if canonical:
            return canonical
    if predicate and obj and (bucket in {"rules", "events", "descriptors"} or group in {"rule", "event", "descriptor"}):
        return f"{subject} {predicate} {obj}".strip()
    if predicate and obj:
        return f"{subject} {predicate} = {obj}".strip()
    return " ".join(part for part in (subject, predicate) if part)


def _raw_claim_text(claim: dict[str, Any]) -> str:
    text = _text(claim.get("claim_text"))
    if text:
        return text
    return " ".join(part for part in (_text(claim.get("subject")), _claim_predicate(claim), _claim_object(claim)) if part)


def _canonical_claim_text(claim: dict[str, Any]) -> str:
    subject = _text(claim.get("subject"))
    predicate = _claim_predicate(claim)
    obj = _claim_object(claim)
    if _claim_matches_intent(claim, "rule", "", ""):
        action = _canonical_rule_action(claim)
        rule_object = _canonical_rule_object(claim)
        if subject and action and rule_object:
            return f"{subject} {action} {rule_object}".strip()
        if action and rule_object:
            return f"{action} {rule_object}".strip()
    if subject and predicate and obj:
        return f"{subject} {predicate} {obj}".strip()
    if predicate and obj:
        return f"{predicate} {obj}".strip()
    return _raw_claim_text(claim)


def _claim_matches_state(claim: dict[str, Any], state: str | None) -> bool:
    if not state:
        return True
    return _claim_state(claim) == state


def _ordered_claims(claims: list[dict[str, Any]], *, time_filter: str | None, state: str | None) -> list[dict[str, Any]]:
    def rank(claim: dict[str, Any]) -> tuple[int, int, str]:
        historical = _is_historical(claim)
        state_mismatch = 0 if _claim_matches_state(claim, state) else 1
        if time_filter == "historical":
            time_rank = 0 if historical else 1
        elif time_filter == "current":
            time_rank = 1 if historical else 0
        else:
            time_rank = 2 if historical else 0
        if _text(claim.get("fact_bucket")) == "conflicts":
            time_rank = min(time_rank, 1)
        return (state_mismatch, time_rank, _claim_id(claim))

    return sorted(claims, key=rank)


def _has_current_state_conflict(claims: list[dict[str, Any]]) -> bool:
    states = {
        state
        for claim in claims
        for state in [_claim_state(claim)]
        if state and not _is_historical(claim)
    }
    return {"active", "inactive"}.issubset(states)


def _keyword_score(chunk: dict[str, Any], profile: dict[str, Any], keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    haystack = fold_text(
        " ".join(
            [
                _text(chunk.get("retrieval_chunk_text")),
                _text(profile.get("entity_name")),
                _text(profile.get("canonical_key")),
            ]
        )
    )
    hits = sum(1 for keyword in keywords if fold_text(keyword) in haystack)
    return hits / max(len(keywords), 1)


def _entity_types_compatible(query_type: str, profile_type: str) -> bool:
    if not query_type:
        return True
    if query_type == profile_type:
        return True
    if query_type == "system_component" and profile_type in {"software", "module", "service", "workflow", "process"}:
        return True
    return False


def _entity_keyword_fallback(query_profile: dict[str, Any], profile: dict[str, Any], chunk: dict[str, Any]) -> bool:
    keywords = [fold_text(_text(item)) for item in query_profile.get("keywords") or [] if _text(item)]
    if not keywords:
        return False
    haystack = fold_text(
        " ".join(
            [
                _text(profile.get("entity_name")),
                _text(profile.get("canonical_key")),
                _text(chunk.get("entity_name")),
                _text(chunk.get("canonical_key")),
            ]
        )
    )
    entity_hits = [keyword for keyword in keywords if keyword in haystack]
    return len(entity_hits) >= 2


def _canonical_entity_key(value: Any) -> str:
    text = _text(value)
    return canonicalize_entity_key(text) or fold_text(text)


def _profile_matches_entity(query_profile: dict[str, Any], profile: dict[str, Any], chunk: dict[str, Any]) -> tuple[bool, str | None]:
    entity_type = _text(query_profile.get("entity_type")).lower()
    profile_type = _text(profile.get("entity_type") or chunk.get("entity_type")).lower()
    if not _entity_types_compatible(entity_type, profile_type):
        return False, "entity_type_mismatch"
    entity = _canonical_entity_key(query_profile.get("entity"))
    if entity:
        canonical_keys = {
            _canonical_entity_key(profile.get("canonical_key")),
            _canonical_entity_key(chunk.get("canonical_key")),
        } - {""}
        if entity not in canonical_keys:
            return False, "entity_mismatch"
    elif _text(query_profile.get("relation_object")):
        return True, None
    elif (
        entity_type == "system_component"
        and _text(query_profile.get("intent")).lower() == "relation"
        and not _entity_keyword_fallback(query_profile, profile, chunk)
    ):
        return False, "entity_keyword_mismatch"
    return True, None


class QueryAwareRetrievalV0:
    version = QUERY_AWARE_RETRIEVAL_VERSION

    def match(
        self,
        *,
        query_profile: dict[str, Any],
        retrieval_chunks: list[dict[str, Any]],
        global_profiles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        profiles_by_id = {_profile_id(profile): profile for profile in global_profiles if _profile_id(profile)}
        filtered: list[dict[str, Any]] = []
        matched_chunks: list[dict[str, Any]] = []
        matched_claims: list[dict[str, Any]] = []
        keywords = [_text(item) for item in query_profile.get("keywords") or [] if _text(item)]
        state = _text(query_profile.get("state")).lower() or None
        time_filter = _text(query_profile.get("time_filter")).lower() or None
        expected_answer_type = _text(query_profile.get("expected_answer_type")).lower() or None

        for chunk in retrieval_chunks:
            if not isinstance(chunk, dict):
                continue
            profile = profiles_by_id.get(_profile_id(chunk), {})
            if not profile:
                profile = {
                    "profile_id": chunk.get("profile_id"),
                    "entity_name": chunk.get("entity_name"),
                    "entity_type": chunk.get("entity_type"),
                    "canonical_key": chunk.get("canonical_key"),
                    "claims": [],
                }
            matches, reason = _profile_matches_entity(query_profile, profile, chunk)
            if not matches:
                filtered.append(
                    {
                        "profile_id": chunk.get("profile_id"),
                        "entity_name": chunk.get("entity_name") or profile.get("entity_name"),
                        "reason": reason,
                    }
                )
                continue
            claims = _ordered_claims(_claims_from_chunk(chunk, profile), time_filter=time_filter, state=state)
            preferred_claims = [claim for claim in claims if _claim_matches_state(claim, state)]
            conflict_ids = _conflict_claim_ids(chunk)
            conflict_claims = [
                claim
                for claim in claims
                if _text(claim.get("fact_bucket")) == "conflicts" or (_claim_id(claim) and _claim_id(claim) in conflict_ids)
            ]
            if state and not preferred_claims:
                filtered.append(
                    {
                        "profile_id": chunk.get("profile_id"),
                        "entity_name": chunk.get("entity_name") or profile.get("entity_name"),
                        "reason": "state_mismatch",
                    }
                )
                continue
            selected_claims = preferred_claims or claims
            intent = _text(query_profile.get("intent")).lower()
            relation_predicate = fold_text(_text(query_profile.get("relation_predicate")))
            relation_object = fold_text(_text(query_profile.get("relation_object")))
            if intent in {"relation", "rule", "event", "descriptor"}:
                intent_claims = [claim for claim in selected_claims if _claim_matches_intent(claim, intent, relation_predicate, relation_object)]
                if not intent_claims:
                    filtered.append(
                        {
                            "profile_id": chunk.get("profile_id"),
                            "entity_name": chunk.get("entity_name") or profile.get("entity_name"),
                            "reason": f"{intent}_claim_mismatch",
                        }
                    )
                    continue
                selected_claims = intent_claims
            answer_type_claims = [
                claim
                for claim in selected_claims
                if _claim_matches_expected_answer_type(claim, expected_answer_type)
            ]
            if expected_answer_type and not answer_type_claims:
                filtered.append(
                    {
                        "profile_id": chunk.get("profile_id"),
                        "entity_name": chunk.get("entity_name") or profile.get("entity_name"),
                        "reason": "semantic_answer_type_mismatch",
                        "expected_answer_type": expected_answer_type,
                    }
                )
                continue
            selected_claims = answer_type_claims or selected_claims
            for claim in conflict_claims:
                if _claim_id(claim) not in {_claim_id(item) for item in selected_claims}:
                    selected_claims.append(claim)
            temporal_context_used = any(_is_historical(claim) for claim in selected_claims)
            conflict_marker = bool(chunk.get("conflicting")) or bool((chunk.get("structured_facts") or {}).get("conflicts")) or _has_current_state_conflict(selected_claims)
            score = 0.45 + (_keyword_score(chunk, profile, keywords) * 0.25)
            if selected_claims:
                score += 0.15
            if conflict_marker:
                score += 0.05
            if temporal_context_used and time_filter in {"historical", None}:
                score += 0.05
            score = round(min(score, 0.95), 4)
            matched_chunks.append(
                {
                    "profile_id": chunk.get("profile_id"),
                    "entity_name": chunk.get("entity_name") or profile.get("entity_name"),
                    "entity_type": profile.get("entity_type"),
                    "retrieval_chunk_text": chunk.get("retrieval_chunk_text"),
                    "conflict_marker": conflict_marker,
                    "temporal_context_used": temporal_context_used,
                    "matched_claim_ids": [_claim_id(claim) for claim in selected_claims if _claim_id(claim)],
                    "evidence_ids": list(chunk.get("evidence_ids") or []),
                    "source_ids": list(chunk.get("source_ids") or []),
                    "retrieval_confidence": score,
                }
            )
            for claim in selected_claims:
                if _claim_state(claim):
                    canonical_claim_text = _display_claim(claim)
                    display_claim_text = canonical_claim_text
                else:
                    canonical_claim_text = _canonical_claim_text(claim)
                    display_claim_text = canonical_claim_text or _display_claim(claim)
                matched_claims.append(
                    {
                        "profile_id": chunk.get("profile_id"),
                        "entity_name": chunk.get("entity_name") or profile.get("entity_name"),
                        "claim_id": _claim_id(claim),
                        "claim_text": display_claim_text,
                        "raw_claim_text": _raw_claim_text(claim),
                        "canonical_claim_text": canonical_claim_text,
                        "display_claim_text": display_claim_text,
                        "language": _text(claim.get("language") or claim.get("source_language")),
                        "predicate": _claim_predicate(claim),
                        "object": _claim_object(claim),
                        "fact_bucket": _text(claim.get("fact_bucket")),
                        "claim_group": _text(claim.get("claim_group")),
                        "claim_semantic_type": _claim_semantic_type(claim),
                        "state": _claim_state(claim),
                        "time_filter": _claim_time_filter(claim),
                        "time_values": _claim_time_values(claim),
                        "sentence_ids": _claim_sentence_ids(claim),
                        "source_ids": _claim_source_ids(claim),
                        "conflict_marker": conflict_marker and _text(claim.get("fact_bucket")) == "conflicts",
                    }
                )

        matched_chunks = sorted(matched_chunks, key=lambda item: float(item.get("retrieval_confidence") or 0.0), reverse=True)
        confidence = round(
            sum(float(item.get("retrieval_confidence") or 0.0) for item in matched_chunks) / max(len(matched_chunks), 1),
            4,
        )
        return {
            "matched_chunks": matched_chunks,
            "matched_claims": matched_claims,
            "filtered_out_reason": filtered,
            "retrieval_confidence": confidence,
            "query_retrieval_match_count": len(matched_chunks),
            "query_retrieval_filtered_count": len(filtered),
            "conflict_marker_included": any(bool(item.get("conflict_marker")) for item in matched_chunks),
            "temporal_context_used": any(bool(item.get("temporal_context_used")) for item in matched_chunks),
            "builder_version": self.version,
        }


__all__ = ["QUERY_AWARE_RETRIEVAL_VERSION", "QueryAwareRetrievalV0"]
