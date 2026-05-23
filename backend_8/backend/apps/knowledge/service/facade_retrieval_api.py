from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class RetrievalFacadeMixin:
    async def retrieve(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        compare_mode: bool = False,
    ) -> QueryRun:
        return await self._retrieval_service.retrieve(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            compare_mode=compare_mode,
        )

    async def build_chat_context(
        self,
        *,
        tenant: str | None = None,
        corpus_uuid: str | None = None,
        query: str | None = None,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        question: str | None = None,
        kb_uuid: str | None = None,
        current_user_id: int | None = None,
        current_user_role: str | None = None,
        parsed_query: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        return await self._retrieval_service.build_chat_context(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            question=question,
            kb_uuid=kb_uuid,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
            parsed_query=parsed_query,
            debug=debug,
        )

    async def answer_support(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._retrieval_service.answer_support(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
        )

    def get_metrics(self) -> dict[str, object]:
        return self._metrics_store.snapshot()


__all__ = ["RetrievalFacadeMixin"]
