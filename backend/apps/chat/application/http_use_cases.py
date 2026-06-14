# backend/apps/chat/application/http_use_cases.py
# Feladat: Chat HTTP endpointok use-case orchestration logikaja. A router csak
# requestet validal, dependencyt kap es ezeket a use-case-eket hivja.

from __future__ import annotations

import hashlib
import inspect
import ipaddress
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, Response as MutableResponse

from apps.chat.application.channel_request_policy import (
    channel_access_service_or_503,
    extract_channel_secret,
    tenant_required_id,
)
from apps.chat.application.channel_session_policy import (
    apply_channel_session_pacing,
    channel_session_limits,
    resolve_or_set_channel_session_id,
)
from apps.chat.router.chat_response import AskResponse
from apps.chat.application.chat_payload_policy import (
    effective_debug_for_user,
    normalize_budget_result,
    normalize_chat_payload,
    tenant_chat_limits,
    validate_chat_payload_or_413,
)
from apps.chat.errors import ChatPermissionDenied
from apps.chat.service.channel_audit import build_channel_api_audit
from apps.chat.service.chat_service import (
    ChatPolicyViolationError,
    PiiDepersonalizationUnavailableError,
)
from apps.chat.service.chat_permission_service import ChatPermissionService
from core.kernel.audit import AuditAction, AuditPort
from core.kernel.deps.facade import get_service
from core.kernel.http.security_errors import security_http_exception
from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.interface.observability import increment_metric, log_structured_event, observe_metric


def _channel_policy_reason_code(reason: str | None) -> str:
    text = str(reason or "").strip()
    if ":" in text:
        return text.split(":", 1)[0].strip() or "unknown"
    return "unknown"


def _canonical_signed_request_reason(reason: str | None) -> str:
    code = _channel_policy_reason_code(reason)
    reason_map = {
        "missing_signature_headers": "missing_signature",
        "invalid_signature": "invalid_signature",
        "expired_timestamp": "expired_timestamp",
        "reused_nonce": "reused_nonce",
        "invalid_body_hash": "invalid_body_hash",
        "redis_unavailable": "redis_unavailable",
        "missing_ip_allowlist": "ip_not_allowed",
        "credential_revoked": "credential_revoked",
        "credential_expired": "credential_expired",
    }
    return reason_map.get(code, code or "unknown")


def _hash_client_ip(remote_ip: str | None) -> str:
    raw_ip = str(remote_ip or "").strip()
    if not raw_ip:
        return "unknown"
    normalized_ip = raw_ip
    try:
        normalized_ip = str(ipaddress.ip_address(raw_ip))
    except ValueError:
        normalized_ip = raw_ip
    return hashlib.sha256(normalized_ip.encode("utf-8")).hexdigest()[:12]


def _llm_budget_manager(svc) -> Any | None:
    manager = getattr(svc, "_llm_budget_manager", None)
    if manager is None or not callable(getattr(manager, "acquire", None)) or not callable(getattr(manager, "release", None)):
        return None
    return manager


def audit_channel_policy_rejection(
    *,
    reason: str,
    tenant_id: int,
    credential_id: int | None,
    channel_id: int | None,
    remote_ip: str | None,
    path: str,
    method: str,
    request_id: str | None,
    timestamp: str | None = None,
    audit: AuditPort | None = None,
) -> None:
    reason_code = _canonical_signed_request_reason(reason)
    event_timestamp = str(timestamp or datetime.now(UTC).isoformat())
    client_ip_hash = _hash_client_ip(remote_ip)
    log_structured_event(
        "apps.chat.channel",
        "channel_api_credential.rejected",
        level=logging.WARNING,
        reason_code=reason_code,
        tenant_id=tenant_id,
        channel_id=channel_id,
        credential_id=credential_id,
        client_ip_hash=client_ip_hash,
        request_id=str(request_id or ""),
        timestamp=event_timestamp,
        path=path,
        method=method,
    )
    if audit is None:
        return
    try:
        audit.log(
            AuditAction.SIGNED_REQUEST_REJECTED,
            actor_type="api_credential",
            outcome="failure",
            target_type="channel_credential",
            target_id=str(credential_id) if credential_id is not None else None,
            details={
                "tenant_id": tenant_id,
                "channel_id": channel_id,
                "credential_id": credential_id,
                "reason": reason_code,
                "client_ip_hash": client_ip_hash,
                "timestamp": event_timestamp,
                "request_id": request_id,
                "path": path,
                "method": method,
            },
        )
    except Exception:
        log_structured_event(
            "apps.chat.channel",
            "signed_request_rejected.audit_failed",
            level=logging.WARNING,
            tenant_id=tenant_id,
            channel_id=channel_id,
            credential_id=credential_id,
            reason_code=reason_code,
        )


