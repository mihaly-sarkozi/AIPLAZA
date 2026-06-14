from __future__ import annotations

from typing import Any

# Kanonikus letöltési URL — query_run_id és source_id helyettesítőkkel.
CHAT_SOURCE_DOWNLOAD_URL_TEMPLATE = "/api/chat/sources/{query_run_id}/{source_id}/download"


def build_download_url(*, query_run_id: str | None, source_id: str | None) -> str | None:
    if not query_run_id or not source_id:
        return None
    return CHAT_SOURCE_DOWNLOAD_URL_TEMPLATE.format(query_run_id=query_run_id, source_id=source_id)


class BuildCitationService:
    def build(
        self,
        context_blocks: list[dict[str, Any]],
        *,
        kb_uuid: str,
        query_run_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        citations: list[dict[str, Any]] = []
        citation_ids: list[str] = []
        for order, block in enumerate(context_blocks, start=1):
            citation_id = str(block.get("citation_id") or f"CIT-{order}")
            source_id = str(block.get("source_id") or block.get("chunk_id") or "")
            download_ref = f"source:{source_id}" if source_id else f"index:kb:{kb_uuid}:chunk:{block.get('chunk_id') or ''}"
            download_url = build_download_url(query_run_id=query_run_id, source_id=source_id)
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
                "download_ref": download_ref,
                "download_url": download_url,
                "download_url_template": CHAT_SOURCE_DOWNLOAD_URL_TEMPLATE,
                "index_ref": f"kb:{kb_uuid}:chunk:{block.get('chunk_id')}",
                "display_order": order,
                "kb_uuid": kb_uuid,
            }
            citations.append(citation)
            citation_ids.append(citation_id)
        return citations, citation_ids


__all__ = ["BuildCitationService", "CHAT_SOURCE_DOWNLOAD_URL_TEMPLATE", "build_download_url"]
