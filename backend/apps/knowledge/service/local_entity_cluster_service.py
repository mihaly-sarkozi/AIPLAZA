from __future__ import annotations

import logging
import uuid as uuid_lib
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.source import Source
from apps.knowledge.service.language_rules import resolve_language

logger = logging.getLogger(__name__)


class LocalEntityClusterService:
    def __init__(
        self,
        *,
        resolver: Any,
        repository: Any | None,
        is_missing_table_error: Callable[..., bool],
    ) -> None:
        self._resolver = resolver
        self._repository = repository
        self._is_missing_table_error = is_missing_table_error

    def resolve_and_persist(
        self,
        *,
        run: InterpretationRun,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        mentions: list[Mention],
        claims: list[Claim],
    ) -> tuple[list[LocalEntityCluster], dict[str, Any]]:
        run_uuid = _uuid_or_none(run.id)
        source_uuid = _uuid_or_none(source.id)
        source_language = (
            document.language
            or getattr(source, "language", None)
            or resolve_language(text=sentences[0].text_content if sentences else None)
        )
        local_clusters, local_resolver_trace = self._resolver.resolve_with_trace(
            run_uuid,
            source_uuid,
            sentences,
            mentions,
            claims,
            language=source_language,
        )
        logger.debug(
            "[LOCAL RESOLVER V1]\ninterpretation_run_id=%s\ncluster_count=%s\nclaim_count=%s",
            run.id,
            len(local_clusters),
            len(claims),
        )
        self._persist_clusters(
            run=run,
            source=source,
            document=document,
            run_uuid=run_uuid,
            source_uuid=source_uuid,
            local_clusters=local_clusters,
        )
        return local_clusters, local_resolver_trace

    def _persist_clusters(
        self,
        *,
        run: InterpretationRun,
        source: Source,
        document: Document,
        run_uuid: uuid_lib.UUID | None,
        source_uuid: uuid_lib.UUID | None,
        local_clusters: list[LocalEntityCluster],
    ) -> None:
        if self._repository is None:
            return
        try:
            if run_uuid is not None:
                self._repository.delete_by_run(run_uuid)
            elif source_uuid is not None:
                self._repository.delete_by_source(source_uuid)
            if local_clusters:
                self._repository.save_many(local_clusters)
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc, "knowledge_local_entity_clusters"):
                logger.warning(
                    "knowledge.local_entity_clusters.skip_missing_table",
                    extra={
                        "document_id": document.id,
                        "interpretation_run_id": run.id,
                        "source_id": source.id,
                    },
                )
                return
            raise


def _uuid_or_none(value: Any) -> uuid_lib.UUID | None:
    if not value:
        return None
    try:
        return uuid_lib.UUID(str(value))
    except (TypeError, ValueError):
        return None


__all__ = ["LocalEntityClusterService"]
