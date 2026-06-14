from __future__ import annotations

from typing import Any


class BuildSearchContextService:
    def __init__(self, *, max_blocks: int = 6, max_chars: int = 4000) -> None:
        self._max_blocks = max(1, int(max_blocks))
        self._max_chars = max(500, int(max_chars))

    def build(self, hydrated_hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
        blocks: list[dict[str, Any]] = []
        seen_chunks: set[str] = set()
        prompt_parts: list[str] = []
        total_chars = 0

        for index, hit in enumerate(hydrated_hits, start=1):
            if len(blocks) >= self._max_blocks:
                break
            chunk_id = str(hit.get("chunk_id") or "").strip()
            if not chunk_id or chunk_id in seen_chunks:
                continue
            text = self._clean_text(str(hit.get("text") or hit.get("snippet") or ""))
            if not text:
                continue
            if total_chars + len(text) > self._max_chars:
                remaining = max(120, self._max_chars - total_chars)
                text = text[:remaining].rstrip() + "…"
            citation_id = f"CIT-{len(blocks) + 1}"
            block = {
                "context_block_id": f"ctx-{index}",
                "citation_id": citation_id,
                "chunk_id": chunk_id,
                "training_item_id": str(hit.get("training_item_id") or ""),
                "source_id": str(hit.get("source_id") or chunk_id),
                "rank": int(hit.get("rank") or index),
                "document_title": str(hit.get("document_title") or ""),
                "section_title": str(hit.get("section_title") or ""),
                "page_numbers": list(hit.get("page_numbers") or []),
                "heading_path": hit.get("heading_path"),
                "text": text,
                "snippet": str(hit.get("snippet") or text[:480]),
                "qdrant_score": float(hit.get("score") or 0.0),
                "hybrid_score": float(hit.get("hybrid_score") or 0.0),
                "overall_score": float(hit.get("overall_score") or 0.0),
                "included_in_prompt": True,
                "token_estimate": max(1, len(text) // 4),
            }
            blocks.append(block)
            seen_chunks.add(chunk_id)
            total_chars += len(text)
            page_label = ", ".join(str(p) for p in block["page_numbers"]) if block["page_numbers"] else "—"
            section = block["section_title"] or "—"
            prompt_parts.append(
                f"[{citation_id}]\n"
                f"Dokumentum: {block['document_title'] or 'Ismeretlen'}\n"
                f"Oldal: {page_label}\n"
                f"Szekció: {section}\n"
                f"Szöveg:\n{text}"
            )

        prompt_context = "\n\n".join(prompt_parts)
        return blocks, prompt_context


    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(str(value or "").split())


__all__ = ["BuildSearchContextService"]
