from __future__ import annotations

from collections.abc import Callable
from typing import Any


class AnswerSourceBuilder:
    def __init__(self, *, sanitize_debug_text: Callable[[Any], str]) -> None:
        self._sanitize_debug_text = sanitize_debug_text

    @staticmethod
    def _normalize_page_numbers(value: Any) -> list[int]:
        if not isinstance(value, list):
            return []
        out: list[int] = []
        for item in value:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out

    def _citation_fields(self, row: dict[str, Any]) -> dict[str, Any]:
        citation_id = str(row.get("citation_id") or "").strip()
        download_url = str(row.get("download_url") or "").strip() or None
        download_url_template = str(row.get("download_url_template") or "").strip() or None
        download_ref = str(row.get("download_ref") or "").strip() or None
        section_title = self._sanitize_debug_text(row.get("section_title") or "")
        return {
            "citation_id": citation_id,
            "download_url": download_url,
            "download_url_template": download_url_template,
            "download_ref": download_ref,
            "page_numbers": self._normalize_page_numbers(row.get("page_numbers")),
            "section_title": section_title,
        }

    def build_sources_from_packet(self, packet: dict[str, Any]) -> list[dict[str, Any]]:
        kb_sources = packet.get("sources") or []
        if isinstance(kb_sources, list) and kb_sources:
            out: list[dict[str, Any]] = []
            kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
            for row in kb_sources:
                if not isinstance(row, dict):
                    continue
                source_id = str(row.get("source_id") or row.get("chunk_id") or "").strip()
                if not source_id:
                    continue
                pages = row.get("page_numbers") or []
                page_label = ", ".join(str(p) for p in pages) if pages else ""
                title = str(row.get("document_title") or row.get("title") or source_id)
                if page_label:
                    title = f"{title} — oldal {page_label}"
                section = str(row.get("section_title") or "").strip()
                if section:
                    title = f"{title} — {section}"
                citation_id = str(row.get("citation_id") or "")
                if citation_id:
                    title = f"[{citation_id}] {title}"
                out.append(
                    {
                        "kb_uuid": str(row.get("kb_uuid") or kb_uuid),
                        "kb_name": str(packet.get("kb_name") or ""),
                        "point_id": source_id,
                        "source_id": source_id,
                        "title": self._sanitize_debug_text(title),
                        "snippet": self._sanitize_debug_text(row.get("snippet") or ""),
                        "source_type": self._sanitize_debug_text(row.get("document_type") or row.get("source_type") or ""),
                        "file_ref": None,
                        "display_type": "",
                        "created_by": None,
                        "created_by_label": "",
                        "created_at": None,
                        **self._citation_fields(row),
                    }
                )
            if out:
                return out[:8]

        rows = []
        context_blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        blocks_by_source = self._blocks_by_source(context_blocks)
        for key in ["source_chunks", "evidence_sentences", "top_assertions"]:
            rows.extend(packet.get(key) or [])
        fallback_kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        fallback_source_ids = self._fallback_source_ids(packet)
        out = self._sources_from_rows(packet, rows, blocks_by_source)
        if not out and fallback_kb_uuid:
            out = self._fallback_sources(packet, fallback_kb_uuid, fallback_source_ids)
        return out

    @staticmethod
    def _blocks_by_source(context_blocks: list[Any]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for block in context_blocks:
            if isinstance(block, dict):
                source_id = str(block.get("source_id") or "").strip()
                if source_id and source_id not in out:
                    out[source_id] = block
        return out

    @staticmethod
    def _fallback_source_ids(packet: dict[str, Any]) -> list[str]:
        ids: list[str] = []
        values = [*(packet.get("cited_source_ids") or []), *(packet.get("source_ids") or [])]
        values.extend(item.get("source_id") for item in packet.get("evidence_summary") or [] if isinstance(item, dict))
        values.extend(
            block.get("source_id")
            for block in packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
            if isinstance(block, dict)
        )
        for value in values:
            text = str(value or "").strip()
            if text and text not in ids:
                ids.append(text)
        return ids

    def _sources_from_rows(
        self,
        packet: dict[str, Any],
        rows: list[Any],
        blocks_by_source: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, str]] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = self._source_item(packet, row, blocks_by_source)
            if item is None:
                continue
            display_key = self._display_key(row, item)
            item_key = (item["kb_uuid"], display_key, str(row.get("display_type") or "").strip().lower())
            if item_key in seen:
                continue
            seen.add(item_key)
            out.append(item)
            if len(out) >= 8:
                break
        return out

    def _source_item(
        self,
        packet: dict[str, Any],
        row: dict[str, Any],
        blocks_by_source: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        kb_uuid = str(row.get("kb_uuid") or "").strip()
        kb_name = str(row.get("kb_name") or (packet.get("kb_names") or {}).get(kb_uuid) or "").strip()
        point_id = str(row.get("source_point_id") or row.get("source_id") or row.get("id") or row.get("point_id") or "").strip()
        source_id = str(row.get("source_id") or "").strip()
        has_source_metadata = bool(row.get("display_type") or row.get("file_ref") or row.get("created_by_label") or row.get("created_by") is not None)
        if not source_id and has_source_metadata:
            source_id = point_id
        if not source_id and row.get("build_id") and not has_source_metadata:
            return None
        source_id = source_id or point_id
        if not kb_uuid or not point_id or not source_id:
            return None
        block = blocks_by_source.get(source_id, {})
        citation_row = {**block, **row}
        return {
            "kb_uuid": kb_uuid,
            "kb_name": self._sanitize_debug_text(kb_name),
            "point_id": point_id,
            "source_id": source_id,
            "title": self._sanitize_debug_text(row.get("source_document_title") or block.get("document_title") or ""),
            "snippet": self._sanitize_debug_text(block.get("snippet") or block.get("text") or row.get("text") or row.get("snippet") or ""),
            "source_type": self._sanitize_debug_text(row.get("source_type") or block.get("source_type") or block.get("content_type") or ""),
            "file_ref": self._sanitize_debug_text(row.get("file_ref") or "") or None,
            "display_type": self._sanitize_debug_text(row.get("display_type") or ""),
            "created_by": row.get("created_by"),
            "created_by_label": self._sanitize_debug_text(row.get("created_by_label") or ""),
            "created_at": str(row.get("created_at") or "").strip() or None,
            **self._citation_fields(citation_row),
        }

    @staticmethod
    def _display_key(row: dict[str, Any], item: dict[str, Any]) -> str:
        title_key = " ".join(str(row.get("source_document_title") or "").strip().lower().split())
        snippet_key = " ".join(str(row.get("text") or row.get("snippet") or row.get("payload", {}).get("text") or "").strip().lower().split())
        is_chat_text_training = (
            str(row.get("source_type") or "").strip().lower() == "text"
            and ("chatből tanított szöveg" in title_key or "gepel" in str(row.get("display_type") or "").lower() or "gépel" in str(row.get("display_type") or "").lower())
        )
        return snippet_key if is_chat_text_training and snippet_key else (f"{title_key}|{snippet_key}".strip("|") or item["source_id"])

    def _fallback_sources(
        self,
        packet: dict[str, Any],
        fallback_kb_uuid: str,
        fallback_source_ids: list[str],
    ) -> list[dict[str, Any]]:
        return [
            {
                "kb_uuid": fallback_kb_uuid,
                "kb_name": self._sanitize_debug_text((packet.get("kb_names") or {}).get(fallback_kb_uuid) or ""),
                "point_id": source_id,
                "source_id": source_id,
                "title": f"Forrás {source_id[:8]}",
                "snippet": "",
                "source_type": "",
                "file_ref": None,
                "display_type": "",
                "created_by": None,
                "created_by_label": "",
                "created_at": None,
                "citation_id": "",
                "download_url": None,
                "download_url_template": None,
                "download_ref": None,
                "page_numbers": [],
                "section_title": "",
            }
            for source_id in fallback_source_ids[:8]
        ]


__all__ = ["AnswerSourceBuilder"]
