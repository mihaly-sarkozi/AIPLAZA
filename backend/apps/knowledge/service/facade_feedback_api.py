from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class FeedbackFacadeMixin:
    def apply_knowledge_feedback(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        target_entity: str,
        claim_text: str,
        feedback_type: str,
        optional_new_claim: str | None = None,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        return self._knowledge_feedback_service.apply(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            target_entity=target_entity,
            claim_text=claim_text,
            feedback_type=feedback_type,
            optional_new_claim=optional_new_claim,
            user_input=user_input,
            user_id=user_id,
        )

    def withdraw_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        source_id: str,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        return self._knowledge_feedback_service.withdraw_source(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            source_id=source_id,
            user_input=user_input,
            user_id=user_id,
        )

    def get_lineage(
        self,
        *,
        corpus_uuid: str,
        claim_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        return self._lineage_service.get_lineage(
            corpus_uuid=corpus_uuid,
            claim_id=claim_id,
            profile_id=profile_id,
        )

    def get_quality_report(self, *, corpus_uuid: str) -> dict[str, Any]:
        return self._report_service.get_quality_report(corpus_uuid=corpus_uuid)


__all__ = ["FeedbackFacadeMixin"]
