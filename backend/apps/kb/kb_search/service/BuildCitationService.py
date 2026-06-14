from __future__ import annotations

from typing import Any


class BuildCitationService:
    def build(self, context_blocks: list[dict[str, Any]], *, kb_uuid: str) -> tuple[list[dict[str, Any]], list[str]]:
        citations: list[dict[str, Any]] = []
        citation_ids: list[str] = []
        for order, block in enumerate(context_blocks, start=1):
            citation_id = str(block.get("citation_id") or f"CIT-{order}")
            source_id = str(block.get("source_id") or block.get("chunk_id") or "")
            citation = {
                "citation_id": citation_id,
                "source_id": source_id,
                "chunk_id": str(block.get("chunk_id") or ""),
                "training_item_id": str(block.get("training_item_id") or ""),
                "document_title": str(block.get("document_title") or ""),
                "document_type": str(block.get("content_type") or block.get("source_type") or ""),
                "page_numbers": list(block.get("page_numbers") or []),
                "section_title": str(block.get("section_title") or ""),
                "snippet": str(block.get("snippet") or block.get("text") or "")[:480],
                "download_ref": f"/api/chat/sources/{{query_run_id}}/{source_id}/download",
                "index_ref": f"kb:{kb_uuid}:chunk:{block.get('chunk_id')}",
                "display_order": order,
                "kb_uuid": kb_uuid,
            }
            citations.append(citation)
            citation_ids.append(citation_id)
        return citations, citation_ids


__all__ = ["BuildCitationService"]
