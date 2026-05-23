"""Claim kinyerés: pattern név és nyelv a trace / debug / riport számára."""
from __future__ import annotations

from typing import Any

from apps.knowledge.service.claim_extract_constants import USE_PREDICATE_FOLDS
from apps.knowledge.service.language_rules import fold_text


def infer_extraction_pattern_name(
    *,
    language: str,
    pred_f: str,
    subject_source: str,
    display_predicate: str,
    hu_hasznal_subject_end: int | None,
) -> str:
    """Stabil, gépiolvasható pattern azonosító (pl. ``hu_use_object_before_predicate``)."""
    lang = (language or "en").lower().split("-", maxsplit=1)[0]
    use_folds = USE_PREDICATE_FOLDS.get(lang, set())

    if lang == "hu":
        if pred_f in use_folds:
            if hu_hasznal_subject_end is not None:
                return "hu_use_object_before_predicate"
            if subject_source == "hu_use_head_heuristic":
                return "hu_use_head_subject"
            if subject_source == "mention":
                return "hu_use_subject_mention"
            if subject_source == "long_subject_rewrite":
                return "hu_use_long_subject_rewrite"
            if subject_source == "inherited":
                return "hu_use_inherited_subject"
            return "hu_use_fallback_subject"
        if pred_f == "vezetoje":
            return "hu_relation_vezetoje"
        if pred_f == "felelt":
            return "hu_relation_felelt"
        return "hu_v1_lexical_predicate"

    if lang == "en":
        if pred_f in use_folds:
            if subject_source == "mention":
                return "en_use_subject_mention"
            return "en_use_fallback_subject"
        p = fold_text(display_predicate)
        if "responsible" in p:
            return "en_responsible_predicate"
        return "en_v1_lexical_predicate"

    if lang == "es":
        if pred_f in use_folds:
            if subject_source == "mention":
                return "es_use_subject_mention"
            return "es_use_fallback_subject"
        if "responsable" in fold_text(display_predicate):
            return "es_responsable_predicate"
        return "es_v1_lexical_predicate"

    return f"{lang}_v1_lexical_predicate"


def attach_extraction_provenance(metadata: dict[str, Any], *, language: str, pattern_name: str) -> dict[str, Any]:
    """``pattern_name``, ``language``, trace-mezők (``extraction_*``)."""
    return {
        **metadata,
        "pattern_name": pattern_name,
        "language": language,
        "extraction_pattern": pattern_name,
        "extraction_language": language,
    }


__all__ = ["attach_extraction_provenance", "infer_extraction_pattern_name"]
