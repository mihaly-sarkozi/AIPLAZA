from __future__ import annotations

import logging
import inspect
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Awaitable, Callable

from apps.chat.errors import ChatPermissionDenied

from core.kernel.config.config_loader import settings

logger = logging.getLogger(__name__)

_USE_KB_SEARCH = bool(getattr(settings, "chat_use_kb_search", True))
_ALLOW_LEGACY = bool(getattr(settings, "chat_allow_legacy_retrieval", False))


@dataclass(frozen=True)
class PermissionSubject:
    id: int | None
    role: str | None
    is_active: bool = True


class RetrievalContextBuilder:
    def __init__(
        self,
        *,
        kb_service: Any,
        retrieval_service: Any,
        query_parser: Any,
        context_builder: Any,
        enrich_parsed_query: Callable[[str, dict[str, Any]], dict[str, Any]],
        is_followup: Callable[[int | None, dict[str, Any]], bool],
        llm_context_text_from_packet: Callable[[dict[str, Any]], str],
        stamp_packet_kb: Callable[[dict[str, Any], str, str], None],
        merge_context_packets: Callable[..., dict[str, Any]],
    ) -> None:
        self.kb_service = kb_service
        self.retrieval_service = retrieval_service
        self.query_parser = query_parser
        self.context_builder = context_builder
        self._enrich_parsed_query = enrich_parsed_query
        self._is_followup = is_followup
        self._llm_context_text_from_packet = llm_context_text_from_packet
        self._stamp_packet_kb = stamp_packet_kb
        self._merge_context_packets = merge_context_packets

    async def _call_context_builder(
        self,
        builder: Callable[..., Awaitable[dict[str, Any]]],
        *,
        tenant: str | None,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        call_kwargs = dict(kwargs)
        if tenant is not None:
            try:
                signature = inspect.signature(builder)
                accepts_tenant = "tenant" in signature.parameters or any(
                    parameter.kind == inspect.Parameter.VAR_KEYWORD
                    for parameter in signature.parameters.values()
                )
            except (TypeError, ValueError):
                accepts_tenant = True
            if accepts_tenant:
                call_kwargs["tenant"] = tenant
        return await builder(**call_kwargs)

    async def build(
        self,
        *,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
        conversation_history: list[dict] | None = None,
        channel_id: str | None = None,
        conversation_id: str | None = None,
        channel_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        permission_subject = PermissionSubject(id=user_id, role=user_role, is_active=True) if user_id is not None else None
        t_parse = perf_counter()
        parsed = self.query_parser.parse(question) if self.query_parser is not None else {"intent": "summary"}
        parsed = self._enrich_parsed_query(question, parsed)
        parsed["parse_time_ms"] = round((perf_counter() - t_parse) * 1000.0, 2)

        can_use_kb_search = (
            bool(kb_uuid)
            and _USE_KB_SEARCH
            and self.retrieval_service is not None
            and hasattr(self.retrieval_service, "build_context_for_chat")
        )
        if self.kb_service is None and not can_use_kb_search:
            return self._empty_context_packet(parsed, user_id)

        if kb_uuid and user_id is not None and self.kb_service is not None:
            can_use = self.kb_service.user_can_use(kb_uuid, user_id, permission_subject)
            if inspect.isawaitable(can_use):
                can_use = await can_use
            if not can_use:
                raise ChatPermissionDenied("Nincs jogosultság a megadott tudástár használatához.")

        if not kb_uuid and user_id is not None:
            packet = await self._build_multi_kb_context_packet(
                question=question,
                user_id=user_id,
                user_role=user_role,
                permission_subject=permission_subject,
                parsed=parsed,
                tenant=tenant,
                debug=debug,
            )
            packet["query_focus"] = parsed
            packet["parser_audit"] = parsed.get("parser_audit") or {}
            packet.setdefault("scoring_summary", {})
            packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
            packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
            packet["is_followup"] = self._is_followup(user_id, parsed)
            return packet

        if (
            kb_uuid
            and _USE_KB_SEARCH
            and self.retrieval_service is not None
            and hasattr(self.retrieval_service, "build_context_for_chat")
        ):
            packet = await self._call_context_builder(
                self.retrieval_service.build_context_for_chat,
                tenant=tenant,
                kwargs={
                    "question": question,
                    "current_user_id": user_id,
                    "current_user_role": user_role,
                    "parsed_query": parsed,
                    "kb_uuid": kb_uuid,
                    "debug": debug,
                    "conversation_history": conversation_history,
                    "channel_id": channel_id,
                    "conversation_id": conversation_id,
                    "channel_metadata": channel_metadata,
                },
            )
            packet["query_focus"] = parsed
            packet["parser_audit"] = parsed.get("parser_audit") or {}
            packet.setdefault("scoring_summary", {})
            packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
            packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
            packet["is_followup"] = self._is_followup(user_id, parsed)
            return packet

        if user_id is not None:
            if _ALLOW_LEGACY and self.retrieval_service is not None and hasattr(self.retrieval_service, "build_context_for_chat"):
                packet = await self._call_context_builder(
                    self.retrieval_service.build_context_for_chat,
                    tenant=tenant,
                    kwargs={
                        "question": question,
                        "current_user_id": user_id,
                        "current_user_role": user_role,
                        "parsed_query": parsed,
                        "kb_uuid": kb_uuid,
                        "debug": debug,
                    },
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet
            if _ALLOW_LEGACY and hasattr(self.kb_service, "build_context_for_chat"):
                packet = await self._call_context_builder(
                    self.kb_service.build_context_for_chat,
                    tenant=tenant,
                    kwargs={
                        "question": question,
                        "current_user_id": user_id,
                        "current_user_role": user_role,
                        "parsed_query": parsed,
                        "kb_uuid": kb_uuid,
                    },
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet
            if _ALLOW_LEGACY and hasattr(self.kb_service, "build_chat_context"):
                packet = await self._call_context_builder(
                    self.kb_service.build_chat_context,
                    tenant=tenant,
                    kwargs={
                        "question": question,
                        "current_user_id": user_id,
                        "current_user_role": user_role,
                        "parsed_query": parsed,
                        "kb_uuid": kb_uuid,
                        "debug": debug,
                    },
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet

        assertions: list[dict[str, Any]] = []
        if user_id is not None:
            search_assertions = getattr(self.kb_service, "search_assertions", None)
            if search_assertions is None:
                return {
                    "query_focus": parsed,
                    "parser_audit": parsed.get("parser_audit") or {},
                    "top_assertions": [],
                    "evidence_sentences": [],
                    "source_chunks": [],
                    "related_entities": [],
                    "scoring_summary": {"latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)}},
                    "is_followup": self._is_followup(user_id, parsed),
                }
            assertions = search_assertions(
                current_user_id=user_id,
                current_user_role=user_role,
                predicates=None,
                entity_ids=None,
                limit=18,
            )
        packet = self.context_builder.build_context_packet(assertions, [], [], []) if self.context_builder is not None else {
            "top_assertions": assertions
        }
        packet["query_focus"] = parsed
        packet["parser_audit"] = parsed.get("parser_audit") or {}
        packet.setdefault("scoring_summary", {})
        packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
        packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
        packet["is_followup"] = self._is_followup(user_id, parsed)
        return packet

    async def _build_single_kb_context_packet(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        parsed: dict[str, Any],
        kb_uuid: str,
        tenant: str | None,
        debug: bool,
    ) -> dict[str, Any]:
        if self.retrieval_service is not None and hasattr(self.retrieval_service, "build_context_for_chat"):
            return await self._call_context_builder(
                self.retrieval_service.build_context_for_chat,
                tenant=tenant,
                kwargs={
                    "question": question,
                    "current_user_id": user_id,
                    "current_user_role": user_role,
                    "parsed_query": parsed,
                    "kb_uuid": kb_uuid,
                    "debug": debug,
                },
            )
        if hasattr(self.kb_service, "build_context_for_chat"):
            return await self._call_context_builder(
                self.kb_service.build_context_for_chat,
                tenant=tenant,
                kwargs={
                    "question": question,
                    "current_user_id": user_id,
                    "current_user_role": user_role,
                    "parsed_query": parsed,
                    "kb_uuid": kb_uuid,
                },
            )
        if hasattr(self.kb_service, "build_chat_context"):
            return await self._call_context_builder(
                self.kb_service.build_chat_context,
                tenant=tenant,
                kwargs={
                    "question": question,
                    "current_user_id": user_id,
                    "current_user_role": user_role,
                    "parsed_query": parsed,
                    "kb_uuid": kb_uuid,
                    "debug": debug,
                },
            )
        return {}

    async def _build_multi_kb_context_packet(
        self,
        *,
        question: str,
        user_id: int,
        user_role: str | None,
        permission_subject: PermissionSubject | None,
        parsed: dict[str, Any],
        tenant: str | None,
        debug: bool,
    ) -> dict[str, Any]:
        list_all = getattr(self.kb_service, "list_all", None)
        if not callable(list_all):
            return {
                "query_focus": parsed,
                "top_assertions": [],
                "evidence_sentences": [],
                "source_chunks": [],
                "related_entities": [],
                "scoring_summary": {"latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)}},
            }
        corpora = list_all(current_user_id=user_id, current_user=permission_subject)
        if inspect.isawaitable(corpora):
            corpora = await corpora
        candidates = [
            item
            for item in corpora
            if str(getattr(item, "uuid", "") or "").strip() and getattr(item, "deleted_at", None) is None
        ]
        diagnostics: dict[str, Any] = {
            "candidate_kb_count": len(candidates),
            "processed_kb_count": 0,
            "context_kb_count": 0,
            "permission_skipped_kb_count": 0,
            "failed_kb_count": 0,
            "empty_context_kb_count": 0,
            "ready_index_kb_count": 0,
            "candidate_kb_uuids": [],
            "context_kb_uuids": [],
            "empty_context_kb_uuids": [],
        }
        packets: list[dict[str, Any]] = []
        has_ready_index_candidate = False
        kb_names: dict[str, str] = {}
        for corpus in candidates:
            current_kb_uuid = str(getattr(corpus, "uuid", "") or "").strip()
            if not current_kb_uuid:
                continue
            current_kb_tenant = str(getattr(corpus, "tenant", "") or "").strip()
            if tenant and current_kb_tenant and current_kb_tenant != str(tenant).strip():
                diagnostics["permission_skipped_kb_count"] += 1
                continue
            diagnostics["candidate_kb_uuids"].append(current_kb_uuid)
            kb_names[current_kb_uuid] = str(getattr(corpus, "name", "") or current_kb_uuid)
            try:
                packet = await self._build_single_kb_context_packet(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    parsed=parsed,
                    kb_uuid=current_kb_uuid,
                    tenant=tenant,
                    debug=debug,
                )
            except ChatPermissionDenied:
                diagnostics["permission_skipped_kb_count"] += 1
                continue
            except Exception:
                diagnostics["failed_kb_count"] += 1
                logger.debug("chat.multi_kb_context_failed", extra={"kb_uuid": current_kb_uuid}, exc_info=True)
                continue
            if not isinstance(packet, dict):
                continue
            diagnostics["processed_kb_count"] += 1
            has_context_text = bool(self._llm_context_text_from_packet(packet).strip())
            is_ready_candidate = (not bool(packet.get("no_ready_index_build"))) or has_context_text
            if is_ready_candidate:
                has_ready_index_candidate = True
                diagnostics["ready_index_kb_count"] += 1
            packet["kb_uuid"] = current_kb_uuid
            packet["corpus_uuid"] = current_kb_uuid
            packet["kb_name"] = kb_names[current_kb_uuid]
            self._stamp_packet_kb(packet, current_kb_uuid, kb_names[current_kb_uuid])
            if has_context_text:
                diagnostics["context_kb_count"] += 1
                diagnostics["context_kb_uuids"].append(current_kb_uuid)
                packets.append(packet)
            else:
                diagnostics["empty_context_kb_count"] += 1
                diagnostics["empty_context_kb_uuids"].append(current_kb_uuid)
        return self._merge_context_packets(
            packets,
            kb_names=kb_names,
            parsed=parsed,
            no_ready_index_build=not has_ready_index_candidate,
            multi_kb_diagnostics=diagnostics,
        )

    @staticmethod
    def _empty_context_packet(parsed: dict[str, Any], user_id: int | None) -> dict[str, Any]:
        return {
            "query_focus": parsed,
            "parser_audit": parsed.get("parser_audit") or {},
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": [],
            "related_entities": [],
            "scoring_summary": {"latency_ms": {"parse": float(parsed.get("parse_time_ms") or 0.0)}},
            "is_followup": False,
        }


__all__ = ["PermissionSubject", "RetrievalContextBuilder"]
