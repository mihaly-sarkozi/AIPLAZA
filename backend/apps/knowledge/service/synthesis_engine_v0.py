from __future__ import annotations

import logging
from typing import Any

from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key
from apps.knowledge.service.language_rules import fold_text


SYNTHESIS_ENGINE_VERSION = "synthesis_engine_v0"
logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _entity_key(value: Any) -> str:
    text = _text(value)
    return canonicalize_entity_key(text) or fold_text(text)


def _row_entity_key(row: dict[str, Any]) -> str:
    for key in ("entity_name", "canonical_key", "subject"):
        value = _entity_key(row.get(key))
        if value:
            return value
    return ""


def _filter_to_query_entity(
    query_profile: dict[str, Any],
    matched_chunks: list[dict[str, Any]],
    matched_claims: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    query_entity = _entity_key(query_profile.get("entity"))
    if not query_entity:
        return matched_chunks, matched_claims, True
    filtered_chunks = [chunk for chunk in matched_chunks if _row_entity_key(chunk) == query_entity]
    filtered_claims = [claim for claim in matched_claims if _row_entity_key(claim) == query_entity]
    return filtered_chunks, filtered_claims, bool(filtered_chunks)


def _no_answer_result(*, version: str, synthesis_debug: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "answer_text": "I could not find enough information to answer this question.",
        "answer_mode": "no_answer",
        "cited_claim_ids": [],
        "cited_evidence_ids": [],
        "cited_sentence_ids": [],
        "cited_source_ids": [],
        "source_ids": [],
        "evidence_summary": [],
        "synthesis_confidence": 0.0,
        "builder_version": version,
    }
    if synthesis_debug is not None:
        result["synthesis_debug"] = synthesis_debug
    return result


def _entity_name(query_profile: dict[str, Any], matched_chunks: list[dict[str, Any]], matched_claims: list[dict[str, Any]]) -> str:
    explicit = _text(query_profile.get("entity"))
    if explicit:
        return explicit
    for row in [*matched_claims, *matched_chunks]:
        value = _text(row.get("entity_name"))
        if value:
            return value
    return "The entity"


def _article_name(name: str) -> str:
    if name.lower().startswith(("the ", "a ", "an ")):
        return name
    return f"The {name}"


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _claim_sentence_ids(claim: dict[str, Any]) -> list[str]:
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    return [* _str_list(claim.get("sentence_id")), *_str_list(claim.get("sentence_ids")), *_str_list(evidence.get("sentence_ids"))]


def _claim_source_ids(claim: dict[str, Any]) -> list[str]:
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    return [*_str_list(claim.get("source_id")), *_str_list(claim.get("source_ids")), *_str_list(evidence.get("source_id")), *_str_list(evidence.get("source_ids"))]


def _citation_payload(matched_chunks: list[dict[str, Any]], matched_claims: list[dict[str, Any]]) -> dict[str, Any]:
    claim_ids = [_text(item.get("claim_id")) for item in matched_claims if _text(item.get("claim_id"))]
    sentence_ids = [sentence_id for claim in matched_claims for sentence_id in _claim_sentence_ids(claim)]
    source_ids = [
        *[source_id for claim in matched_claims for source_id in _claim_source_ids(claim)],
        *[source_id for chunk in matched_chunks for source_id in _str_list(chunk.get("source_ids"))],
    ]
    evidence_ids = [
        *claim_ids,
        *sentence_ids,
        *[
            _text(evidence_id)
            for chunk in matched_chunks
            for evidence_id in chunk.get("evidence_ids") or []
            if _text(evidence_id)
        ],
    ]
    evidence_debug = []
    for claim in matched_claims:
        claim_id = _text(claim.get("claim_id"))
        claim_sentence_ids = _claim_sentence_ids(claim) or [""]
        claim_source_ids = _claim_source_ids(claim) or [""]
        for sentence_id in claim_sentence_ids:
            for source_id in claim_source_ids:
                evidence_debug.append({"claim_id": claim_id, "sentence_id": sentence_id, "source_id": source_id})
    return {
        "cited_claim_ids": list(dict.fromkeys(claim_ids)),
        "cited_evidence_ids": list(dict.fromkeys(evidence_ids)),
        "cited_sentence_ids": list(dict.fromkeys(sentence_ids)),
        "cited_source_ids": list(dict.fromkeys(source_ids)),
        "source_ids": list(dict.fromkeys(source_ids)),
        "evidence_debug": evidence_debug,
    }


def _fact_subject_name(name: str) -> str:
    tokens = [token for token in name.split() if token]
    if len(tokens) >= 2 and all(token[:1].isupper() for token in tokens):
        return name
    return _article_name(name)


def _claim_state(claim: dict[str, Any]) -> str:
    return _text(claim.get("state")).lower()


def _is_state_claim(claim: dict[str, Any]) -> bool:
    return _claim_state(claim) in {"active", "inactive"}


def _time_markers(claim: dict[str, Any]) -> set[str]:
    return {
        _text(claim.get("time_filter")).lower(),
        _text(claim.get("fact_bucket")).lower(),
        _text(claim.get("time_mode")).lower(),
        _text(claim.get("time_dominant")).lower(),
        _text(claim.get("status")).lower(),
    } - {""}


def _is_historical_claim(claim: dict[str, Any]) -> bool:
    return bool(_time_markers(claim).intersection({"historical", "bounded", "past"}))


def _is_current_claim(claim: dict[str, Any]) -> bool:
    markers = _time_markers(claim)
    if _is_historical_claim(claim):
        return False
    if markers.intersection({"current", "active", "present"}):
        return True
    return _is_state_claim(claim)


def _current_state_claims(matched_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in matched_claims if _is_state_claim(item) and _is_current_claim(item)]


def _historical_state_claims(matched_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in matched_claims if _is_state_claim(item) and _is_historical_claim(item)]


def _unique_states(claims: list[dict[str, Any]]) -> list[str]:
    states: list[str] = []
    for claim in claims:
        state = _claim_state(claim)
        if state and state not in states:
            states.append(state)
    return states


def _clean_historical_text(value: str) -> str:
    text = " ".join(_text(value).split())
    if not text:
        return ""
    for marker in (", currently", " currently", "currently "):
        text = text.replace(marker, " ")
    return " ".join(text.split(" ,")).strip(" ,.")


def _historical_state_text(claim: dict[str, Any]) -> str:
    claim_text = _clean_historical_text(_text(claim.get("claim_text")))
    if claim_text:
        return claim_text
    state = _claim_state(claim)
    return _clean_historical_text(state)


def _historical_phrase(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return ""
    state_text = _historical_state_text(claims[0])
    return f"Historically, it was {state_text}." if state_text else ""


def _relation_claims(matched_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for claim in matched_claims:
        predicate = _text(claim.get("predicate")).lower()
        bucket = _text(claim.get("fact_bucket")).lower()
        if bucket == "relations" or predicate in {"uses", "use", "használ", "hasznal", "utiliza", "usa", "integrates", "integrates with"}:
            out.append(claim)
    return out


def _bucket_claims(matched_claims: list[dict[str, Any]], bucket: str, group: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for claim in matched_claims:
        if _text(claim.get("fact_bucket")).lower() == bucket or _text(claim.get("claim_group")).lower() == group:
            out.append(claim)
    return out


def _predicate_object_sentence(entity_name: str, claim: dict[str, Any]) -> str:
    predicate = _text(claim.get("predicate"))
    obj = _text(claim.get("object"))
    canonical_rule = _canonical_rule_object(claim)
    if canonical_rule:
        return f"{_fact_subject_name(entity_name)} must {canonical_rule}."
    if predicate and obj:
        return f"{_fact_subject_name(entity_name)} {predicate} {obj}."
    claim_text = _text(claim.get("claim_text")).rstrip(".")
    return f"{_article_name(claim_text)}." if claim_text else ""


def _rule_object_for_answer(entity_name: str, claim: dict[str, Any]) -> str:
    canonical_rule = _canonical_rule_object(claim)
    if canonical_rule:
        return canonical_rule
    obj = _text(claim.get("object"))
    if obj:
        return obj
    claim_text = _text(claim.get("claim_text")).rstrip(".")
    subject = _text(claim.get("subject")) or entity_name
    if subject and claim_text.lower().startswith(subject.lower()):
        claim_text = claim_text[len(subject):].strip()
    for prefix in ("must ", "should ", "required to ", "kötelező ", "kell ", "debe "):
        if claim_text.lower().startswith(prefix):
            return claim_text[len(prefix):].strip()
    return claim_text


def _rule_sentence(entity_name: str, claim: dict[str, Any]) -> str:
    rule_object = _rule_object_for_answer(entity_name, claim)
    if not rule_object:
        return ""
    return f"{_fact_subject_name(entity_name)} must {rule_object}."


def _canonical_rule_object(claim: dict[str, Any]) -> str | None:
    bucket = _text(claim.get("fact_bucket")).lower()
    group = _text(claim.get("claim_group")).lower()
    predicate = fold_text(_text(claim.get("predicate")))
    if bucket != "rules" and group != "rule" and predicate not in {"must", "should", "required", "kotelezo", "kötelező", "kell", "debe"}:
        return None
    text = fold_text(" ".join([_text(claim.get("predicate")), _text(claim.get("object")), _text(claim.get("claim_text"))]))
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
    return None


def _relation_sentence(entity_name: str, claim: dict[str, Any]) -> str:
    return _predicate_object_sentence(entity_name, claim)


def _state_answer(name: str, matched_chunks: list[dict[str, Any]], matched_claims: list[dict[str, Any]]) -> tuple[list[str], str]:
    current_claims = _current_state_claims(matched_claims)
    historical_claims = _historical_state_claims(matched_claims)
    current_states = _unique_states(current_claims)
    conflict = any(bool(item.get("conflict_marker")) for item in matched_chunks) or len(current_states) > 1
    sentences: list[str] = []
    mode = "no_answer"

    if conflict and {"active", "inactive"}.issubset(set(current_states)):
        sentences.append(
            f"{_article_name(name)} has conflicting current status information: "
            "one source says it is active, another says it is inactive."
        )
        mode = "conflict"
    elif current_states:
        sentences.append(f"{_article_name(name)} is currently {current_states[0]}.")
        mode = "direct"

    historical = _historical_phrase(historical_claims)
    if historical:
        sentences.append(historical)
        if mode == "direct":
            mode = "state_with_history"
        elif mode == "no_answer":
            mode = "historical"
    return sentences, mode


def _relation_answer(name: str, matched_claims: list[dict[str, Any]]) -> tuple[list[str], str]:
    claims = _relation_claims(matched_claims)
    if not claims:
        return [], "no_answer"
    answer = _relation_sentence(name, claims[0])
    return ([answer] if answer else []), "direct" if answer else "no_answer"


def _rule_answer(name: str, matched_claims: list[dict[str, Any]]) -> tuple[list[str], str]:
    claims = _bucket_claims(matched_claims, "rules", "rule")
    if not claims:
        return [], "no_answer"
    answer = _rule_sentence(name, claims[0])
    return ([answer] if answer else []), "direct" if answer else "no_answer"


def _descriptor_answer(name: str, matched_claims: list[dict[str, Any]]) -> tuple[list[str], str]:
    claims = _bucket_claims(matched_claims, "descriptors", "descriptor") or _relation_claims(matched_claims)
    if not claims:
        return [], "no_answer"
    answer = _predicate_object_sentence(name, claims[0])
    return ([answer] if answer else []), "direct" if answer else "no_answer"


def _event_answer(name: str, matched_claims: list[dict[str, Any]]) -> tuple[list[str], str]:
    claims = _bucket_claims(matched_claims, "events", "event")
    if not claims:
        return [], "no_answer"
    answer = _predicate_object_sentence(name, claims[0])
    return ([answer] if answer else []), "direct" if answer else "no_answer"


def _fallback_summary_answer(name: str, matched_claims: list[dict[str, Any]]) -> tuple[list[str], str]:
    if not matched_claims:
        return ["I found related information, but not a direct answer to the question."], "summary"
    claim = matched_claims[0]
    answer = _predicate_object_sentence(name, claim)
    if answer:
        return [answer], "summary"
    claim_text = _text(claim.get("claim_text")).rstrip(".")
    if claim_text:
        return [f"{_article_name(claim_text)}."], "summary"
    return ["I found related information, but not a direct answer to the question."], "summary"


class SynthesisEngineV0:
    version = SYNTHESIS_ENGINE_VERSION

    def synthesize(
        self,
        *,
        query_profile: dict[str, Any],
        matched_chunks: list[dict[str, Any]],
        matched_claims: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not matched_chunks:
            return _no_answer_result(version=self.version)

        matched_chunks, matched_claims, entity_matches = _filter_to_query_entity(query_profile, matched_chunks, matched_claims)
        if not entity_matches:
            return _no_answer_result(
                version=self.version,
                synthesis_debug={
                    "routed_intent": _text(query_profile.get("intent")).lower() or "unknown",
                    "entity_guard": "explicit_entity_mismatch",
                    "query_entity": _text(query_profile.get("entity")),
                },
            )

        name = _entity_name(query_profile, matched_chunks, matched_claims)
        intent = _text(query_profile.get("intent")).lower()
        current_claims = _current_state_claims(matched_claims)
        historical_claims = _historical_state_claims(matched_claims)
        synthesis_debug = {
            "routed_intent": intent or "unknown",
            "current_facts_count": len(current_claims),
            "historical_facts_count": len(historical_claims),
            "raw_matched_claims": matched_claims,
        }
        logger.info("knowledge.synthesis.debug", extra={"knowledge_synthesis": synthesis_debug})
        citations = _citation_payload(matched_chunks, matched_claims)
        synthesis_debug["evidence"] = citations["evidence_debug"]

        if intent == "state":
            sentences, mode = _state_answer(name, matched_chunks, matched_claims)
        elif intent == "relation":
            sentences, mode = _relation_answer(name, matched_claims)
        elif intent == "rule":
            sentences, mode = _rule_answer(name, matched_claims)
        elif intent == "descriptor":
            sentences, mode = _descriptor_answer(name, matched_claims)
        elif intent == "event":
            sentences, mode = _event_answer(name, matched_claims)
        else:
            sentences, mode = _fallback_summary_answer(name, matched_claims)

        if not sentences:
            sentences, mode = _fallback_summary_answer(name, matched_claims)
        answer = " ".join(sentences)
        if (
            mode != "no_answer"
            and answer
            and (
                not citations["cited_claim_ids"]
                or not citations["cited_sentence_ids"]
                or not citations["cited_source_ids"]
            )
        ):
            missing = []
            if not citations["cited_claim_ids"]:
                missing.append("claim_id")
            if not citations["cited_sentence_ids"]:
                missing.append("sentence_id")
            if not citations["cited_source_ids"]:
                missing.append("source_id")
            synthesis_debug["evidence_guard"] = "missing_" + "_".join(missing)
            return _no_answer_result(version=self.version, synthesis_debug=synthesis_debug)

        confidence = 0.55
        intent_claims = {
            "relation": _relation_claims(matched_claims),
            "rule": _bucket_claims(matched_claims, "rules", "rule"),
            "event": _bucket_claims(matched_claims, "events", "event"),
            "descriptor": _bucket_claims(matched_claims, "descriptors", "descriptor"),
        }.get(intent, [])
        if current_claims or historical_claims or intent_claims:
            confidence += 0.2
        conflict = any(bool(item.get("conflict_marker")) for item in matched_chunks)
        if conflict:
            confidence = min(confidence, 0.72)
        if citations["cited_claim_ids"]:
            confidence += 0.05

        return {
            "answer_text": answer,
            "answer_mode": mode,
            "cited_claim_ids": citations["cited_claim_ids"],
            "cited_evidence_ids": citations["cited_evidence_ids"],
            "cited_sentence_ids": citations["cited_sentence_ids"],
            "cited_source_ids": citations["cited_source_ids"],
            "source_ids": citations["source_ids"],
            "evidence_summary": citations["evidence_debug"],
            "synthesis_confidence": round(max(0.0, min(confidence, 0.95)), 4),
            "synthesis_debug": synthesis_debug,
            "builder_version": self.version,
        }


__all__ = ["SYNTHESIS_ENGINE_VERSION", "SynthesisEngineV0"]
