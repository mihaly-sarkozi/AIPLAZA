from __future__ import annotations

import re

from apps.knowledge.domain.query_profile import QUERY_RESOLVER_VERSION, QueryProfile
from apps.knowledge.service.language_rules import detect_language, fold_text
from shared.text.language_lexicon import get_lexicon_terms


def _contains_any(folded: str, markers: tuple[str, ...]) -> bool:
    return any(fold_text(marker) in folded for marker in markers)


def _lexicon_terms(language: str | None, key: str) -> tuple[str, ...]:
    values = []
    for item in get_lexicon_terms(language, key):
        folded = fold_text(item)
        if folded and folded not in values:
            values.append(folded)
    return tuple(values)


def _state_from_query(folded: str) -> str | None:
    if re.search(r"\binactive\b|\binaktiv\b|\binaktív\b|\binactivo\b", folded):
        return "inactive"
    if re.search(r"\bactive\b|\baktiv\b|\baktív\b|\bactivo\b", folded):
        return "active"
    return None


def _intent_from_query(folded: str, *, language: str | None) -> tuple[str, str]:
    if re.search(r"\bapply(?:ies)?\s+to\b", folded):
        return "descriptor", "intent:descriptor_apply_to_marker"
    if re.search(r"\bwhat\s+does\b.+\bdescribe\b", folded):
        return "descriptor", "intent:descriptor_describe_marker"
    if re.search(r"\bwhat\s+is\b.+\bpolicy\b", folded):
        return "descriptor", "intent:descriptor_what_is_policy_marker"
    if re.search(r"\bwhat\s+happened\s+to\b", folded) or re.search(r"\bwhen\s+did\b.+\bhappen\b", folded):
        return "event", "intent:event_question_marker"
    if _contains_any(folded, _lexicon_terms(language, "state_markers")):
        return "state", "intent:state_marker"
    if _contains_any(folded, _lexicon_terms(language, "rule_markers")):
        return "rule", "intent:rule_marker"
    if _contains_any(folded, _lexicon_terms(language, "event_markers")):
        return "event", "intent:event_marker"
    if _contains_any(folded, _lexicon_terms(language, "relation_markers")):
        return "relation", "intent:relation_marker"
    if _contains_any(folded, _lexicon_terms(language, "descriptor_markers")):
        return "descriptor", "intent:descriptor_marker"
    return "unknown", "intent:unknown"


def _expected_answer_type_from_query(folded: str, *, language: str | None) -> tuple[str | None, str | None]:
    location_words = _lexicon_terms(language, "answer_type_location_words")
    if location_words and any(re.search(rf"\b{re.escape(word)}\b", folded) for word in location_words):
        return "location", "answer_type:location_question"
    time_words = _lexicon_terms(language, "answer_type_time_words")
    if time_words and any(re.search(rf"\b{re.escape(word)}\b", folded) for word in time_words):
        return "time", "answer_type:time_question"
    person_words = _lexicon_terms(language, "answer_type_person_words")
    if person_words and any(re.search(rf"\b{re.escape(word)}\b", folded) for word in person_words):
        return "person", "answer_type:person_question"
    explanation_words = _lexicon_terms(language, "answer_type_explanation_words")
    if explanation_words and any(re.search(rf"\b{re.escape(word)}\b", folded) for word in explanation_words):
        return "explanation", "answer_type:explanation_question"
    object_words = _lexicon_terms(language, "answer_type_object_words")
    if object_words and any(re.search(rf"\b{re.escape(word)}\b", folded) for word in object_words):
        return "object", "answer_type:object_question"
    return None, None


def _relation_predicate_from_query(folded: str, intent: str) -> str | None:
    if intent != "relation":
        return None
    if re.search(r"\b(use|uses|using|haszn[aá]l|utiliza|usa)\b", folded):
        return "uses"
    if re.search(r"\b(integrates|integrated|integrate|integra|kapcsol[oó]dik)\b", folded):
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


def _time_filter(
    folded: str,
    *,
    intent: str,
    state: str | None,
    language: str | None,
) -> tuple[str | None, str]:
    if intent == "event":
        return "event_time", "time:event_time"
    if "status of" in folded or "status for" in folded:
        return None, "time:no_forced_filter_status_question"
    if _contains_any(folded, _lexicon_terms(language, "historical_markers")):
        return "historical", "time:historical_marker"
    if _contains_any(folded, _lexicon_terms(language, "current_markers")):
        return "current", "time:current_marker"
    if intent == "state" and state and folded.startswith("which "):
        return "current", "time:state_listing_defaults_current"
    return None, "time:no_forced_filter"


def _entity_type(folded: str, *, language: str | None) -> tuple[str | None, str | None]:
    if any(re.search(rf"\b{re.escape(qualifier)}\b", folded) for qualifier in _lexicon_terms(language, "location_qualifiers")):
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


def _keywords(query: str, entity: str | None, state: str | None, intent: str, *, language: str | None) -> list[str]:
    values: list[str] = []
    stopwords = set(_lexicon_terms(language, "question_stopwords"))
    stopwords.update({"kapcsolatban", "kapcslatban", "kapcsan", "kapcsán", "there"})
    for source in (query, entity or "", state or "", intent if intent != "unknown" else ""):
        for token in re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]+", source):
            folded = fold_text(token)
            if not folded or folded in stopwords or len(folded) <= 1:
                continue
            for keyword in _keyword_variants(folded, language=language):
                if keyword and keyword not in stopwords and len(keyword) > 1 and keyword not in values:
                    values.append(keyword)
    return values


def _keyword_variants(folded: str, *, language: str | None) -> list[str]:
    variants = [folded]
    # Gyakori magyar elgépelés: "nyugdijjakal" -> "nyugdijakal" -> "nyugdij".
    repaired = re.sub(r"ijj(?=[a-z]|$)", "ij", folded)
    if repaired not in variants:
        variants.append(repaired)
    suffixes = list(_lexicon_terms(language, "entity_suffixes"))
    for hu_suffix in _lexicon_terms("hu", "entity_suffixes"):
        if hu_suffix not in suffixes:
            suffixes.append(hu_suffix)
    for candidate in list(variants):
        for suffix in suffixes:
            if candidate.endswith(suffix) and len(candidate) > len(suffix) + 2:
                stem = candidate[: -len(suffix)]
                if stem not in variants:
                    variants.append(stem)
                break
    return variants


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
        language = detect_language(raw_query)
        reasons: list[str] = []
        reasons.append(f"language:{language}")
        intent, intent_reason = _intent_from_query(folded, language=language)
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
        expected_answer_type, answer_type_reason = _expected_answer_type_from_query(folded, language=language)
        if answer_type_reason:
            reasons.append(answer_type_reason)
        state = _state_from_query(folded)
        if state:
            reasons.append(f"state:{state}")
        time_filter, time_reason = _time_filter(
            folded,
            intent=intent,
            state=state,
            language=language,
        )
        reasons.append(time_reason)
        entity_type, entity_type_reason = _entity_type(folded, language=language)
        if entity_type_reason:
            reasons.append(entity_type_reason)
        entity, detected_entities = _detected_entity(raw_query, entity_type)
        detected_entities = [*detected_entities, *relation_object_entities]
        if entity:
            reasons.append("entity:explicit_query_entity")
        keywords = _keywords(
            raw_query,
            " ".join(part for part in [entity or "", relation_object or ""] if part),
            state,
            intent,
            language=language,
        )
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
