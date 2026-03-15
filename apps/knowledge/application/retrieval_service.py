from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any
import uuid as uuid_lib
import json
from pathlib import Path

from config.settings import settings


class KnowledgeRetrievalService:
    """Retrieval orchestráció query parse + keresés + context assembly folyamatra."""

    def __init__(self, kb_service: Any) -> None:
        self.kb_service = kb_service
        self._debug_records: list[dict] = []
        self._trace_records: list[dict] = []
        self._feedback_records: list[dict] = []

    def _persist_trace_row(self, row: dict[str, Any]) -> None:
        if not bool(getattr(settings, "kb_debug_trace_persist", True)):
            return
        path_value = str(getattr(settings, "kb_debug_trace_path", "logs/retrieval_traces.jsonl") or "").strip()
        if not path_value:
            return
        try:
            path = Path(path_value)
            if not path.is_absolute():
                path = Path.cwd() / path
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            return

    @staticmethod
    def _normalize_score(value: float, min_v: float, max_v: float) -> float:
        if max_v <= min_v:
            return 0.0
        return (value - min_v) / (max_v - min_v)

    def _apply_candidate_fusion(self, packet: dict) -> dict:
        top = list(packet.get("top_assertions") or [])
        if not top:
            return packet
        scores = [float(x.get("final_score") or 0.0) for x in top]
        mn, mx = min(scores), max(scores)
        for row in top:
            norm_final = self._normalize_score(float(row.get("final_score") or 0.0), mn, mx)
            semantic = float(row.get("semantic_match") or 0.0)
            lexical = float(row.get("lexical_match") or 0.0)
            row["fusion_rank_score"] = (0.64 * norm_final) + (0.24 * semantic) + (0.12 * lexical)
        packet["top_assertions"] = sorted(top, key=lambda x: float(x.get("fusion_rank_score") or 0.0), reverse=True)
        return packet

    @staticmethod
    def _enforce_assertion_first_model(packet: dict) -> dict:
        """Architekturális guard rail: chunk/sentence nem lehet elsődleges truth context."""
        assertions = list(packet.get("top_assertions") or [])
        if not assertions:
            packet["evidence_sentences"] = []
            packet["source_chunks"] = []
            packet.setdefault("scoring_summary", {})
            packet["scoring_summary"]["assertion_first_enforced"] = True
            packet["scoring_summary"]["degraded_mode"] = "no_assertion_context"
            return packet
        packet.setdefault("scoring_summary", {})
        packet["scoring_summary"]["assertion_first_enforced"] = True
        packet["scoring_summary"]["truth_unit"] = "assertion"
        packet["scoring_summary"]["chunk_role"] = "secondary_evidence_view"
        return packet

    @staticmethod
    def resolve_fallback_hierarchy(assertion_hits: int, entity_hits: int, sentence_hits: int) -> list[str]:
        """Fallback sorrend: chunk csak végső szint."""
        if assertion_hits >= 2:
            return ["assertion_first"]
        if entity_hits >= 1:
            return ["entity_first", "sentence_first", "chunk_fallback"]
        if sentence_hits >= 1:
            return ["sentence_first", "chunk_fallback"]
        return ["entity_first", "sentence_first", "chunk_fallback"]

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
        ablation_mode: str = "full_context",
        debug: bool = False,
    ) -> dict:
        """Context packet építése a meglévő knowledge service-re támaszkodva."""
        retrieval_mode = str(parsed_query.get("retrieval_mode") or "assertion_first")
        parsed_query["retrieval_mode"] = retrieval_mode
        t0 = perf_counter()
        packet = await self.kb_service.build_context_for_chat(
            question=question,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
            parsed_query=parsed_query,
            kb_uuid=kb_uuid,
        )
        elapsed_ms = (perf_counter() - t0) * 1000.0
        packet = self._apply_candidate_fusion(packet)
        packet = self._enforce_assertion_first_model(packet)
        packet.setdefault("scoring_summary", {})
        packet["scoring_summary"]["ablation_mode"] = ablation_mode
        packet["scoring_summary"]["retrieval_service_ms"] = round(elapsed_ms, 2)
        packet["scoring_summary"]["fallback_hierarchy"] = self.resolve_fallback_hierarchy(
            assertion_hits=len(packet.get("top_assertions") or []),
            entity_hits=len(packet.get("related_entities") or []),
            sentence_hits=len(packet.get("evidence_sentences") or []),
        )

        if ablation_mode == "assertion_only":
            packet["expanded_assertions"] = []
            packet["supporting_assertions"] = []
            packet["evidence_sentences"] = []
            packet["source_chunks"] = []
        elif ablation_mode == "assertion_neighbors":
            packet["evidence_sentences"] = []
            packet["source_chunks"] = []
        elif ablation_mode == "assertion_neighbors_evidence":
            packet["source_chunks"] = []

        if debug:
            trace_id = str(uuid_lib.uuid4())
            rec = {
                "trace_id": trace_id,
                "query": question,
                "parsed_query": deepcopy(parsed_query),
                "top_seeds": [x.get("id") for x in (packet.get("seed_assertions") or [])[:10]],
                "expanded_assertions": [x.get("id") for x in (packet.get("expanded_assertions") or [])[:20]],
                "final_context_summary": packet.get("scoring_summary", {}),
            }
            self._debug_records.append(rec)
            self._debug_records = self._debug_records[-200:]
            self._trace_records.append(
                {
                    "trace_id": trace_id,
                    "query": question,
                    "parser_output": deepcopy(parsed_query),
                    "top_seeds": rec["top_seeds"],
                    "expanded_assertions": rec["expanded_assertions"],
                    "final_context": {
                        "top_assertions": [x.get("id") for x in (packet.get("top_assertions") or [])[:20]],
                        "key_assertions": [x.get("id") for x in (packet.get("key_assertions") or [])[:20]],
                        "evidence_count": len(packet.get("evidence_sentences") or []),
                    },
                    "answer_metadata": packet.get("scoring_summary", {}),
                }
            )
            self._persist_trace_row(self._trace_records[-1])
            self._trace_records = self._trace_records[-1000:]
            packet["retrieval_debug_record"] = rec
            packet["scoring_summary"]["trace_id"] = trace_id
        return packet

    def get_debug_records(self, limit: int = 50) -> list[dict]:
        return list(self._debug_records[-max(1, min(limit, 500)):])

    def list_traces(self, limit: int = 100) -> list[dict]:
        return list(self._trace_records[-max(1, min(limit, 1000)):])

    def capture_feedback(
        self,
        trace_id: str,
        helpful: bool | None = None,
        context_useful: bool | None = None,
        wrong_entity_resolution: bool = False,
        wrong_time_slice: bool = False,
        note: str | None = None,
    ) -> dict:
        row = {
            "trace_id": str(trace_id),
            "helpful": helpful,
            "context_useful": context_useful,
            "wrong_entity_resolution": bool(wrong_entity_resolution),
            "wrong_time_slice": bool(wrong_time_slice),
            "note": str(note or "").strip(),
        }
        self._feedback_records.append(row)
        self._persist_trace_row({"feedback": row})
        self._feedback_records = self._feedback_records[-2000:]
        return {"status": "ok", "feedback": row}

    def list_feedback(self, limit: int = 100) -> list[dict]:
        return list(self._feedback_records[-max(1, min(limit, 2000)):])