def audit_channel_action(
    audit: AuditPort,
    action: AuditAction,
    *,
    user_id: int | None,
    tenant_id: int,
    credential_id: int | None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        audit.log(
            action,
            user_id=user_id,
            actor_type="user",
            target_type="channel_credential",
            target_id=str(credential_id) if credential_id is not None else None,
            details={"tenant_id": tenant_id, **dict(details or {})},
        )
    except Exception:
        log_structured_event(
            "apps.chat.channel",
            "channel_credential.audit_failed",
            level=logging.WARNING,
            action=str(action),
            tenant_id=tenant_id,
            credential_id=credential_id,
        )


def audit_channel_credential_created(
    *,
    audit: AuditPort,
    user_id: int | None,
    tenant_id: int,
    created: dict[str, Any],
) -> None:
    audit_channel_action(
        audit,
        AuditAction.API_CREDENTIAL_CREATED,
        user_id=user_id,
        tenant_id=tenant_id,
        credential_id=int(created.get("id") or 0),
        details={
            "channel_type": created.get("channel_type"),
            "allowed_kb_count": len(created.get("allowed_kb_uuids") or []),
            "allowed_origin_count": len(created.get("allowed_origins") or []),
            "allowed_ip_range_count": len(created.get("allowed_ip_ranges") or []),
            "can_use_signed_request": bool(created.get("can_use_signed_request")),
            "expires_at": str(created.get("expires_at") or ""),
        },
    )


def audit_channel_credential_rotated(
    *,
    audit: AuditPort,
    user_id: int | None,
    tenant_id: int,
    credential_id: int,
    rotated: dict[str, Any],
) -> None:
    audit_channel_action(
        audit,
        AuditAction.API_CREDENTIAL_ROTATED,
        user_id=user_id,
        tenant_id=tenant_id,
        credential_id=credential_id,
        details={"rotating_until": str(rotated.get("rotating_until") or "")},
    )


def audit_channel_credential_revoked(
    *,
    audit: AuditPort,
    user_id: int | None,
    tenant_id: int,
    credential_id: int,
) -> None:
    audit_channel_action(
        audit,
        AuditAction.API_CREDENTIAL_REVOKED,
        user_id=user_id,
        tenant_id=tenant_id,
        credential_id=credential_id,
    )


def _response_from_payload(payload: dict[str, Any], *, limits: dict[str, Any], effective_debug: bool) -> AskResponse:
    response_kwargs = {
        "answer": str(payload.get("answer") or ""),
        "conversation_id": payload.get("conversation_id"),
        "turn_id": payload.get("turn_id"),
        "query_run_id": payload.get("query_run_id") or None,
        "sources": (payload.get("sources") or [])[: int(limits["max_sources"])],
        "answer_mode": str(payload.get("answer_mode") or "no_answer"),
        "answer_source": str(payload.get("answer_source") or "none"),
        "confidence": float(payload.get("confidence") or 0.0),
        "evidence": payload.get("evidence") or [],
        "cited_claim_ids": payload.get("cited_claim_ids") or [],
        "cited_sentence_ids": payload.get("cited_sentence_ids") or [],
        "cited_source_ids": payload.get("cited_source_ids") or [],
        "citations": payload.get("citations") or [],
        "citation_records": payload.get("citation_records") or [],
        "query_profile": payload.get("query_profile") or {},
        "matched_chunks": payload.get("matched_chunks") or [],
        "claims": payload.get("claims") or [],
        "context_blocks": payload.get("context_blocks") or [],
        "readiness": payload.get("readiness") or {},
        "encoded_prompt_context": str(payload.get("encoded_prompt_context") or "") if effective_debug else "",
        "restored_pii_spans": payload.get("restored_pii_spans") or [],
    }
    if effective_debug:
        response_kwargs.update({"prompt_context": payload.get("prompt_context") or {}, "debug": payload.get("debug")})
    return AskResponse(**response_kwargs)


async def handle_chat_request(*, req, tenant, current_user, svc) -> AskResponse:
    try:
        limits = tenant_chat_limits(tenant)
        normalize_chat_payload(req, limits=limits)
        validate_chat_payload_or_413(req, limits=limits)
        effective_debug = effective_debug_for_user(requested=bool(req.debug), user=current_user, limits=limits)
        usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
        allowed, reason = usage_service.can_consume_question(tenant)
        if not allowed:
            raise HTTPException(status_code=402, detail=reason)

        budget_reservation = None
        budget_manager = _llm_budget_manager(svc)
        if budget_manager is not None:
            prompt_chars = svc.estimate_prompt_chars(
                question=req.question,
                conversation_history=req.conversation_history,
                retrieval_history=req.retrieval_history,
            )
            budget_allowed, budget_reason, budget_reservation = normalize_budget_result(
                budget_manager.acquire(
                    tenant_id=int(getattr(tenant, "tenant_id", 0) or 0),
                    scope=f"tenant_chat:{str(limits.get('budget_scope') or 'default')}",
                    prompt_chars=prompt_chars,
                )
            )
            if not budget_allowed:
                increment_metric("llm.budget_reject_total", 1.0, tags={"channel": "tenant_chat"})
                detail = budget_reason or "Túl sok kérés rövid idő alatt."
                status_code = 503 if "nem elérhető" in str(detail).lower() else 429
                raise HTTPException(status_code=status_code, detail=detail)

        if hasattr(svc, "chat_with_sources"):
            chat_with_sources = getattr(svc, "chat_with_sources")
            if inspect.iscoroutinefunction(chat_with_sources):
                try:
                    payload = await chat_with_sources(
                        req.question,
                        user_id=current_user.id,
                        user_role=current_user.role,
                        kb_uuid=req.kb_uuid,
                        tenant=getattr(tenant, "slug", None),
                        debug=effective_debug,
                        conversation_history=req.conversation_history,
                        retrieval_history=req.retrieval_history,
                        conversation_id=req.conversation_id,
                        channel_id=req.channel_id or "web",
                        base_prompt_id=req.base_prompt_id,
                    )
                except TypeError:
                    try:
                        payload = await chat_with_sources(
                            req.question,
                            user_id=current_user.id,
                            user_role=current_user.role,
                            kb_uuid=req.kb_uuid,
                            tenant=getattr(tenant, "slug", None),
                            debug=effective_debug,
                        )
                    except TypeError:
                        payload = await chat_with_sources(req.question)
                finally:
                    if budget_manager is not None:
                        budget_manager.release(budget_reservation)
                usage_service.record_question(tenant, current_user.id)
                return _response_from_payload(payload, limits=limits, effective_debug=effective_debug)

        if budget_manager is not None:
            budget_manager.release(budget_reservation)
        try:
            answer = await svc.chat(
                req.question,
                user_id=current_user.id,
                user_role=current_user.role,
                kb_uuid=req.kb_uuid,
                debug=effective_debug,
                conversation_history=req.conversation_history,
                retrieval_history=req.retrieval_history,
            )
        except TypeError:
            try:
                answer = await svc.chat(
                    req.question,
                    user_id=current_user.id,
                    user_role=current_user.role,
                    kb_uuid=req.kb_uuid,
                    debug=effective_debug,
                )
            except TypeError:
                answer = await svc.chat(req.question)
    except ChatPermissionDenied as exc:
        log_structured_event(
            "apps.chat",
            "chat.permission_denied",
            level=logging.WARNING,
            reason=str(exc),
            user_id=getattr(current_user, "id", None),
            tenant_id=getattr(tenant, "tenant_id", None),
        )
        raise
    except PermissionError as exc:
        log_structured_event(
            "apps.chat",
            "chat.permission_denied",
            level=logging.WARNING,
            reason=str(exc),
            user_id=getattr(current_user, "id", None),
            tenant_id=getattr(tenant, "tenant_id", None),
        )
        raise HTTPException(status_code=403, detail="Chat permission denied.") from exc
    except ChatPolicyViolationError:
        raise
    except PiiDepersonalizationUnavailableError:
        raise

    usage_service.record_question(tenant, current_user.id)
    return AskResponse(answer=answer, sources=[], debug=None, answer_source="llm_fallback" if answer else "none")


async def handle_channel_chat_request(
    *,
    request: Request,
    req,
    tenant,
    response: MutableResponse,
    audit: AuditPort | None,
    svc,
) -> AskResponse:
    channel_svc = channel_access_service_or_503(svc)
    tenant_id = tenant_required_id(tenant)
    limits = tenant_chat_limits(tenant)
    normalize_chat_payload(req, limits=limits)
    validate_chat_payload_or_413(req, limits=limits)
    effective_debug = False
    secret = extract_channel_secret(request)
    remote_ip = request.client.host if request.client else None
    request_id = getattr(request.state, "request_id", None)
    principal, auth_reason = channel_svc.authenticate_with_reason(
        tenant_id=tenant_id,
        secret=secret,
        origin=request.headers.get("Origin"),
    )
    chat_permission_service = ChatPermissionService()
    if principal is None:
        reason_code = _canonical_signed_request_reason(auth_reason)
        increment_metric("channel.chat.rejected.auth", 1.0, tags={"reason": reason_code})
        if reason_code in {"credential_revoked", "credential_expired"}:
            audit_channel_policy_rejection(
                reason=f"{reason_code}: Channel credential rejected during authentication.",
                tenant_id=tenant_id,
                channel_id=None,
                credential_id=None,
                remote_ip=remote_ip,
                path=request.url.path,
                method=request.method,
                request_id=request_id,
                audit=audit,
            )
        raise security_http_exception(status_code=401, code="UNAUTHORIZED", message="Authentication failed.")

    raw_body = await request.body()
    if str(principal.channel_type or "").strip().lower() == "api":
        policy_allowed, policy_reason = channel_svc.authorize_api_request(
            principal,
            remote_ip=remote_ip,
            method=request.method,
            path=request.url.path,
            body=raw_body,
            timestamp=request.headers.get("X-Channel-Timestamp"),
            nonce=request.headers.get("X-Channel-Nonce"),
            signature=request.headers.get("X-Channel-Signature"),
            body_hash=request.headers.get("X-Channel-Body-SHA256"),
        )
        if not policy_allowed:
            reason_code = _canonical_signed_request_reason(policy_reason)
            increment_metric("channel.chat.rejected.api_policy", 1.0, tags={"reason": reason_code})
            audit_channel_policy_rejection(
                reason=policy_reason,
                tenant_id=tenant_id,
                channel_id=principal.credential_id,
                credential_id=principal.credential_id,
                remote_ip=remote_ip,
                path=request.url.path,
                method=request.method,
                request_id=request_id,
                audit=audit,
            )
            raise security_http_exception(status_code=401, code="UNAUTHORIZED", message="Authentication failed.")

    if not chat_permission_service.can_send_channel_message(principal, principal, tenant):
        raise security_http_exception(status_code=401, code="UNAUTHORIZED", message="Authentication failed.")

    kb_uuid = req.kb_uuid or chat_permission_service.default_channel_kb(principal)
    if not chat_permission_service.can_access_channel_kb(principal, kb_uuid):
        audit_channel_policy_rejection(
            reason="knowledge_base_scope_denied: Credential cannot access requested knowledge base.",
            tenant_id=tenant_id,
            channel_id=principal.credential_id,
            credential_id=principal.credential_id,
            remote_ip=remote_ip,
            path=request.url.path,
            method=request.method,
            request_id=request_id,
            audit=audit,
        )
        raise security_http_exception()

    session_id = resolve_or_set_channel_session_id(request, response)
    pace_allowed, retry_after_sec, wait_applied_ms = await apply_channel_session_pacing(
        tenant_id=tenant_id,
        credential_id=principal.credential_id,
        session_id=session_id,
    )
    if wait_applied_ms > 0:
        observe_metric("channel.chat.wait_applied.ms", float(wait_applied_ms), unit="ms")
    if not pace_allowed:
        increment_metric("channel.chat.rejected.too_fast", 1.0)
        raise HTTPException(
            status_code=429,
            detail="Túl gyorsan érkeznek a kérdések. Várj egy kicsit, majd próbáld újra.",
            headers={"Retry-After": str(max(1, int(retry_after_sec or 1)))},
        )

    session_limits = channel_session_limits()
    reserve_with_session = getattr(channel_svc, "reserve_question_slot_with_session", None)
    if callable(reserve_with_session):
        allowed, reason, quota_reservation = reserve_with_session(
            principal,
            session_key=f"session:{session_id}",
            session_per_minute_limit=int(session_limits["session_per_minute"]),
            session_burst_10s_limit=int(session_limits["session_burst_10s"]),
        )
    else:
        allowed, reason, quota_reservation = channel_svc.reserve_question_slot(principal)
    if not allowed:
        increment_metric("channel.chat.rejected.quota", 1.0)
        channel_svc.record_usage(
            tenant_id=tenant_id,
            credential_id=principal.credential_id,
            channel_type=principal.channel_type,
            status="rejected_quota",
            question=req.question,
            kb_uuid=kb_uuid,
            query_run_id=None,
            origin=request.headers.get("Origin"),
            remote_ip=remote_ip,
            response_ms=0,
            llm_ms=0,
            context_build_ms=0,
            total_ms=0,
        )
        detail = reason or "Túl sok kérés rövid idő alatt."
        status_code = 503 if "nem elérhető" in str(detail).lower() else 429
        raise HTTPException(status_code=status_code, detail=detail)

    budget_reservation = None
    budget_manager = _llm_budget_manager(svc)
    if budget_manager is not None:
        prompt_chars = svc.estimate_prompt_chars(
            question=req.question,
            conversation_history=req.conversation_history,
            retrieval_history=req.retrieval_history,
        )
        budget_allowed, budget_reason, budget_reservation = normalize_budget_result(
            budget_manager.acquire(
                tenant_id=tenant_id,
                scope=f"channel:{principal.credential_id}:{str(limits.get('budget_scope') or 'default')}",
                prompt_chars=prompt_chars,
            )
        )
        if not budget_allowed:
            increment_metric("llm.budget_reject_total", 1.0, tags={"channel": principal.channel_type})
            channel_svc.release_question_slot(quota_reservation)
            quota_reservation = None
            detail = budget_reason or "Túl sok kérés rövid idő alatt."
            status_code = 503 if "nem elérhető" in str(detail).lower() else 429
            raise HTTPException(status_code=status_code, detail=detail)

    channel_id, channel_metadata = build_channel_api_audit(
        channel_type=principal.channel_type,
        credential_id=principal.credential_id,
        external_session_id=session_id,
    )

    try:
        payload = await svc.chat_with_sources(
            req.question,
            user_id=None,
            user_role="channel",
            kb_uuid=kb_uuid,
            tenant=getattr(tenant, "slug", None),
            debug=effective_debug,
            conversation_history=req.conversation_history,
            retrieval_history=req.retrieval_history,
            conversation_id=session_id,
            channel_id=channel_id,
            channel_metadata=channel_metadata,
        )
    except ChatPolicyViolationError:
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
        raise
    except PiiDepersonalizationUnavailableError:
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
        raise
    except Exception:
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
        raise
    finally:
        if budget_manager is not None:
            budget_manager.release(budget_reservation)

    usage_status = "ok" if str(payload.get("answer") or "").strip() else "empty_answer"
    if usage_status != "ok":
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
    timing = ((payload.get("prompt_context") or {}).get("index_debug") or {}).get("timing_ms") if isinstance(payload, dict) else {}
    channel_svc.record_usage(
        tenant_id=tenant_id,
        credential_id=principal.credential_id,
        channel_type=principal.channel_type,
        status=usage_status,
        question=req.question,
        kb_uuid=kb_uuid,
        query_run_id=payload.get("query_run_id"),
        origin=request.headers.get("Origin"),
        remote_ip=remote_ip,
        response_ms=timing.get("total") if isinstance(timing, dict) else 0,
        llm_ms=timing.get("llm") if isinstance(timing, dict) else 0,
        context_build_ms=timing.get("context_build") if isinstance(timing, dict) else 0,
        total_ms=timing.get("total") if isinstance(timing, dict) else 0,
    )
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    usage_service.record_question(tenant, 0)
    increment_metric("channel.chat.requests", 1.0)
    if isinstance(timing, dict):
        observe_metric("channel.chat.latency.ms", float(timing.get("total") or 0.0), unit="ms")

    return _response_from_payload(payload, limits=limits, effective_debug=effective_debug)


async def handle_ws_chat_message(
    *,
    svc,
    usage_service,
    tenant,
    user,
    question: str,
    kb_uuid: str | None,
    limits: dict[str, Any],
):
    allowed, reason = usage_service.can_consume_question(tenant)
    if not allowed:
        increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "tenant_quota"})
        return {"error": reason or "Quota exceeded"}

    budget_reservation = None
    budget_manager = _llm_budget_manager(svc)
    if budget_manager is not None:
        prompt_chars = svc.estimate_prompt_chars(
            question=question,
            conversation_history=[],
            retrieval_history=[],
        )
        budget_allowed, budget_reason, budget_reservation = normalize_budget_result(
            budget_manager.acquire(
                tenant_id=int(getattr(tenant, "tenant_id", 0) or 0),
                scope=f"ws_chat:{str(limits.get('budget_scope') or 'default')}",
                prompt_chars=prompt_chars,
            )
        )
        if not budget_allowed:
            increment_metric("llm.budget_reject_total", 1.0, tags={"channel": "ws_chat"})
            detail = budget_reason or "LLM budget exceeded"
            return {
                "error": detail,
                "close_code": 1013 if "nem elérhető" in str(detail).lower() else None,
                "close_reason": "LLM budget service unavailable",
            }

    async def _stream():
        nonlocal budget_reservation
        try:
            try:
                async for chunk in svc.chat_stream(
                    question,
                    user_id=user.id,
                    user_role=user.role,
                    kb_uuid=kb_uuid or None,
                ):
                    yield {"chunk": chunk}
            except TypeError:
                async for chunk in svc.chat_stream(question):
                    yield {"chunk": chunk}
            usage_service.record_question(tenant, user.id)
            yield {"done": True}
        finally:
            if budget_manager is not None:
                budget_manager.release(budget_reservation)

    return _stream()


__all__ = [
    "audit_channel_action",
    "audit_channel_credential_created",
    "audit_channel_credential_revoked",
    "audit_channel_credential_rotated",
    "audit_channel_policy_rejection",
    "handle_channel_chat_request",
    "handle_chat_request",
    "handle_ws_chat_message",
]
