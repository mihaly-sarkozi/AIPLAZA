from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.domain.query_run import QueryRun
from apps.knowledge.service.retrieval_service import RetrievalService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@dataclass(slots=True)
class _CorpusStore:
    corpus: Corpus | None

    def get_by_uuid(self, uuid: str) -> Corpus | None:
        if self.corpus is not None and self.corpus.uuid == uuid:
            return self.corpus
        return None


class _SourceStore:
    def get(self, source_id: str):  # type: ignore[no-untyped-def]
        return None


class _DocumentStore:
    def get_for_source(self, source_id: str):  # type: ignore[no-untyped-def]
        return None


def _corpus(*, tenant: str, uuid: str) -> Corpus:
    return Corpus(
        id=1,
        tenant=tenant,
        uuid=uuid,
        name=f"KB {uuid}",
        description=None,
        qdrant_collection_name=f"kb_{uuid}",
        created_at=None,
        updated_at=None,
    )


def _service(corpus: Corpus | None, calls: list[dict]) -> RetrievalService:
    async def _retrieve_query(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(dict(kwargs))
        return QueryRun(
            tenant=str(kwargs.get("tenant") or ""),
            corpus_uuid=str(kwargs.get("corpus_uuid") or ""),
            query=str(kwargs.get("query") or ""),
        )

    return RetrievalService(
        source_store=_SourceStore(),
        document_store=_DocumentStore(),
        corpus_store=_CorpusStore(corpus),
        retrieve_query=_retrieve_query,
        source_display_type=lambda _source: "",
        source_created_by_label=lambda _source: "",
    )


@pytest.mark.anyio
async def test_tenant_a_kb_does_not_enter_tenant_b_retrieval() -> None:
    calls: list[dict] = []
    service = _service(_corpus(tenant="tenant-a", uuid="kb-a"), calls)

    with pytest.raises(PermissionError):
        await service.build_chat_context(tenant="tenant-b", corpus_uuid="kb-a", query="hello")

    assert calls == []


@pytest.mark.anyio
async def test_retrieval_requires_explicit_tenant_scope() -> None:
    calls: list[dict] = []
    service = _service(_corpus(tenant="tenant-a", uuid="kb-a"), calls)

    with pytest.raises(PermissionError):
        await service.build_chat_context(tenant="", corpus_uuid="kb-a", query="hello")

    assert calls == []


@pytest.mark.anyio
async def test_retrieval_allows_matching_tenant_resource_scope() -> None:
    calls: list[dict] = []
    service = _service(_corpus(tenant="tenant-a", uuid="kb-a"), calls)

    packet = await service.build_chat_context(tenant="tenant-a", corpus_uuid="kb-a", query="hello")

    assert packet["kb_uuid"] == "kb-a"
    assert calls and calls[0]["tenant"] == "tenant-a"
