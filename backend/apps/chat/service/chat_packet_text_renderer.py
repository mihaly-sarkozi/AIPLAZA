from __future__ import annotations

from typing import Any


class ChatPacketTextRenderer:
    def __init__(
        self,
        *,
        max_context_blocks: int,
        max_primary_assertions: int,
        max_supporting_assertions: int,
        max_evidence_lines: int,
        max_context_chunks: int,
        max_context_text_chars: int,
        max_context_block_snippet_chars: int,
    ) -> None:
        self._max_context_blocks = max_context_blocks
        self._max_primary_assertions = max_primary_assertions
        self._max_supporting_assertions = max_supporting_assertions
        self._max_evidence_lines = max_evidence_lines
        self._max_context_chunks = max_context_chunks
        self._max_context_text_chars = max_context_text_chars
        self._max_context_block_snippet_chars = max_context_block_snippet_chars

    def llm_text(self, packet: dict[str, Any]) -> str:
        chunk_text_lines = []
        seen: set[str] = set()
        for row in (packet.get("source_chunks") or [])[: self._max_context_chunks]:
            text = str(row.get("text") or row.get("payload", {}).get("text") or "").strip()
            if not text:
                continue
            if len(text) > self._max_context_block_snippet_chars:
                text = f"{text[: self._max_context_block_snippet_chars].rstrip()}..."
            key = " ".join(text.lower().split())
            if key in seen:
                continue
            seen.add(key)
            chunk_text_lines.append(f"- {text}")
        if chunk_text_lines:
            return ("Context chunks:\n" + "\n".join(chunk_text_lines))[: self._max_context_text_chars]

        prompt_context = str(packet.get("encoded_prompt_context") or packet.get("prompt_context") or "").strip()
        if prompt_context:
            return prompt_context[: self._max_context_text_chars]

        for index, block in enumerate(
            (packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [])[: self._max_context_blocks],
            start=1,
        ):
            text = str(block.get("snippet") or block.get("text") or "").strip()
            if not text:
                continue
            if len(text) > self._max_context_block_snippet_chars:
                text = f"{text[: self._max_context_block_snippet_chars].rstrip()}..."
            key = " ".join(text.lower().split())
            if key in seen:
                continue
            seen.add(key)
            citation_id = str(block.get("citation_id") or f"B{index}").strip()
            chunk_text_lines.append(f"- [{citation_id}] {text}")
        if not chunk_text_lines:
            return ""
        return ("Context:\n" + "\n".join(chunk_text_lines))[: self._max_context_text_chars]

    def context_text(self, packet: dict[str, Any]) -> str:
        block_lines = self._block_lines(packet)
        primary_lines = self._primary_lines(packet, block_lines)
        if not primary_lines and not block_lines:
            return ""
        base = self._base_context(packet, block_lines, primary_lines)
        intent = str((packet.get("query_focus") or {}).get("intent", "summary"))
        if intent == "timeline":
            timeline_lines = [
                f"- [TL] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]} {x.get('text') or ''}"
                for x in (packet.get("timeline_sequence") or [])[:6]
            ]
            return (base + ("\nChronology:\n" + "\n".join(timeline_lines) if timeline_lines else ""))[: self._max_context_text_chars]
        if intent == "comparison":
            cmp = packet.get("comparison_summary") or {}
            return (
                base
                + "\nComparison focus:\n"
                + f"- left={cmp.get('left_target')} ({cmp.get('left_count', 0)})\n"
                + f"- right={cmp.get('right_target')} ({cmp.get('right_count', 0)})"
            )[: self._max_context_text_chars]
        guidance = {
            "relation": "\nRelation guidance: koncentrálj a kapcsolati állításokra és bizonyítékra.",
            "attribute": "\nAttribute guidance: emeld ki az attribútum és státusz jellegű állításokat.",
        }.get(intent, "")
        return (base + guidance)[: self._max_context_text_chars]

    def _block_lines(self, packet: dict[str, Any]) -> list[str]:
        lines = []
        for index, block in enumerate((packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [])[: self._max_context_blocks], start=1):
            text = str(block.get("snippet") or block.get("text") or "").strip()
            if not text:
                continue
            if len(text) > self._max_context_block_snippet_chars:
                text = f"{text[: self._max_context_block_snippet_chars].rstrip()}..."
            subject = str(block.get("subject") or block.get("primary_subject") or "-").strip() or "-"
            space = str(block.get("space") or block.get("primary_space") or "-").strip() or "-"
            time = str(block.get("time") or block.get("primary_time") or "-").strip() or "-"
            block_id = str(block.get("block_id") or block.get("id") or "").strip()
            lines.append(f"- [B{index}] block_id={block_id}; alany={subject}; hely={space}; idő={time}\n{text}")
        return lines

    def _primary_lines(self, packet: dict[str, Any], block_lines: list[str]) -> list[str]:
        primary = packet.get("primary_assertions") or packet.get("seed_assertions") or packet.get("summary_assertions") or packet.get("top_assertions") or []
        lines = [f"- [A] {text}" for row in primary[: self._max_primary_assertions] if (text := row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or "")]
        if lines or block_lines:
            return lines
        for row in (packet.get("source_chunks") or [])[: self._max_context_chunks]:
            if text := row.get("text") or row.get("payload", {}).get("text") or "":
                lines.append(f"- [C] {text}")
        for row in (packet.get("evidence_sentences") or [])[: self._max_evidence_lines]:
            if len(lines) >= self._max_primary_assertions:
                break
            if text := row.get("text") or row.get("payload", {}).get("text") or "":
                if not any(text[:50] in existing for existing in lines):
                    lines.append(f"- [S] {text}")
        return lines

    def _base_context(self, packet: dict[str, Any], block_lines: list[str], primary_lines: list[str]) -> str:
        query_focus = packet.get("query_focus") or {}
        parts = [
            f"Intent: {query_focus.get('intent', 'summary')}",
            f"Retrieval mode: {query_focus.get('retrieval_mode', 'assertion_first')}",
        ]
        sections = [
            ("Knowledge blocks", block_lines),
            ("Primary assertions", primary_lines),
            ("Supporting assertions", self._supporting_lines(packet)),
            ("Evidence sentences", self._evidence_lines(packet)),
            ("Context chunks", self._chunk_lines(packet)),
            ("Related entities", [f"- [E] {x.get('canonical_name') or x.get('entity_id')}" for x in (packet.get("related_entities") or [])[:5]]),
            ("Places", [f"- [P] {x.get('place_key')} ({len(x.get('assertion_ids') or [])} állítás)" for x in (packet.get("related_places") or [])[:5] if x.get("place_key")]),
            ("Time slices", [f"- [T] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]}..{str(x.get('valid_time_to') or x.get('time_to') or '')[:10]} ({len(x.get('assertion_ids') or [])} állítás)" for x in (packet.get("time_slice_groups") or [])[:4]]),
            ("Conflicts", [f"- [CF] {x.get('focus_key')} ({len(x.get('items') or [])} ellentmondó állítás)" for x in (packet.get("conflict_bundles") or [])[:3]]),
            ("Refinements", [f"- [RF] {x.get('focus_key')} ({len(x.get('assertion_ids') or [])} finomított állítás)" for x in (packet.get("refinement_bundles") or [])[:3]]),
        ]
        for title, lines in sections:
            if lines:
                parts.append(f"{title}:\n" + "\n".join(lines))
        return "\n".join(parts)

    def _supporting_lines(self, packet: dict[str, Any]) -> list[str]:
        primary = packet.get("primary_assertions") or packet.get("seed_assertions") or packet.get("summary_assertions") or packet.get("top_assertions") or []
        primary_ids = {str(row.get("id")) for row in primary[:6] if row.get("id") is not None}
        lines = []
        for row in (packet.get("supporting_assertions") or packet.get("expanded_assertions") or [])[: self._max_supporting_assertions]:
            if str(row.get("id")) in primary_ids:
                continue
            if text := row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or "":
                lines.append(f"- [SA] {text}")
        return lines

    def _evidence_lines(self, packet: dict[str, Any]) -> list[str]:
        lines = []
        for row in (packet.get("evidence_sentences") or [])[: self._max_evidence_lines]:
            if text := row.get("text") or row.get("payload", {}).get("text") or "":
                prefix = "[S]" if str(row.get("context_role") or "").startswith("primary") else "[SE]"
                lines.append(f"- {prefix} {text}")
        return lines

    def _chunk_lines(self, packet: dict[str, Any]) -> list[str]:
        lines = []
        for row in (packet.get("source_chunks") or [])[: self._max_context_chunks]:
            if text := row.get("text") or row.get("payload", {}).get("text") or "":
                prefix = "[C]" if str(row.get("context_role") or "") == "primary_chunk" else "[CF]"
                lines.append(f"- {prefix} {text}")
        return lines


__all__ = ["ChatPacketTextRenderer"]
