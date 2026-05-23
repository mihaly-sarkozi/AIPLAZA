from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from core.kernel.interface.observability import increment_metric, log_structured_event, observe_metric
from shared.utils import sanitize_log_data

logger = logging.getLogger(__name__)


class ChatTelemetryService:
    def record_missing_context_if_needed(
        self,
        *,
        packet: dict[str, Any],
        question: str,
        user_id: int | None,
        kb_uuid: str | None,
    ) -> None:
        build_ids = packet.get("build_ids") if isinstance(packet, dict) else None
        has_ready_build_reference = isinstance(build_ids, list) and any(str(item or "").strip() for item in build_ids)
        should_show_missing_index_message = bool(packet.get("no_ready_index_build")) and not has_ready_build_reference
        if not should_show_missing_index_message:
            return
        increment_metric("chat_missing_ready_index_detected_total", 1)
        log_structured_event(
            "apps.chat",
            "chat.context.empty_missing_ready_index",
            level=logging.WARNING,
            user_id=user_id,
            kb_uuid=str(packet.get("kb_uuid") or packet.get("corpus_uuid") or kb_uuid or "").strip() or None,
            no_ready_index_build=True,
            has_ready_build_reference=has_ready_build_reference,
            query_preview=sanitize_log_data({"query_preview": str(question or "")[:160]}).get("query_preview"),
        )

    def record_timing(
        self,
        *,
        packet: dict[str, Any],
        context_build_ms: float,
        llm_ms: float,
        started_at: float,
        user_role: str | None,
        kb_uuid: str | None,
        context_text: str,
        context_failed: bool,
        prompt_context: dict[str, Any],
        encoded_answer_text: str,
    ) -> None:
        packet["_chat_timing_ms"] = {
            "context_build": context_build_ms,
            "llm": llm_ms,
            "total": round((perf_counter() - started_at) * 1000.0, 2),
        }
        timing_tags = {"channel": str(user_role or "user").strip().lower() or "user"}
        total_ms = float(packet["_chat_timing_ms"]["total"])
        increment_metric("chat_requests_total", 1.0, tags=timing_tags)
        observe_metric("chat_latency_seconds", total_ms / 1000.0, unit="seconds", tags=timing_tags)
        observe_metric("retrieval_latency_seconds", float(context_build_ms) / 1000.0, unit="seconds", tags=timing_tags)
        observe_metric("llm_cost_estimate", 0.0, unit="usd", tags=timing_tags)
        if isinstance(prompt_context, dict):
            prompt_context["encoded_answer_text"] = str(encoded_answer_text or "").strip()
            index_debug = prompt_context.get("index_debug")
            if isinstance(index_debug, dict):
                index_debug["timing_ms"] = packet.get("_chat_timing_ms") or {}
        logger.info(
            "chat_with_sources timing ms",
            extra={
                "timing_ms": packet.get("_chat_timing_ms"),
                "kb_uuid": str(kb_uuid or "").strip() or "all",
                "has_context": bool(context_text and not context_failed),
            },
        )


__all__ = ["ChatTelemetryService"]
