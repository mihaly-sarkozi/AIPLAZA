# backend/apps/knowledge/service/knowledge_report_service.py
# Owns quality report assembly for knowledge global profiles.

from __future__ import annotations

from typing import Any

from apps.knowledge.service.knowledge_quality_report_v0 import KnowledgeQualityReportV0


class KnowledgeReportService:
    def __init__(self, facade: Any) -> None:
        self._facade = facade

    def __getattr__(self, name: str) -> Any:
        return getattr(self._facade, name)

    def get_quality_report(self, *, corpus_uuid: str) -> dict[str, Any]:
        global_profiles = self._load_existing_global_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        global_profiles, feedback_events = self._knowledge_feedback_service.apply_feedback_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        global_profiles, source_withdrawal_events = self._knowledge_feedback_service.apply_source_withdrawals_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        report = KnowledgeQualityReportV0().build(corpus_uuid=corpus_uuid, global_profiles=global_profiles)
        report["feedback_events"] = feedback_events
        report["source_withdrawal_events"] = source_withdrawal_events
        return report


__all__ = ["KnowledgeReportService"]
