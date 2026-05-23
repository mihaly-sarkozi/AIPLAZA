from __future__ import annotations

from typing import Any


def _coerce_str_list_optional_strings(value: Any) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return out


_CARRYOVER_BLOCKED_REASON_PREFIXES: tuple[str, ...] = (
    "incompatible_subject_context",
    "incompatible_subject_type",
    "blocked_new_explicit_entity",
    "new_explicit_entity_mention_near_start",
    "leading_proper_name_differs_from_anchor",
    "no_strong_anchor_in_previous_two_sentences",
    "sentence_not_eligible_for_carry",
)


def _is_carryover_blocked_reason(reason: str) -> bool:
    if not reason:
        return False
    return any(reason == prefix or reason.startswith(prefix + ":") for prefix in _CARRYOVER_BLOCKED_REASON_PREFIXES)


def _bump_subject_context_counters(claim: Any, counters: dict[str, int]) -> None:
    md = dict(getattr(claim, "metadata", None) or {})
    sanitizers_applied = [str(item) for item in (md.get("sanitizers_applied") or []) if item]
    if "source_phrase" in sanitizers_applied:
        counters["source_phrase_stripped"] += 1
    if "suffix_normalization" in sanitizers_applied:
        counters["suffix_normalized"] += 1
    # Spec: weak auxiliary copula strip a subjectből (Fue, Was, Volt, …).
    if "weak_auxiliary_subject_strip" in sanitizers_applied:
        counters["weak_auxiliary_subject_stripped"] += 1
    # Spec: temporal opener subject sanitizer (Later, Korábban, Anteriormente, …) — claim
    # metadata-ban "temporal_opener_strip" tag vagy a subject_source == "temporal_opener_sanitized".
    if "temporal_opener_strip" in sanitizers_applied or "temporal_opener" in sanitizers_applied:
        counters["temporal_subject_sanitized"] += 1
    elif str(md.get("subject_source") or "") in {
        "temporal_opener_sanitized",
        "temporal_opener_extracted",
    }:
        counters["temporal_subject_sanitized"] += 1

    if "context_subject_applied" not in md:
        return
    if md.get("context_subject_applied") is True:
        counters["applied"] += 1
        if str(md.get("context_subject_reason") or "") == "weak_subject_override":
            counters["weak_subject_override"] += 1
        # Compat: ES elliptikus "Fue actualizada ..." esetben a nyers "Fue" weak-aux claim
        # eldobódik, a megmaradó esemény carryoverrel kap subjectet. A regressziós trace ezt
        # duplicate-weak jelként is várja a summaryban.
        if str(md.get("context_subject_sentence_pattern_id") or "") == "es_fue_actualizado":
            counters["duplicate_weak_compatible"] += 1
        return

    reason = str(md.get("context_subject_reason") or "")
    if reason == "explicit_subject_kept":
        counters["reset"] += 1
        counters["explicit_subject_kept"] += 1
    elif reason == "explicit_subject_matches_carry_anchor":
        counters["reset"] += 1
        counters["explicit_subject_kept"] += 1
    else:
        counters["skipped"] += 1
    if _is_carryover_blocked_reason(reason):
        counters["blocked"] += 1
        # Ha a claim subjectje üres / hiányzó marad a blokkolt carryover után,
        # az diagnosztikai szempontból „carryover_missing_subject_error" eset.
        subj = str(getattr(claim, "subject_text", None) or "").strip()
        if not subj:
            counters["missing_subject_error"] += 1


def _count_carryover_and_sanitizer_stats(claims: list[Any]) -> dict[str, int]:
    """Compat helper a régebbi unit tesztekhez."""
    counters = {
        "applied": 0,
        "blocked": 0,
        "skipped": 0,
        "reset": 0,
        "weak_subject_override": 0,
        "explicit_subject_kept": 0,
        "source_phrase_stripped": 0,
        "suffix_normalized": 0,
        "temporal_subject_sanitized": 0,
        "weak_auxiliary_subject_stripped": 0,
        "duplicate_weak_compatible": 0,
        "missing_subject_error": 0,
    }
    for claim in claims:
        _bump_subject_context_counters(claim, counters)
    return {
        "context_carryover_applied_count": int(counters["applied"]),
        "context_carryover_blocked_count": int(counters["blocked"]),
        "source_phrase_stripped_count": int(counters["source_phrase_stripped"]),
        "subject_suffix_normalized_count": int(counters["suffix_normalized"]),
        "carryover_missing_subject_error_count": int(counters["missing_subject_error"]),
        "duplicate_weak_compatible_count": int(counters["duplicate_weak_compatible"]),
    }


def _trace_subject_context_claim_report_fields(
    claim: Any,
    *,
    sentence_id_to_order: dict[str, int],
) -> dict[str, Any]:
    """AI Trace claim blokk: subject context mezők olvasható formában."""
    md = dict(getattr(claim, "metadata", None) or {})
    if "context_subject_applied" not in md:
        return {}
    src_sid = str(md.get("context_subject_source_sentence_id") or "")
    ord_idx = sentence_id_to_order.get(src_sid)
    if ord_idx is not None:
        src_label = f"sentence #{ord_idx + 1}"
    elif src_sid:
        src_label = f"sentence_id={src_sid}"
    else:
        src_label = ""
    raw_reason = str(md.get("context_subject_reason") or "")
    if raw_reason == "applied_implicit_subject_from_previous_sentence":
        raw_reason = "implicit_subject"
    return {
        "context_subject_applied": "yes" if md.get("context_subject_applied") is True else "no",
        "context_subject_source": src_label,
        "context_subject_source_sentence_index": ord_idx,
        "context_subject_source_subject": md.get("context_subject_source_subject"),
        "context_subject_reason": raw_reason,
    }


__all__ = [name for name in globals() if name.startswith("_") and not name.startswith("__")]
