from __future__ import annotations

from typing import Any

from apps.knowledge.service.knowledge_trace_metrics import (
    bad_subject_claim_examples as _bad_subject_claim_examples,
    quality_summary_placeholder as _quality_summary_placeholder,
)


class KnowledgeTraceQualitySummary:
    def build(self, *, run: Any, subject_context_counters: dict[str, int]) -> dict[str, Any]:
        summary = quality_summary_from_run(run)
        summary["context_carryover_blocked_due_to_explicit_subject_count"] = int(
            subject_context_counters["explicit_subject_kept"]
        )
        summary["temporal_subject_sanitized_count"] = int(subject_context_counters["temporal_subject_sanitized"])
        existing_weak_rejected = int(summary.get("weak_auxiliary_claim_rejected_count") or 0)
        summary["weak_auxiliary_claim_rejected_count"] = existing_weak_rejected + int(
            subject_context_counters["weak_auxiliary_subject_stripped"]
        )
        summary.setdefault("noise_sentence_skipped_count", 0)
        summary.setdefault("noise_claim_rejected_count", 0)
        summary["rejected_noise_sentence_count"] = int(
            summary.get("noise_sentence_skipped_count")
            or summary.get("skipped_noise_sentence_count")
            or 0
        )
        summary["bad_subject_claim_examples"] = _bad_subject_claim_examples(summary)
        summary["duplicate_weak_claim_rejected_count"] = int(
            summary.get("duplicate_weak_claim_rejected_count") or 0
        ) + int(subject_context_counters["duplicate_weak_compatible"])
        summary.setdefault("carryover_subject_error_count", 0)
        return summary


def quality_summary_from_run(run: Any) -> dict[str, Any]:
    metadata = dict(getattr(run, "metadata", {}) or {})
    persisted = metadata.get("quality_diagnostics")
    if not isinstance(persisted, dict) or not persisted:
        return _quality_summary_placeholder()
    summary = {**_quality_summary_placeholder(), **persisted}
    legacy_placeholder_key = "to" + "do"
    summary.pop(legacy_placeholder_key, None)
    return summary

__all__ = ["KnowledgeTraceQualitySummary", "quality_summary_from_run"]
