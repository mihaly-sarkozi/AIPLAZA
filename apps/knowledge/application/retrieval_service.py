from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from time import perf_counter
from typing import Any
import uuid as uuid_lib
import json
import re
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

    @staticmethod
    def _sanitize_debug_text(value: Any) -> str:
        text = str(value or "")
        if not text:
            return ""
        text = re.sub(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", "[redacted_email]", text)
        text = re.sub(r"\b(?:\+?\d[\d\s().-]{6,}\d)\b", "[redacted_phone]", text)
        text = re.sub(r"\b\d{6,}\b", "[redacted_number]", text)
        if len(text) > 400:
            text = text[:400] + "..."
        return text

    @classmethod
    def _sanitize_debug_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, item in value.items():
                key_s = str(key)
                if key_s in {"query_embedding_vector"}:
                    out[key_s] = value.get(key_s)
                    continue
                out[key_s] = cls._sanitize_debug_value(item)
            return out
        if isinstance(value, list):
            return [cls._sanitize_debug_value(x) for x in value]
        if isinstance(value, str):
            return cls._sanitize_debug_text(value)
        return value

    @staticmethod
    def _query_hash(question: str) -> str:
        return sha256(str(question or "").encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _normalize_parsed_query(parsed_query: dict, question: str) -> dict:
        parsed_query.setdefault("raw_query", str(question or "").strip())
        parsed_query.setdefault("intent", "summary")
        parsed_query.setdefault("entity_candidates", [])
        parsed_query.setdefault("resolved_entity_candidates", {})
        parsed_query.setdefault("valid_time_window", {"from": None, "to": None})
        parsed_query.setdefault("place_candidates", [])
        parsed_query.setdefault("resolved_place_candidates", [])
        parsed_query.setdefault("predicate_candidates", [])
        parsed_query.setdefault("relation_candidates", [])
        parsed_query.setdefault("attribute_candidates", [])
        parsed_query.setdefault("lexical_focus_terms", [])
        parsed_query.setdefault("exact_phrase_candidates", [])
        parsed_query.setdefault("rare_entity_terms", [])
        parsed_query.setdefault("hybrid_profile", {})
        parsed_query.setdefault("normalized_query_text", str(question or "").strip().lower())
        parsed_query.setdefault("lexical_query_text", parsed_query.get("normalized_query_text") or str(question or "").strip().lower())
        parsed_query.setdefault("query_embedding_text", parsed_query.get("normalized_query_text") or str(question or "").strip())
        parsed_query.setdefault("focus_axes", {})
        parsed_query.setdefault("parser_audit", {})
        parsed_query.setdefault("parse_time_ms", 0.0)
        parsed_query.setdefault("query_embedding_prepare_calls", 0)
        parsed_query.setdefault("query_embedding_generation_count", 0)
        retrieval_mode = str(parsed_query.get("retrieval_mode") or "assertion_first")
        parsed_query["retrieval_mode"] = retrieval_mode
        return parsed_query

    async def prepare_query_embedding(self, parsed_query: dict, question: str) -> dict:
        """Request-szintű query embedding előkészítése egyszer."""
        if not isinstance(parsed_query, dict):
            return {"prepared": False, "reason": "invalid_parsed_query"}
        parsed_query["query_embedding_prepare_calls"] = int(parsed_query.get("query_embedding_prepare_calls") or 0) + 1
        qdrant = getattr(self.kb_service, "qdrant", None)
        if qdrant is None or not hasattr(qdrant, "embed_text"):
            parsed_query.setdefault("query_embedding_vector", None)
            parsed_query.setdefault("query_embedding_time_ms", 0.0)
            return {"prepared": False, "reason": "qdrant_not_available"}
        if parsed_query.get("query_embedding_vector") is not None:
            parsed_query.setdefault("query_embedding_time_ms", 0.0)
            parsed_query["query_embedding_reused"] = True
            return {"prepared": True, "reused": True, "embedding_time_ms": float(parsed_query.get("query_embedding_time_ms") or 0.0)}
        query_text = str(parsed_query.get("query_embedding_text") or question or "").strip()
        if not query_text:
            parsed_query["query_embedding_vector"] = None
            parsed_query["query_embedding_time_ms"] = 0.0
            return {"prepared": False, "reason": "empty_query"}
        t0 = perf_counter()
        vector = await qdrant.embed_text(query_text)
        elapsed = (perf_counter() - t0) * 1000.0
        parsed_query["query_embedding_vector"] = vector
        parsed_query["query_embedding_time_ms"] = round(elapsed, 2)
        parsed_query["query_embedding_reused"] = False
        parsed_query["query_embedding_generation_count"] = int(parsed_query.get("query_embedding_generation_count") or 0) + 1
        return {"prepared": True, "reused": False, "embedding_time_ms": float(parsed_query["query_embedding_time_ms"])}

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
            rel_conf = float(row.get("relation_confidence") or 0.0)
            rel_weight = float(row.get("relation_weight") or 0.0)
            relation_component = (0.65 * rel_conf) + (0.35 * rel_weight)
            noisy_penalty = 0.12 if str(row.get("relation_type") or "").strip() and rel_conf < 0.30 else 0.0
            row["fusion_rank_score"] = (
                (0.58 * norm_final)
                + (0.22 * semantic)
                + (0.10 * lexical)
                + (0.10 * relation_component)
                - noisy_penalty
            )
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
        parsed_query = self._normalize_parsed_query(parsed_query=parsed_query, question=question)
        retrieval_mode = str(parsed_query.get("retrieval_mode") or "assertion_first")
        parsed_query["retrieval_mode"] = retrieval_mode
        await self.prepare_query_embedding(parsed_query=parsed_query, question=question)
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
        packet["scoring_summary"]["place_context_count"] = len(packet.get("related_places") or [])
        packet["scoring_summary"]["local_assertion_space"] = packet.get("local_assertion_space") or {}
        packet["scoring_summary"]["assertion_neighborhood_count"] = len(packet.get("assertion_neighborhoods") or [])
        packet["scoring_summary"]["assertion_mention_trace_count"] = len(packet.get("assertion_mention_traces") or [])
        packet["scoring_summary"]["parser_intent"] = parsed_query.get("intent")
        packet["scoring_summary"]["parser_focus_axes"] = parsed_query.get("focus_axes") or {}
        packet["scoring_summary"]["parser_audit"] = parsed_query.get("parser_audit") or {}
        packet["scoring_summary"]["entity_candidates"] = parsed_query.get("entity_candidates") or []
        packet["scoring_summary"]["predicate_candidates"] = parsed_query.get("predicate_candidates") or []
        packet["scoring_summary"]["relation_candidates"] = parsed_query.get("relation_candidates") or []
        packet["scoring_summary"]["attribute_candidates"] = parsed_query.get("attribute_candidates") or []
        packet["scoring_summary"]["resolved_place_candidates"] = parsed_query.get("resolved_place_candidates", {})
        packet["scoring_summary"]["resolved_place_hierarchy_keys"] = parsed_query.get("resolved_place_hierarchy_keys", {})
        packet["scoring_summary"]["place_debug_top"] = [
            {
                "place_key": x.get("place_key"),
                "best_place_match": float(x.get("best_place_match") or 0.0),
                "mention_count_in_context": int(x.get("mention_count_in_context") or 0),
                "hierarchy_keys": x.get("hierarchy_keys") or [],
            }
            for x in (packet.get("related_places") or [])[:10]
        ]
        packet["scoring_summary"]["query_embedding_reused"] = bool(parsed_query.get("query_embedding_reused") or False)
        packet["scoring_summary"]["parse_time_ms"] = float(parsed_query.get("parse_time_ms") or 0.0)
        packet["scoring_summary"]["query_embedding_time_ms"] = float(parsed_query.get("query_embedding_time_ms") or 0.0)
        packet["scoring_summary"]["query_embedding_prepare_calls"] = int(parsed_query.get("query_embedding_prepare_calls") or 0)
        packet["scoring_summary"]["query_embedding_generation_count"] = int(parsed_query.get("query_embedding_generation_count") or 0)
        relation_rows = [x for x in (packet.get("top_assertions") or []) if str(x.get("relation_type") or "").strip()]
        packet["scoring_summary"]["relation_debug_top"] = [
            {
                "assertion_id": x.get("id"),
                "relation_type": x.get("relation_type"),
                "weight": float(x.get("relation_weight") or 0.0),
                "confidence": float(x.get("relation_confidence") or 0.0),
            }
            for x in sorted(
                relation_rows,
                key=lambda r: (
                    float(r.get("relation_confidence") or 0.0),
                    float(r.get("relation_weight") or 0.0),
                ),
                reverse=True,
            )[:10]
        ]
        packet["scoring_summary"]["hybrid_score_top"] = [
            {
                "assertion_id": x.get("id"),
                "point_type": x.get("point_type"),
                "semantic_score": float(x.get("semantic_match") or 0.0),
                "lexical_score": float(x.get("lexical_match") or 0.0),
                "fusion_score": float(x.get("fusion_match") or x.get("final_score") or 0.0),
                "final_score": float(x.get("final_score") or x.get("fusion_rank_score") or 0.0),
            }
            for x in (packet.get("top_assertions") or [])[:10]
        ]

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
            parsed_query_debug = deepcopy(parsed_query)
            if isinstance(parsed_query_debug, dict) and parsed_query_debug.get("query_embedding_vector") is not None:
                vec_len = len(parsed_query_debug.get("query_embedding_vector") or [])
                parsed_query_debug["query_embedding_vector"] = f"<reused_vector:{vec_len}>"
            parsed_query_debug = self._sanitize_debug_value(parsed_query_debug)
            safe_query = self._sanitize_debug_text(question)
            rec = {
                "trace_id": trace_id,
                "query": safe_query,
                "query_hash": self._query_hash(question),
                "parsed_query": parsed_query_debug,
                "top_seeds": [x.get("id") for x in (packet.get("seed_assertions") or [])[:10]],
                "expanded_assertions": [x.get("id") for x in (packet.get("expanded_assertions") or [])[:20]],
                "final_context_summary": packet.get("scoring_summary", {}),
                "parser_vs_retrieval_audit": {
                    "parser_intent": parsed_query_debug.get("intent"),
                    "retrieval_mode": parsed_query_debug.get("retrieval_mode"),
                    "entity_candidates": parsed_query_debug.get("entity_candidates") or [],
                    "resolved_entity_candidates": parsed_query_debug.get("resolved_entity_candidates") or {},
                    "place_candidates": parsed_query_debug.get("place_candidates") or [],
                    "resolved_place_candidates": parsed_query_debug.get("resolved_place_candidates") or [],
                    "valid_time_window": parsed_query_debug.get("valid_time_window") or {},
                },
            }
            self._debug_records.append(rec)
            self._debug_records = self._debug_records[-200:]
            self._trace_records.append(
                {
                    "trace_id": trace_id,
                    "query": safe_query,
                    "query_hash": self._query_hash(question),
                    "parser_output": parsed_query_debug,
                    "top_seeds": rec["top_seeds"],
                    "expanded_assertions": rec["expanded_assertions"],
                    "final_context": {
                        "top_assertions": [x.get("id") for x in (packet.get("top_assertions") or [])[:20]],
                        "key_assertions": [x.get("id") for x in (packet.get("key_assertions") or [])[:20]],
                        "seed_assertions": [x.get("id") for x in (packet.get("seed_assertions") or [])[:20]],
                        "local_assertion_space": packet.get("local_assertion_space") or {},
                        "evidence_count": len(packet.get("evidence_sentences") or []),
                        "assertion_neighborhood_count": len(packet.get("assertion_neighborhoods") or []),
                        "assertion_mention_trace_count": len(packet.get("assertion_mention_traces") or []),
                        "related_places": [x.get("place_key") for x in (packet.get("related_places") or [])[:20]],
                        "place_debug_top": packet.get("scoring_summary", {}).get("place_debug_top", []),
                        "relation_debug_top": packet.get("scoring_summary", {}).get("relation_debug_top", []),
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
