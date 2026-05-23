from __future__ import annotations

from typing import Any

from apps.chat.service.chat_query_enrichment_service import ChatQueryEnrichmentService


class ChatContextPacketMerger:
    def __init__(
        self,
        *,
        query_enrichment_service: ChatQueryEnrichmentService,
        multi_kb_packet_score_threshold: float,
        multi_kb_block_score_threshold: float,
        multi_kb_block_relative_floor_ratio: float,
    ) -> None:
        self._query_enrichment_service = query_enrichment_service
        self._multi_kb_packet_score_threshold = multi_kb_packet_score_threshold
        self._multi_kb_block_score_threshold = multi_kb_block_score_threshold
        self._multi_kb_block_relative_floor_ratio = multi_kb_block_relative_floor_ratio

    @staticmethod
    def packet_score(packet: dict[str, Any]) -> float:
        score = 0.0
        for key in ("synthesis_confidence", "retrieval_confidence", "confidence"):
            try:
                score = max(score, float(packet.get(key) or 0.0))
            except (TypeError, ValueError):
                pass
        try:
            score += min(1.0, float((packet.get("scoring_summary") or {}).get("result_count") or 0) / 10.0)
        except (TypeError, ValueError):
            pass
        return score

    @staticmethod
    def packet_retrieval_confidence(packet: dict[str, Any]) -> float:
        for value in (
            packet.get("retrieval_confidence"),
            (packet.get("scoring_summary") or {}).get("retrieval_confidence"),
            packet.get("confidence"),
        ):
            try:
                parsed = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return 0.0

    def packet_has_strong_context_blocks(self, packet: dict[str, Any], *, strong_entities: list[str]) -> bool:
        blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        if not isinstance(blocks, list):
            return False
        return any(
            isinstance(block, dict) and self.candidate_block_score(block, strong_entities=strong_entities) >= self._multi_kb_block_score_threshold
            for block in blocks
        )

    def packet_has_entity_matching_fallback_rows(self, packet: dict[str, Any], *, strong_entities: list[str]) -> bool:
        if not strong_entities:
            return False
        for key in ("source_chunks", "evidence_sentences", "top_assertions"):
            for row in packet.get(key) or []:
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("subject") or row.get("entity_name") or ""),
                        str(row.get("text") or row.get("snippet") or row.get("claim_text") or ""),
                    ]
                ).strip()
                if text and self._query_enrichment_service.text_matches_strong_entity(text, strong_entities):
                    return True
        return False

    def candidate_block_score(self, row: dict[str, Any], *, strong_entities: list[str]) -> float:
        if strong_entities:
            block_text = " ".join(
                [
                    str(row.get("subject") or row.get("primary_subject") or ""),
                    str(row.get("snippet") or row.get("text") or ""),
                ]
            )
            if not self._query_enrichment_service.text_matches_strong_entity(block_text, strong_entities):
                return 0.0
        try:
            return float(row.get("match_score") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def dynamic_multi_kb_block_floor(self, packets: list[dict[str, Any]], *, strong_entities: list[str]) -> float:
        scores: list[float] = []
        for packet in packets:
            for key in ("context_blocks", "matched_semantic_blocks"):
                for row in packet.get(key) or []:
                    if isinstance(row, dict):
                        score = self.candidate_block_score(row, strong_entities=strong_entities)
                        if score > 0:
                            scores.append(score)
        if not scores:
            return self._multi_kb_block_score_threshold
        return max(self._multi_kb_block_score_threshold, max(scores) * self._multi_kb_block_relative_floor_ratio)

    @staticmethod
    def stamp_packet_kb(packet: dict[str, Any], kb_uuid: str, kb_name: str) -> None:
        for key in (
            "source_chunks",
            "evidence_sentences",
            "top_assertions",
            "matched_chunks",
            "matched_claims",
            "context_blocks",
            "matched_semantic_blocks",
            "evidence_summary",
        ):
            for row in packet.get(key) or []:
                if isinstance(row, dict):
                    row.setdefault("kb_uuid", kb_uuid)
                    row.setdefault("kb_name", kb_name)

    def merge_context_packets(
        self,
        packets: list[dict[str, Any]],
        *,
        kb_names: dict[str, str],
        parsed: dict[str, Any],
        no_ready_index_build: bool = False,
        multi_kb_diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not packets:
            return self._empty_packet(parsed, kb_names, no_ready_index_build, multi_kb_diagnostics)
        strong_entities = self._query_enrichment_service.strong_entity_candidates(parsed)
        ordered = sorted(packets, key=self.packet_score, reverse=True)
        qualified, fallback_to_non_entity_gate = self._qualified_packets(ordered, strong_entities)
        effective_strong_entities = [] if fallback_to_non_entity_gate else strong_entities
        dynamic_block_floor = self.dynamic_multi_kb_block_floor(qualified, strong_entities=effective_strong_entities)
        if not qualified:
            empty = self._empty_packet(parsed, kb_names, no_ready_index_build, multi_kb_diagnostics)
            empty.update({"answer_text": "", "dynamic_block_score_threshold": dynamic_block_floor})
            return empty
        merged = self._base_merged_packet(parsed, kb_names, no_ready_index_build, multi_kb_diagnostics, len(qualified), dynamic_block_floor)
        if fallback_to_non_entity_gate:
            merged["filtered_out_reason"] = [
                "entity_gate_fallback: strict entity szűrés nem adott találatot, ezért packet-score alapú fallback futott"
            ]
        self._copy_single_kb_pii_settings(merged, qualified)
        for packet in qualified:
            self._merge_packet_rows(merged, packet, effective_strong_entities, dynamic_block_floor)
            self._merge_source_ids(merged, packet)
            summary = packet.get("scoring_summary") or {}
            merged["scoring_summary"]["result_count"] += int(summary.get("result_count") or 0)
        if int(merged["scoring_summary"].get("result_count") or 0) <= 0:
            semantic_rows = merged.get("context_blocks") or merged.get("matched_semantic_blocks") or []
            if semantic_rows:
                merged["scoring_summary"]["result_count"] = len(semantic_rows)
        return merged

    def _qualified_packets(self, ordered: list[dict[str, Any]], strong_entities: list[str]) -> tuple[list[dict[str, Any]], bool]:
        qualified: list[dict[str, Any]] = []
        for packet in ordered:
            has_entity_signal = (
                self.packet_has_strong_context_blocks(packet, strong_entities=strong_entities)
                or self.packet_has_entity_matching_fallback_rows(packet, strong_entities=strong_entities)
            )
            if strong_entities:
                if has_entity_signal:
                    qualified.append(packet)
                continue
            if self.packet_retrieval_confidence(packet) >= self._multi_kb_packet_score_threshold and has_entity_signal:
                qualified.append(packet)
        if not strong_entities or qualified:
            return qualified, False
        return [
            packet
            for packet in ordered
            if self.packet_retrieval_confidence(packet) >= self._multi_kb_packet_score_threshold
            and self.packet_has_strong_context_blocks(packet, strong_entities=[])
        ], True

    @staticmethod
    def _empty_packet(
        parsed: dict[str, Any],
        kb_names: dict[str, str],
        no_ready_index_build: bool,
        multi_kb_diagnostics: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "query_focus": parsed,
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": [],
            "related_entities": [],
            "matched_semantic_blocks": [],
            "matched_chunks": [],
            "matched_claims": [],
            "kb_scope": "all",
            "kb_names": kb_names,
            "answer_mode": "no_answer",
            "no_ready_index_build": bool(no_ready_index_build),
            "multi_kb_diagnostics": multi_kb_diagnostics or {},
            "scoring_summary": {
                "result_count": 0,
                "kb_count": len(kb_names),
                "kb_qualified_count": 0,
                "latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)},
            },
        }

    @staticmethod
    def _base_merged_packet(
        parsed: dict[str, Any],
        kb_names: dict[str, str],
        no_ready_index_build: bool,
        multi_kb_diagnostics: dict[str, Any] | None,
        qualified_count: int,
        dynamic_block_floor: float,
    ) -> dict[str, Any]:
        return {
            "query_focus": parsed,
            "kb_scope": "all",
            "kb_uuid": "",
            "corpus_uuid": "",
            "kb_names": kb_names,
            "answer_mode": "summary",
            "answer_text": "",
            "query_run_id": None,
            "no_ready_index_build": bool(no_ready_index_build),
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": [],
            "related_entities": [],
            "context_blocks": [],
            "matched_semantic_blocks": [],
            "matched_chunks": [],
            "matched_claims": [],
            "evidence_summary": [],
            "cited_source_ids": [],
            "source_ids": [],
            "dynamic_block_score_threshold": dynamic_block_floor,
            "multi_kb_diagnostics": multi_kb_diagnostics or {},
            "scoring_summary": {
                "result_count": 0,
                "kb_count": len(kb_names),
                "kb_qualified_count": qualified_count,
                "latency_ms": {},
            },
        }

    @staticmethod
    def _copy_single_kb_pii_settings(merged: dict[str, Any], qualified: list[dict[str, Any]]) -> None:
        qualified_kb_uuids = {
            str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
            for packet in qualified
            if str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        }
        if len(qualified_kb_uuids) != 1:
            return
        effective_kb_uuid = next(iter(qualified_kb_uuids))
        merged["kb_uuid"] = effective_kb_uuid
        merged["corpus_uuid"] = effective_kb_uuid
        for packet in qualified:
            if str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip() != effective_kb_uuid:
                continue
            if "pii_depersonalization_enabled" in packet:
                merged["pii_depersonalization_enabled"] = bool(packet.get("pii_depersonalization_enabled"))
            if str(packet.get("personal_data_sensitivity") or "").strip():
                merged["personal_data_sensitivity"] = str(packet.get("personal_data_sensitivity")).strip()
            break

    def _merge_packet_rows(
        self,
        merged: dict[str, Any],
        packet: dict[str, Any],
        effective_strong_entities: list[str],
        dynamic_block_floor: float,
    ) -> None:
        packet_selected_source_ids: set[str] = set()
        for key, limit in (
            ("context_blocks", 8),
            ("matched_semantic_blocks", 8),
            ("source_chunks", 8),
            ("evidence_sentences", 8),
            ("matched_chunks", 12),
            ("matched_claims", 12),
            ("evidence_summary", 12),
        ):
            current = merged.setdefault(key, [])
            for row in packet.get(key) or []:
                if not isinstance(row, dict):
                    continue
                if not self._row_allowed(key, row, effective_strong_entities, dynamic_block_floor, packet_selected_source_ids):
                    continue
                if key in {"context_blocks", "matched_semantic_blocks"}:
                    source_id = str(row.get("source_id") or row.get("source_point_id") or "").strip()
                    if source_id:
                        packet_selected_source_ids.add(source_id)
                if len(current) < limit:
                    current.append(row)

    def _row_allowed(
        self,
        key: str,
        row: dict[str, Any],
        effective_strong_entities: list[str],
        dynamic_block_floor: float,
        packet_selected_source_ids: set[str],
    ) -> bool:
        if key in {"context_blocks", "matched_semantic_blocks"}:
            return self.candidate_block_score(row, strong_entities=effective_strong_entities) >= dynamic_block_floor
        if key in {"matched_chunks", "matched_claims"} and effective_strong_entities:
            row_text = " ".join([str(row.get("entity_name") or row.get("subject") or ""), str(row.get("claim_text") or row.get("display_claim_text") or "")])
            return self._query_enrichment_service.text_matches_strong_entity(row_text, effective_strong_entities)
        if key in {"source_chunks", "evidence_sentences", "evidence_summary"} and effective_strong_entities:
            row_source_id = str(row.get("source_id") or row.get("source_point_id") or row.get("point_id") or row.get("id") or "").strip()
            row_text = " ".join([str(row.get("subject") or row.get("entity_name") or ""), str(row.get("text") or row.get("snippet") or row.get("claim_text") or "")]).strip()
            source_match = bool(packet_selected_source_ids) and row_source_id in packet_selected_source_ids
            text_match = bool(row_text) and self._query_enrichment_service.text_matches_strong_entity(row_text, effective_strong_entities)
            return source_match or text_match
        return True

    @staticmethod
    def _merge_source_ids(merged: dict[str, Any], packet: dict[str, Any]) -> None:
        for source_id in [*(packet.get("cited_source_ids") or []), *(packet.get("source_ids") or [])]:
            text = str(source_id or "").strip()
            if text and text not in merged["cited_source_ids"]:
                merged["cited_source_ids"].append(text)
                merged["source_ids"].append(text)


__all__ = ["ChatContextPacketMerger"]
