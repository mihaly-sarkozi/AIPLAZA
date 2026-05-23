# backend/apps/chat/service/chat_context_packet_service.py
# Owns chat context packet scoring, merge and text normalization.

from __future__ import annotations

import asyncio
import logging
from typing import Any

from apps.chat.errors import ChatPermissionDenied
from apps.chat.service.chat_query_enrichment_service import ChatQueryEnrichmentService

logger = logging.getLogger(__name__)


class ChatContextPacketService:
    def __init__(
        self,
        *,
        query_enrichment_service: ChatQueryEnrichmentService,
        max_context_blocks: int,
        max_primary_assertions: int,
        max_supporting_assertions: int,
        max_evidence_lines: int,
        max_context_chunks: int,
        max_context_text_chars: int,
        max_context_block_snippet_chars: int,
        multi_kb_packet_score_threshold: float,
        multi_kb_block_score_threshold: float,
        multi_kb_block_relative_floor_ratio: float,
        context_timeout_sec: int,
        retrieval_context_builder: Any | None = None,
    ) -> None:
        self._query_enrichment_service = query_enrichment_service
        self._max_context_blocks = max_context_blocks
        self._max_primary_assertions = max_primary_assertions
        self._max_supporting_assertions = max_supporting_assertions
        self._max_evidence_lines = max_evidence_lines
        self._max_context_chunks = max_context_chunks
        self._max_context_text_chars = max_context_text_chars
        self._max_context_block_snippet_chars = max_context_block_snippet_chars
        self._multi_kb_packet_score_threshold = multi_kb_packet_score_threshold
        self._multi_kb_block_score_threshold = multi_kb_block_score_threshold
        self._multi_kb_block_relative_floor_ratio = multi_kb_block_relative_floor_ratio
        self._context_timeout_sec = context_timeout_sec
        self._retrieval_context_builder = retrieval_context_builder

    def set_retrieval_context_builder(self, retrieval_context_builder: Any) -> None:
        self._retrieval_context_builder = retrieval_context_builder

    async def build(
        self,
        *,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        if self._retrieval_context_builder is None:
            return {}
        return await self._retrieval_context_builder.build(
            question=question,
            user_id=user_id,
            user_role=user_role,
            kb_uuid=kb_uuid,
            tenant=tenant,
            debug=debug,
        )

    async def build_single_kb(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        parsed: dict[str, Any],
        kb_uuid: str,
        debug: bool,
        tenant: str | None = None,
    ) -> dict[str, Any]:
        if self._retrieval_context_builder is None:
            return {}
        return await self._retrieval_context_builder._build_single_kb_context_packet(
            question=question,
            user_id=user_id,
            user_role=user_role,
            parsed=parsed,
            kb_uuid=kb_uuid,
            tenant=tenant,
            debug=debug,
        )

    async def build_multi_kb(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        permission_subject: Any | None,
        parsed: dict[str, Any],
        debug: bool,
        tenant: str | None = None,
    ) -> dict[str, Any]:
        if self._retrieval_context_builder is None:
            return {}
        return await self._retrieval_context_builder._build_multi_kb_context_packet(
            question=question,
            user_id=user_id,
            user_role=user_role,
            permission_subject=permission_subject,
            parsed=parsed,
            tenant=tenant,
            debug=debug,
        )

    async def safe_context_text(
        self,
        *,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
    ) -> tuple[str, bool]:
        try:
            packet = await asyncio.wait_for(
                self.build(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    kb_uuid=kb_uuid,
                    tenant=tenant,
                    debug=debug,
                ),
                timeout=self._context_timeout_sec,
            )
            return self.llm_text(packet), False
        except (ChatPermissionDenied, PermissionError):
            raise
        except asyncio.TimeoutError:
            logger.warning(
                "Knowledge context építés timeout (%ss).",
                self._context_timeout_sec,
                exc_info=True,
            )
            return "", True
        except Exception as exc:
            logger.warning("Knowledge context építés sikertelen: %s", exc, exc_info=True)
            return "", True

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

    def packet_has_strong_context_blocks(
        self,
        packet: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> bool:
        blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        if not isinstance(blocks, list):
            return False
        for block in blocks:
            if not isinstance(block, dict):
                continue
            score = self.candidate_block_score(block, strong_entities=strong_entities)
            if score >= self._multi_kb_block_score_threshold:
                return True
        return False

    def packet_has_entity_matching_fallback_rows(
        self,
        packet: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> bool:
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

    def candidate_block_score(
        self,
        row: dict[str, Any],
        *,
        strong_entities: list[str],
    ) -> float:
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

    def dynamic_multi_kb_block_floor(
        self,
        packets: list[dict[str, Any]],
        *,
        strong_entities: list[str],
    ) -> float:
        scores: list[float] = []
        for packet in packets:
            for key in ("context_blocks", "matched_semantic_blocks"):
                for row in packet.get(key) or []:
                    if not isinstance(row, dict):
                        continue
                    score = self.candidate_block_score(row, strong_entities=strong_entities)
                    if score > 0:
                        scores.append(score)
        if not scores:
            return self._multi_kb_block_score_threshold
        top_score = max(scores)
        return max(
            self._multi_kb_block_score_threshold,
            top_score * self._multi_kb_block_relative_floor_ratio,
        )

    @staticmethod
    def stamp_packet_kb(packet: dict[str, Any], kb_uuid: str, kb_name: str) -> None:
        for key in ("source_chunks", "evidence_sentences", "top_assertions", "matched_chunks", "matched_claims"):
            for row in packet.get(key) or []:
                if isinstance(row, dict):
                    row.setdefault("kb_uuid", kb_uuid)
                    row.setdefault("kb_name", kb_name)
        for key in ("context_blocks", "matched_semantic_blocks"):
            for row in packet.get(key) or []:
                if isinstance(row, dict):
                    row.setdefault("kb_uuid", kb_uuid)
                    row.setdefault("kb_name", kb_name)
        for row in packet.get("evidence_summary") or []:
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
        strong_entities = self._query_enrichment_service.strong_entity_candidates(parsed)
        ordered = sorted(packets, key=self.packet_score, reverse=True)
        qualified: list[dict[str, Any]] = []
        fallback_to_non_entity_gate = False
        for packet in ordered:
            has_entity_signal = (
                self.packet_has_strong_context_blocks(packet, strong_entities=strong_entities)
                or self.packet_has_entity_matching_fallback_rows(packet, strong_entities=strong_entities)
            )
            if strong_entities:
                if has_entity_signal:
                    qualified.append(packet)
                continue
            if (
                self.packet_retrieval_confidence(packet) >= self._multi_kb_packet_score_threshold
                and has_entity_signal
            ):
                qualified.append(packet)
        if strong_entities and not qualified:
            fallback_to_non_entity_gate = True
            qualified = [
                packet
                for packet in ordered
                if self.packet_retrieval_confidence(packet) >= self._multi_kb_packet_score_threshold
                and self.packet_has_strong_context_blocks(packet, strong_entities=[])
            ]
        effective_strong_entities = [] if fallback_to_non_entity_gate else strong_entities
        dynamic_block_floor = self.dynamic_multi_kb_block_floor(
            qualified,
            strong_entities=effective_strong_entities,
        )
        if not qualified:
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
                "answer_text": "",
                "no_ready_index_build": bool(no_ready_index_build),
                "dynamic_block_score_threshold": dynamic_block_floor,
                "multi_kb_diagnostics": multi_kb_diagnostics or {},
                "scoring_summary": {
                    "result_count": 0,
                    "kb_count": len(kb_names),
                    "kb_qualified_count": 0,
                    "latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)},
                },
            }
        merged: dict[str, Any] = {
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
                "kb_qualified_count": len(qualified),
                "latency_ms": {},
            },
        }
        if fallback_to_non_entity_gate:
            merged["filtered_out_reason"] = [
                "entity_gate_fallback: strict entity szűrés nem adott találatot, ezért packet-score alapú fallback futott"
            ]
        qualified_kb_uuids = {
            str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
            for packet in qualified
            if str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
        }
        if len(qualified_kb_uuids) == 1:
            effective_kb_uuid = next(iter(qualified_kb_uuids))
            merged["kb_uuid"] = effective_kb_uuid
            merged["corpus_uuid"] = effective_kb_uuid
            for packet in qualified:
                packet_kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or "").strip()
                if packet_kb_uuid != effective_kb_uuid:
                    continue
                if "pii_depersonalization_enabled" in packet:
                    merged["pii_depersonalization_enabled"] = bool(packet.get("pii_depersonalization_enabled"))
                if str(packet.get("personal_data_sensitivity") or "").strip():
                    merged["personal_data_sensitivity"] = str(packet.get("personal_data_sensitivity")).strip()
                break
        for packet in qualified:
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
                    if key in {"context_blocks", "matched_semantic_blocks"}:
                        block_score = self.candidate_block_score(row, strong_entities=effective_strong_entities)
                        if block_score < dynamic_block_floor:
                            continue
                        source_id = str(row.get("source_id") or row.get("source_point_id") or "").strip()
                        if source_id:
                            packet_selected_source_ids.add(source_id)
                    elif key in {"matched_chunks", "matched_claims"} and effective_strong_entities:
                        row_text = " ".join(
                            [
                                str(row.get("entity_name") or row.get("subject") or ""),
                                str(row.get("claim_text") or row.get("display_claim_text") or ""),
                            ]
                        )
                        if not self._query_enrichment_service.text_matches_strong_entity(
                            row_text,
                            effective_strong_entities,
                        ):
                            continue
                    elif key in {"source_chunks", "evidence_sentences", "evidence_summary"} and effective_strong_entities:
                        row_source_id = str(
                            row.get("source_id")
                            or row.get("source_point_id")
                            or row.get("point_id")
                            or row.get("id")
                            or ""
                        ).strip()
                        row_text = " ".join(
                            [
                                str(row.get("subject") or row.get("entity_name") or ""),
                                str(row.get("text") or row.get("snippet") or row.get("claim_text") or ""),
                            ]
                        ).strip()
                        source_match = bool(packet_selected_source_ids) and row_source_id in packet_selected_source_ids
                        text_match = bool(row_text) and self._query_enrichment_service.text_matches_strong_entity(
                            row_text,
                            effective_strong_entities,
                        )
                        if not source_match and not text_match:
                            continue
                    if len(current) < limit:
                        current.append(row)
            for source_id in [*(packet.get("cited_source_ids") or []), *(packet.get("source_ids") or [])]:
                text = str(source_id or "").strip()
                if text and text not in merged["cited_source_ids"]:
                    merged["cited_source_ids"].append(text)
                    merged["source_ids"].append(text)
            summary = packet.get("scoring_summary") or {}
            merged["scoring_summary"]["result_count"] += int(summary.get("result_count") or 0)
        if int(merged["scoring_summary"].get("result_count") or 0) <= 0:
            semantic_rows = merged.get("context_blocks") or merged.get("matched_semantic_blocks") or []
            if semantic_rows:
                merged["scoring_summary"]["result_count"] = len(semantic_rows)
        return merged

    def context_text(self, packet: dict[str, Any]) -> str:
        context_blocks = packet.get("context_blocks") or packet.get("matched_semantic_blocks") or []
        block_lines = []
        for index, block in enumerate(context_blocks[: self._max_context_blocks], start=1):
            text = str(block.get("snippet") or block.get("text") or "").strip()
            if not text:
                continue
            if len(text) > self._max_context_block_snippet_chars:
                text = f"{text[: self._max_context_block_snippet_chars].rstrip()}..."
            subject = str(block.get("subject") or block.get("primary_subject") or "-").strip() or "-"
            space = str(block.get("space") or block.get("primary_space") or "-").strip() or "-"
            time = str(block.get("time") or block.get("primary_time") or "-").strip() or "-"
            block_id = str(block.get("block_id") or block.get("id") or "").strip()
            block_lines.append(
                f"- [B{index}] block_id={block_id}; alany={subject}; hely={space}; idő={time}\n{text}"
            )
        primary = packet.get("primary_assertions") or packet.get("seed_assertions") or packet.get("summary_assertions") or packet.get("top_assertions") or []
        supporting = packet.get("supporting_assertions") or packet.get("expanded_assertions") or []
        primary_lines = []
        for row in primary[: self._max_primary_assertions]:
            text = row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or ""
            if text:
                primary_lines.append(f"- [A] {text}")
        sentence_lines = packet.get("evidence_sentences") or []
        chunk_lines = packet.get("source_chunks") or []
        if not primary_lines and (sentence_lines or chunk_lines):
            for row in chunk_lines[: self._max_context_chunks]:
                text = row.get("text") or row.get("payload", {}).get("text") or ""
                if text:
                    primary_lines.append(f"- [C] {text}")
            for row in sentence_lines[: self._max_evidence_lines]:
                if len(primary_lines) >= self._max_primary_assertions:
                    break
                text = row.get("text") or row.get("payload", {}).get("text") or ""
                if text and not any(t in "\n".join(primary_lines) for t in [text[:50]]):
                    primary_lines.append(f"- [S] {text}")
        if not primary_lines and not block_lines:
            return ""
        related_entities = packet.get("related_entities") or []
        related_places = packet.get("related_places") or []
        time_slices = packet.get("time_slice_groups") or []
        timeline_sequence = packet.get("timeline_sequence") or []
        conflicts = packet.get("conflict_bundles") or []
        refinements = packet.get("refinement_bundles") or []
        supporting_lines = []
        primary_ids = {
            str(row.get("id"))
            for row in primary[:6]
            if row.get("id") is not None
        }
        for row in supporting[: self._max_supporting_assertions]:
            if str(row.get("id")) in primary_ids:
                continue
            text = row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or ""
            if text:
                supporting_lines.append(f"- [SA] {text}")
        evidence_lines = []
        for row in sentence_lines[: self._max_evidence_lines]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                prefix = "[S]" if str(row.get("context_role") or "").startswith("primary") else "[SE]"
                evidence_lines.append(f"- {prefix} {text}")
        chunk_text_lines = []
        for row in chunk_lines[: self._max_context_chunks]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                prefix = "[C]" if str(row.get("context_role") or "") == "primary_chunk" else "[CF]"
                chunk_text_lines.append(f"- {prefix} {text}")
        query_focus = packet.get("query_focus") or {}
        entity_lines = [
            f"- [E] {x.get('canonical_name') or x.get('entity_id')}"
            for x in related_entities[:5]
        ]
        place_lines = [
            f"- [P] {x.get('place_key')} ({len(x.get('assertion_ids') or [])} állítás)"
            for x in related_places[:5]
            if x.get("place_key")
        ]
        slice_lines = [
            f"- [T] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]}..{str(x.get('valid_time_to') or x.get('time_to') or '')[:10]} ({len(x.get('assertion_ids') or [])} állítás)"
            for x in time_slices[:4]
        ]
        timeline_lines = [
            f"- [TL] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]} {x.get('text') or ''}"
            for x in timeline_sequence[:6]
        ]
        conflict_lines = [
            f"- [CF] {x.get('focus_key')} ({len(x.get('items') or [])} ellentmondó állítás)"
            for x in conflicts[:3]
        ]
        refinement_lines = [
            f"- [RF] {x.get('focus_key')} ({len(x.get('assertion_ids') or [])} finomított állítás)"
            for x in refinements[:3]
        ]
        intent = str(query_focus.get("intent", "summary"))
        base = (
            f"Intent: {intent}\n"
            f"Retrieval mode: {query_focus.get('retrieval_mode', 'assertion_first')}\n"
            + ("Knowledge blocks:\n" + "\n".join(block_lines) + "\n" if block_lines else "")
            + ("Primary assertions:\n" + "\n".join(primary_lines) if primary_lines else "")
            + ("\nSupporting assertions:\n" + "\n".join(supporting_lines) if supporting_lines else "")
            + ("\nEvidence sentences:\n" + "\n".join(evidence_lines) if evidence_lines else "")
            + ("\nContext chunks:\n" + "\n".join(chunk_text_lines) if chunk_text_lines else "")
            + ("\nRelated entities:\n" + "\n".join(entity_lines) if entity_lines else "")
            + ("\nPlaces:\n" + "\n".join(place_lines) if place_lines else "")
            + ("\nTime slices:\n" + "\n".join(slice_lines) if slice_lines else "")
            + ("\nConflicts:\n" + "\n".join(conflict_lines) if conflict_lines else "")
            + ("\nRefinements:\n" + "\n".join(refinement_lines) if refinement_lines else "")
        )
        if intent == "timeline":
            return (base + ("\nChronology:\n" + "\n".join(timeline_lines) if timeline_lines else ""))[: self._max_context_text_chars]
        if intent == "comparison":
            cmp = packet.get("comparison_summary") or {}
            return (
                base
                + "\nComparison focus:\n"
                + f"- left={cmp.get('left_target')} ({cmp.get('left_count', 0)})\n"
                + f"- right={cmp.get('right_target')} ({cmp.get('right_count', 0)})"
            )[: self._max_context_text_chars]
        if intent == "relation":
            return (base + "\nRelation guidance: koncentrálj a kapcsolati állításokra és bizonyítékra.")[: self._max_context_text_chars]
        if intent == "attribute":
            return (base + "\nAttribute guidance: emeld ki az attribútum és státusz jellegű állításokat.")[: self._max_context_text_chars]
        return base[: self._max_context_text_chars]

    def llm_text(self, packet: dict[str, Any]) -> str:
        chunk_lines = packet.get("source_chunks") or []
        chunk_text_lines: list[str] = []
        seen_chunk_texts: set[str] = set()
        for row in chunk_lines[: self._max_context_chunks]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            text = str(text or "").strip()
            if not text:
                continue
            if len(text) > self._max_context_block_snippet_chars:
                text = f"{text[: self._max_context_block_snippet_chars].rstrip()}..."
            dedupe_key = " ".join(text.lower().split())
            if dedupe_key in seen_chunk_texts:
                continue
            seen_chunk_texts.add(dedupe_key)
            chunk_text_lines.append(f"- {text}")
        if not chunk_text_lines:
            return ""
        return ("Context chunks:\n" + "\n".join(chunk_text_lines))[: self._max_context_text_chars]


__all__ = ["ChatContextPacketService"]
