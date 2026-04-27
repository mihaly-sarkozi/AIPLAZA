from __future__ import annotations

import re

from apps.knowledge.domain.query_profile import QUERY_RESOLVER_VERSION, QueryProfile
from apps.knowledge.service.language_rules import fold_text


_STOPWORDS = {
    "a",
    "an",
    "are",
    "az",
    "do",
    "does",
    "for",
    "is",
    "of",
    "the",
    "there",
    "to",
    "was",
    "what",
    "which",
    "who",
}
_LOCATION_QUALIFIERS = ("office", "offices", "branch", "branches", "center", "centers", "site", "sites")
_CURRENT_MARKERS = ("current", "currently", "active now", "jelenleg", "most", "actualmente")
_HISTORICAL_MARKERS = ("was", "were", "previously", "historical", "in 20", "in 19", "korabban", "korábban", "anteriormente")
_STATE_MARKERS = ("status", "active", "inactive", "aktív", "inaktív", "activo", "inactivo")
_RELATION_MARKERS = ("use", "uses", "using", "integrate", "integrates", "integrated", "használ", "utiliza", "usa")
_RULE_MARKERS = ("must", "should", "required", "rule", "policy", "kell", "kötelező", "debe")
_EVENT_MARKERS = ("created", "updated", "completed", "happened", "happen", "deprecated", "changed", "launched", "megszűnt", "frissült")
_DESCRIPTOR_MARKERS = ("who is", "what is", "describe", "description", "lead", "responsible", "apply", "applies")


def _contains_any(folded: str, markers: tuple[str, ...]) -> bool:
    return any(fold_text(marker) in folded for marker in markers)


def _state_from_query(folded: str) -> str | None:
    if re.search(r"\binactive\b|\binaktiv\b|\binaktív\b|\binactivo\b", folded):
        return "inactive"
    if re.search(r"\bactive\b|\baktiv\b|\baktív\b|\bactivo\b", folded):
        return "active"
    return None


def _intent_from_query(folded: str) -> tuple[str, str]:
    if re.search(r"\bapply(?:ies)?\s+to\b", folded):
        return "descriptor", "intent:descriptor_apply_to_marker"
    if re.search(r"\bwhat\s+does\b.+\bdescribe\b", folded):
        return "descriptor", "intent:descriptor_describe_marker"
    if re.search(r"\bwhat\s+is\b.+\bpolicy\b", folded):
        return "descriptor", "intent:descriptor_what_is_policy_marker"
    if re.search(r"\bwhat\s+happened\s+to\b", folded) or re.search(r"\bwhen\s+did\b.+\bhappen\b", folded):
        return "event", "intent:event_question_marker"
    if _contains_any(folded, _STATE_MARKERS):
        return "state", "intent:state_marker"
    if _contains_any(folded, _RULE_MARKERS):
        return "rule", "intent:rule_marker"
    if _contains_any(folded, _EVENT_MARKERS):
        return "event", "intent:event_marker"
    if _contains_any(folded, _RELATION_MARKERS):
        return "relation", "intent:relation_marker"
    if _contains_any(folded, _DESCRIPTOR_MARKERS):
        return "descriptor", "intent:descriptor_marker"
    return "unknown", "intent:unknown"


def _expected_answer_type_from_query(folded: str) -> tuple[str | None, str | None]:
    if re.search(r"\bhol\b", folded):
        return "location", "answer_type:location_question"
    if re.search(r"\bmikor\b", folded):
        return "time", "answer_type:time_question"
    if re.search(r"\b(ki|kik)\b", folded):
        return "person", "answer_type:person_question"
    if re.search(r"\bmi[eé]rt\b", folded):
        return "explanation", "answer_type:explanation_question"
    if re.search(r"\bmit\b", folded):
        return "object", "answer_type:object_question"
    return None, None


def _relation_predicate_from_query(folded: str, intent: str) -> str | None:
    if intent != "relation":
        return None
    if re.search(r"\b(use|uses|using|haszn[aá]l|utiliza|usa)\b", folded):
        return "uses"
    if re.search(r"\b(integrates|integrated|integrate)\b", folded):
        return "integrates"
    return None


