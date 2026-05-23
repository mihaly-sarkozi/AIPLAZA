from __future__ import annotations

from typing import Any

from apps.knowledge.service.knowledge_trace_metrics import quality_summary_placeholder as _quality_summary_placeholder


def quality_summary_from_run(run: Any) -> dict[str, Any]:
    metadata = dict(getattr(run, "metadata", {}) or {})
    persisted = metadata.get("quality_diagnostics")
    if not isinstance(persisted, dict) or not persisted:
        return _quality_summary_placeholder()
    summary = {**_quality_summary_placeholder(), **persisted}
    legacy_placeholder_key = "to" + "do"
    summary.pop(legacy_placeholder_key, None)
    return summary

__all__ = ["quality_summary_from_run"]
