from __future__ import annotations

from apps.kb.kb_search.orm.SearchCitation import SearchCitation
from apps.kb.kb_search.orm.SearchContextBlock import SearchContextBlock
from apps.kb.kb_search.orm.SearchQueryResult import SearchQueryResult
from apps.kb.kb_search.orm.SearchQueryRun import SearchQueryRun
from apps.kb.kb_search.repository.SearchCitationRepository import SearchCitationRepository
from apps.kb.kb_search.repository.SearchContextBlockRepository import SearchContextBlockRepository
from apps.kb.kb_search.repository.SearchQueryResultRepository import SearchQueryResultRepository
from apps.kb.kb_search.repository.SearchQueryRunRepository import SearchQueryRunRepository
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class StoreSearchRunService:
    def __init__(
        self,
        *,
        run_repository: SearchQueryRunRepository,
        result_repository: SearchQueryResultRepository,
        context_block_repository: SearchContextBlockRepository,
        citation_repository: SearchCitationRepository,
    ) -> None:
        self._runs = run_repository
        self._results = result_repository
        self._blocks = context_block_repository
        self._citations = citation_repository

    def store(
        self,
        *,
        run: SearchQueryRun,
        ranked_hits: list[dict],
        context_blocks: list[dict],
        citations: list[dict],
        collection_name: str | None,
    ) -> SearchQueryRun:
        result_rows: list[SearchQueryResult] = []
        for hit in ranked_hits:
            payload = dict(hit.get("payload") or {})
            result_rows.append(
                SearchQueryResult(
                    id=new_id("qres"),
                    query_run_id=run.id,
                    knowledge_base_id=run.knowledge_base_id,
                    training_item_id=str(hit.get("training_item_id") or payload.get("training_item_id") or ""),
                    chunk_id=str(hit.get("chunk_id") or payload.get("chunk_id") or ""),
                    embedding_id=str(hit.get("embedding_id") or payload.get("embedding_id") or ""),
                    qdrant_collection=str(collection_name or ""),
                    qdrant_point_id=str(hit.get("qdrant_point_id") or ""),
                    rank=int(hit.get("rank") or 0),
                    qdrant_score=float(hit.get("score") or 0.0),
                    hybrid_score=float(hit.get("hybrid_score") or 0.0),
                    overall_score=float(hit.get("overall_score") or 0.0),
                    payload_json=payload,
                    metadata_json={"ranking": True},
                )
            )

        block_rows: list[SearchContextBlock] = []
        for block in context_blocks:
            block_rows.append(
                SearchContextBlock(
                    id=new_id("qctx"),
                    query_run_id=run.id,
                    context_block_id=str(block.get("context_block_id") or new_id("ctx")),
                    chunk_id=str(block.get("chunk_id") or ""),
                    training_item_id=str(block.get("training_item_id") or ""),
                    source_id=str(block.get("source_id") or ""),
                    rank=int(block.get("rank") or 0),
                    included_in_prompt=1 if block.get("included_in_prompt", True) else 0,
                    token_estimate=int(block.get("token_estimate") or 0),
                    text=str(block.get("text") or ""),
                    snippet=str(block.get("snippet") or ""),
                    heading_path=str(block.get("heading_path") or "") or None,
                    section_title=str(block.get("section_title") or "") or None,
                    page_numbers=list(block.get("page_numbers") or []),
                    metadata_json=dict(block),
                )
            )

        citation_rows: list[SearchCitation] = []
        for citation in citations:
            citation_rows.append(
                SearchCitation(
                    id=new_id("qcit"),
                    query_run_id=run.id,
                    citation_id=str(citation.get("citation_id") or ""),
                    source_id=str(citation.get("source_id") or ""),
                    chunk_id=str(citation.get("chunk_id") or ""),
                    training_item_id=str(citation.get("training_item_id") or ""),
                    document_title=str(citation.get("document_title") or ""),
                    document_type=str(citation.get("document_type") or "") or None,
                    page_numbers=list(citation.get("page_numbers") or []),
                    section_title=str(citation.get("section_title") or "") or None,
                    snippet=str(citation.get("snippet") or ""),
                    download_ref=str(citation.get("download_ref") or "") or None,
                    source_url=str(citation.get("source_url") or "") or None,
                    index_ref=str(citation.get("index_ref") or "") or None,
                    display_order=int(citation.get("display_order") or 0),
                    metadata_json=dict(citation),
                )
            )

        self._results.bulk_create(result_rows)
        self._blocks.bulk_create(block_rows)
        self._citations.bulk_create(citation_rows)
        run.finished_at = utc_now_naive()
        return self._runs.update(run)


__all__ = ["StoreSearchRunService"]