def _relation_object_from_query(query: str, intent: str) -> tuple[str | None, list[dict[str, str]]]:
    if intent != "relation":
        return None, []
    patterns = [
        r"\bwhich\s+(?:services|systems|modules|components)\s+(?:integrate|integrates)\s+with\s+([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,5})\??$",
        r"\bwhich\s+(?:services|systems|modules|components)\s+use\s+([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,5})\??$",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if not match:
            continue
        obj = match.group(1).strip(" ?.")
        obj = re.sub(r"^(the|a|an)\s+", "", obj, flags=re.IGNORECASE)
        return obj, [{"text": obj, "entity_type": "relation_object", "source": "query_relation_object_pattern"}]
    return None, []


def _rule_action_from_query(folded: str, intent: str) -> str | None:
    if intent != "rule":
        return None
    if re.search(r"\b(enable|activate)\b", folded):
        return "enable"
    if re.search(r"\brequired\s+to\s+do\b", folded):
        return "require"
    if re.search(r"\bdo\b", folded):
        return "do"
    return None


def _time_filter(folded: str, *, intent: str, state: str | None) -> tuple[str | None, str]:
    if intent == "event":
        return "event_time", "time:event_time"
    if "status of" in folded or "status for" in folded:
        return None, "time:no_forced_filter_status_question"
    if _contains_any(folded, _HISTORICAL_MARKERS):
        return "historical", "time:historical_marker"
    if _contains_any(folded, _CURRENT_MARKERS):
        return "current", "time:current_marker"
    if intent == "state" and state and folded.startswith("which "):
        return "current", "time:state_listing_defaults_current"
    return None, "time:no_forced_filter"


def _entity_type(folded: str) -> tuple[str | None, str | None]:
    if any(re.search(rf"\b{re.escape(qualifier)}\b", folded) for qualifier in _LOCATION_QUALIFIERS):
        return "location", "entity_type:location_qualifier"
    if any(token in folded for token in ("admin user", "user", "role", "usuario", "felhasználó", "felhasznalo")):
        return "user", "entity_type:user_keyword"
    if "policy" in folded:
        return "policy", "entity_type:policy_keyword"
    if any(token in folded for token in ("service", "services", "module", "modules", "workflow", "process", "review", "system", "systems", "component", "components")):
        return "system_component", "entity_type:technical_component_keyword"
    return None, None


def _detected_entity(query: str, entity_type: str | None) -> tuple[str | None, list[dict[str, str]]]:
    patterns = [
        r"\bwhat\s+does\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+(?:service|module|workflow|process|component|system))\s+(?:use|uses|using|integrate|integrates)\b",
        r"\bwhat\s+does\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+policy)\s+(?:apply\s+to|describe)\b",
        r"\bwhat\s+is\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+policy)\b",
        r"\bwhat\s+happened\s+to\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+(?:service|module|workflow|process|review|component|system|policy))\b",
        r"\bwhen\s+did\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+(?:service|module|workflow|process|review|component|system|policy))\s+happen\b",
        r"\bwhich\s+(?:system|service|module|component)\s+does\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+(?:service|module|workflow|process|component|system))\s+(?:use|integrate|integrates)\b",
        r"\bwhat\s+(?:must|should)\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+(?:user|role|service|module|workflow|process|component|system))\s+(?:enable|activate|use|do)\b",
        r"\bwhat\s+is\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+(?:user|role|service|module|workflow|process|component|system))\s+required\s+to\s+do\b",
        r"\bwhen\s+was\s+(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,4}?\s+(?:service|module|workflow|process|review|component|system))\s+(?:created|updated|completed|deprecated|replaced|migrated)\b",
        r"\b(?:who|what)\s+is\s+(?:the\s+)?([A-Z][A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,3})\b",
        r"\b(?:the\s+)?([A-Z][A-Za-z0-9_-]*(?:\s+[A-Za-z0-9_-]+){0,3}\s+(?:office|branch|center|site))\b",
        r"\b(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,3}\s+(?:service|module|workflow|process|review|component|system))\b",
        r"\b(?:the\s+)?([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,3}\s+(?:user|role))\b",
        r"\b(?:of|for)\s+([A-Z][A-Za-z0-9_-]*(?:\s+[A-Za-z0-9_-]+){0,3})\??$",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if not match:
            continue
        entity = match.group(1).strip(" ?.")
        entity = re.sub(r"^(what\s+does|what\s+must|what\s+should|status\s+of|was|were|is|are|what\s+is|which)\s+", "", entity, flags=re.IGNORECASE)
        entity = re.sub(r"^(the|a|an)\s+", "", entity, flags=re.IGNORECASE)
        return entity, [{"text": entity, "entity_type": entity_type or "unknown", "source": "query_pattern"}]
    return None, []


def _keywords(query: str, entity: str | None, state: str | None, intent: str) -> list[str]:
    values: list[str] = []
    for source in (query, entity or "", state or "", intent if intent != "unknown" else ""):
        for token in re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]+", source):
            folded = fold_text(token)
            if not folded or folded in _STOPWORDS or len(folded) <= 1:
                continue
            if folded not in values:
                values.append(folded)
    return values


def _confidence(
    *,
    entity_type: str | None,
    entity: str | None,
    intent: str,
    state: str | None,
    time_filter: str | None,
    keywords: list[str],
) -> float:
    score = 0.35
    if intent != "unknown":
        score += 0.2
    if entity_type:
        score += 0.15
    if entity:
        score += 0.1
    if state:
        score += 0.1
    if time_filter:
        score += 0.05
    if keywords:
        score += 0.05
    return round(min(score, 0.95), 4)


class QueryResolverV0:
    version = QUERY_RESOLVER_VERSION

    def resolve(self, query: str) -> QueryProfile:
        raw_query = str(query or "").strip()
        folded = fold_text(raw_query)
        reasons: list[str] = []
        intent, intent_reason = _intent_from_query(folded)
        reasons.append(intent_reason)
        relation_predicate = _relation_predicate_from_query(folded, intent)
        if relation_predicate:
            reasons.append(f"relation_predicate:{relation_predicate}")
        relation_object, relation_object_entities = _relation_object_from_query(raw_query, intent)
        if relation_object:
            reasons.append("relation_object:explicit_query_object")
        rule_action = _rule_action_from_query(folded, intent)
        if rule_action:
            reasons.append(f"rule_action:{rule_action}")
        expected_answer_type, answer_type_reason = _expected_answer_type_from_query(folded)
        if answer_type_reason:
            reasons.append(answer_type_reason)
        state = _state_from_query(folded)
        if state:
            reasons.append(f"state:{state}")
        time_filter, time_reason = _time_filter(folded, intent=intent, state=state)
        reasons.append(time_reason)
        entity_type, entity_type_reason = _entity_type(folded)
        if entity_type_reason:
            reasons.append(entity_type_reason)
        entity, detected_entities = _detected_entity(raw_query, entity_type)
        detected_entities = [*detected_entities, *relation_object_entities]
        if entity:
            reasons.append("entity:explicit_query_entity")
        keywords = _keywords(raw_query, " ".join(part for part in [entity or "", relation_object or ""] if part), state, intent)
        return QueryProfile(
            entity_type=entity_type,
            entity=entity,
            intent=intent,
            relation_predicate=relation_predicate,
            relation_object=relation_object,
            rule_action=rule_action,
            expected_answer_type=expected_answer_type,
            state=state,
            time_filter=time_filter,
            space_filter=entity if entity_type == "location" and entity else None,
            keywords=keywords,
            detected_entities=detected_entities,
            confidence=_confidence(
                entity_type=entity_type,
                entity=entity,
                intent=intent,
                state=state,
                time_filter=time_filter,
                keywords=keywords,
            ),
            reasons=reasons,
            builder_version=self.version,
        )


__all__ = ["QueryResolverV0"]
