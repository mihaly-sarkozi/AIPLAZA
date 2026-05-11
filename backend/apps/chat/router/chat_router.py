# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
import asyncio
import inspect
import json
import re
import secrets
import threading
from typing import Any
from datetime import datetime
from time import monotonic
from collections import deque
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request, Response as MutableResponse, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from apps.chat.dependencies import get_chat_service
from core.kernel.config.config_loader import settings
from core.kernel.config.environment import get_app_env
from core.di import RequiredTenantContextDep, get_service, get_tenant_repository
from core.platform.service_keys import PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.security.rate_limit import get_rate_limit_redis, limiter
from core.platform.contract.observability import increment_metric, observe_metric
from core.capabilities.users.dto import User
from core.platform.auth.auth_dependencies import get_current_user, require_permission, validate_ws_token
from core.kernel.security.cookie_policy import (
    CHANNEL_CHAT_SESSION_COOKIE_NAME,
    set_channel_chat_session_cookie,
    set_ws_token_cookie,
)

from apps.chat.router.chat_requests import (
    AskRequest,
    ChannelAskRequest,
    ChannelCredentialCreateRequest,
    ChannelCredentialPolicyUpdateRequest,
    ChannelFeedbackCaptureRequest,
    ChannelFeedbackTriageRequest,
    ChatFeedbackRequest,
)
from apps.chat.router.chat_response import AskResponse
from apps.chat.service.chat_service import ChatPolicyViolationError, PiiDepersonalizationUnavailableError

router = APIRouter()
_ws_lock = threading.Lock()
_ws_fallback_buckets: dict[str, deque[float]] = {}
_ws_connections_lock = threading.Lock()
_ws_connection_counts: dict[str, int] = {}
_WS_BURST_WINDOW_SEC = 10
_channel_session_lock = threading.Lock()
_channel_session_last_seen_ms: dict[str, int] = {}


def _ws_limit_per_10s() -> int:
    return max(1, int(getattr(settings, "ws_chat_max_messages_per_10s", 20) or 20))


def _ws_idle_timeout_sec() -> int:
    return max(5, int(getattr(settings, "ws_chat_idle_timeout_sec", 45) or 45))


def _ws_max_message_chars() -> int:
    return max(256, int(getattr(settings, "ws_chat_max_message_chars", 8000) or 8000))


def _ws_enabled() -> bool:
    return bool(getattr(settings, "enable_chat_websocket", False))


def _ws_max_connections_per_tenant() -> int:
    return max(1, int(getattr(settings, "ws_chat_max_connections_per_tenant", 20) or 20))


def _ws_max_connections_per_user() -> int:
    return max(1, int(getattr(settings, "ws_chat_max_connections_per_user", 3) or 3))


def _ws_rate_limit_key(*, tenant_slug: str | None, user_id: int | None, remote_ip: str | None) -> str:
    tenant_part = str(tenant_slug or "").strip().lower() or "_"
    actor = f"user:{int(user_id)}" if user_id else f"ip:{str(remote_ip or '').strip() or 'unknown'}"
    return f"ws:{tenant_part}:{actor}"


def _ws_allow_message(*, tenant_slug: str | None, user_id: int | None, remote_ip: str | None) -> bool:
    key = _ws_rate_limit_key(tenant_slug=tenant_slug, user_id=user_id, remote_ip=remote_ip)
    now = monotonic()
    redis_client = get_rate_limit_redis()
    if redis_client is not None:
        window_bucket = int(now // _WS_BURST_WINDOW_SEC)
        redis_key = f"rl:{key}:{window_bucket}"
        try:
            count = int(redis_client.incr(redis_key, 1) or 0)
            redis_client.expire(redis_key, _WS_BURST_WINDOW_SEC + 3)
            return count <= _ws_limit_per_10s()
        except Exception:
            pass
    with _ws_lock:
        bucket = _ws_fallback_buckets.get(key) or deque()
        while bucket and now - bucket[0] > _WS_BURST_WINDOW_SEC:
            bucket.popleft()
        if len(bucket) >= _ws_limit_per_10s():
            _ws_fallback_buckets[key] = bucket
            return False
        bucket.append(now)
        _ws_fallback_buckets[key] = bucket
    return True


def _ws_connection_keys(*, tenant_slug: str | None, user_id: int | None) -> tuple[str, str]:
    tenant_key = str(tenant_slug or "").strip().lower() or "_"
    user_key = str(int(user_id or 0))
    return (
        f"ws:conn:tenant:{tenant_key}",
        f"ws:conn:user:{tenant_key}:{user_key}",
    )


def _ws_try_acquire_connection(*, tenant_slug: str | None, user_id: int | None) -> tuple[bool, str, dict[str, str] | None]:
    tenant_conn_key, user_conn_key = _ws_connection_keys(tenant_slug=tenant_slug, user_id=user_id)
    redis_client = get_rate_limit_redis()
    if redis_client is not None:
        try:
            tenant_count = int(redis_client.incr(tenant_conn_key, 1) or 0)
            user_count = int(redis_client.incr(user_conn_key, 1) or 0)
            redis_client.expire(tenant_conn_key, 3600)
            redis_client.expire(user_conn_key, 3600)
            if tenant_count > _ws_max_connections_per_tenant():
                redis_client.decr(tenant_conn_key, 1)
                redis_client.decr(user_conn_key, 1)
                return False, "Túl sok párhuzamos websocket kapcsolat tenant szinten.", None
            if user_count > _ws_max_connections_per_user():
                redis_client.decr(tenant_conn_key, 1)
                redis_client.decr(user_conn_key, 1)
                return False, "Túl sok párhuzamos websocket kapcsolat felhasználói szinten.", None
            return True, "", {"backend": "redis", "tenant_conn_key": tenant_conn_key, "user_conn_key": user_conn_key}
        except Exception:
            pass
    with _ws_connections_lock:
        tenant_count = int(_ws_connection_counts.get(tenant_conn_key, 0))
        user_count = int(_ws_connection_counts.get(user_conn_key, 0))
        if tenant_count >= _ws_max_connections_per_tenant():
            return False, "Túl sok párhuzamos websocket kapcsolat tenant szinten.", None
        if user_count >= _ws_max_connections_per_user():
            return False, "Túl sok párhuzamos websocket kapcsolat felhasználói szinten.", None
        _ws_connection_counts[tenant_conn_key] = tenant_count + 1
        _ws_connection_counts[user_conn_key] = user_count + 1
    return True, "", {"backend": "memory", "tenant_conn_key": tenant_conn_key, "user_conn_key": user_conn_key}


def _ws_release_connection(reservation: dict[str, str] | None) -> None:
    if not reservation:
        return
    tenant_conn_key = str(reservation.get("tenant_conn_key") or "").strip()
    user_conn_key = str(reservation.get("user_conn_key") or "").strip()
    if not tenant_conn_key or not user_conn_key:
        return
    if str(reservation.get("backend") or "") == "redis":
        redis_client = get_rate_limit_redis()
        if redis_client is None:
            return
        try:
            redis_client.decr(tenant_conn_key, 1)
            redis_client.decr(user_conn_key, 1)
        except Exception:
            return
        return
    with _ws_connections_lock:
        for key in (tenant_conn_key, user_conn_key):
            current = int(_ws_connection_counts.get(key, 0))
            if current <= 1:
                _ws_connection_counts.pop(key, None)
            else:
                _ws_connection_counts[key] = current - 1


def _tenant_chat_limits(tenant) -> dict[str, int | bool]:
    config = getattr(tenant, "config", None)
    flags = getattr(config, "feature_flags", None) or {}
    package = str(getattr(config, "package", "") or "").strip().lower()
    is_demo = bool(flags.get("demo_mode"))
    is_starter = package == "starter"
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    if is_demo:
        return {
            "max_question_chars": max(64, int(getattr(settings, "chat_demo_max_question_chars", 1024) or 1024)),
            "max_history_items": max(0, int(getattr(settings, "chat_demo_max_history_items", 8) or 8)),
            "max_history_chars": max(0, int(getattr(settings, "chat_demo_max_history_chars", 2400) or 2400)),
            "max_retrieval_items": max(0, int(getattr(settings, "chat_demo_max_retrieval_items", 6) or 6)),
            "max_retrieval_chars": max(0, int(getattr(settings, "chat_demo_max_retrieval_chars", 1800) or 1800)),
            "max_sources": max(1, int(getattr(settings, "chat_demo_max_sources", 3) or 3)),
            "allow_debug": bool(getattr(settings, "chat_demo_allow_debug", False)) or env != "prod",
            "channel_daily_limit_cap": max(1, int(getattr(settings, "channel_demo_max_daily_limit", 100) or 100)),
            "channel_per_minute_limit_cap": max(1, int(getattr(settings, "channel_demo_max_per_minute_limit", 10) or 10)),
            "budget_scope": "demo",
        }
    default_sources = max(1, int(getattr(settings, "chat_default_max_sources", 8) or 8))
    return {
        "max_question_chars": max(64, int(getattr(settings, "chat_max_input_chars", 2400) or 2400)),
        "max_history_items": max(0, int(getattr(settings, "chat_max_history_items", 30) or 30)),
        "max_history_chars": max(0, int(getattr(settings, "chat_max_history_chars", 12000) or 12000)),
        "max_retrieval_items": max(0, int(getattr(settings, "chat_max_retrieval_items", 20) or 20)),
        "max_retrieval_chars": max(0, int(getattr(settings, "chat_max_retrieval_chars", 6000) or 6000)),
        "max_sources": max(1, int(getattr(settings, "chat_starter_max_sources", 5) or 5)) if is_starter else default_sources,
        "allow_debug": True,
        "channel_daily_limit_cap": max(1, int(getattr(settings, "channel_default_max_daily_limit", 5000) or 5000)),
        "channel_per_minute_limit_cap": max(1, int(getattr(settings, "channel_default_max_per_minute_limit", 120) or 120)),
        "budget_scope": "starter" if is_starter else "default",
    }


def _validate_chat_payload_or_413(req, *, limits: dict[str, int | bool]) -> None:
    question = str(getattr(req, "question", "") or "")
    if len(question) > int(limits["max_question_chars"]):
        raise HTTPException(status_code=413, detail="A kérdés túl hosszú ehhez a csomaghoz.")
    conversation_history = list(getattr(req, "conversation_history", []) or [])
    retrieval_history = list(getattr(req, "retrieval_history", []) or [])
    if len(conversation_history) > int(limits["max_history_items"]):
        raise HTTPException(status_code=413, detail="Túl sok conversation history elem.")
    if len(retrieval_history) > int(limits["max_retrieval_items"]):
        raise HTTPException(status_code=413, detail="Túl sok retrieval history elem.")
    history_chars = 0
    for row in conversation_history:
        if isinstance(row, dict):
            history_chars += len(str(row.get("content") or row.get("text") or ""))
    retrieval_chars = sum(len(str(item or "")) for item in retrieval_history)
    if history_chars > int(limits["max_history_chars"]):
        raise HTTPException(status_code=413, detail="A conversation history mérete túl nagy ehhez a csomaghoz.")
    if retrieval_chars > int(limits["max_retrieval_chars"]):
        raise HTTPException(status_code=413, detail="A retrieval history mérete túl nagy ehhez a csomaghoz.")


def _split_sentences(text: str) -> list[str]:
    parts = re.findall(r"[^.!?]+[.!?]?", str(text or ""))
    return [part.strip() for part in parts if part and part.strip()]


def _normalize_chat_payload(req, *, limits: dict[str, int | bool]) -> None:
    question = str(getattr(req, "question", "") or "").strip()
    question_words = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]+", question)
    question_sentences = _split_sentences(question)
    if len(question_sentences) > 4 or len(question_words) > 30:
        raise HTTPException(status_code=422, detail="Egyszerre csak egy rövid mondatra tudok válaszolni.")
    if len(question_sentences) > 2:
        question = " ".join(question_sentences[:2]).strip()
    max_question_chars = int(limits["max_question_chars"])
    if len(question) > max_question_chars:
        question = question[:max_question_chars].rstrip()
    req.question = question

    conversation_history = list(getattr(req, "conversation_history", []) or [])
    max_history_items = int(limits["max_history_items"])
    max_history_chars = int(limits["max_history_chars"])
    if len(conversation_history) > max_history_items:
        conversation_history = conversation_history[-max_history_items:]
    while conversation_history:
        history_chars = sum(len(str((row or {}).get("content") or (row or {}).get("text") or "")) for row in conversation_history if isinstance(row, dict))
        if history_chars <= max_history_chars:
            break
        conversation_history = conversation_history[1:]
    req.conversation_history = conversation_history

    retrieval_history = list(getattr(req, "retrieval_history", []) or [])
    max_retrieval_items = int(limits["max_retrieval_items"])
    max_retrieval_chars = int(limits["max_retrieval_chars"])
    if len(retrieval_history) > max_retrieval_items:
        retrieval_history = retrieval_history[-max_retrieval_items:]
    while retrieval_history and sum(len(str(item or "")) for item in retrieval_history) > max_retrieval_chars:
        retrieval_history = retrieval_history[1:]
    req.retrieval_history = retrieval_history


def _debug_responses_globally_enabled() -> bool:
    enabled = bool(getattr(settings, "chat_debug_responses_enabled", True))
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    if env == "prod" and not enabled:
        return False
    return enabled


def _effective_debug_for_user(*, requested: bool, user: User, limits: dict[str, int | bool]) -> bool:
    if not requested:
        return False
    if not _debug_responses_globally_enabled():
        return False
    if not bool(limits.get("allow_debug")):
        return False
    # Debug nézetet a chat felületen minden bejelentkezett user kérhesse,
    # különben a forrás/context átláthatóság félrevezetően üres lehet.
    return bool(getattr(user, "id", None))


def _normalize_budget_result(raw: Any) -> tuple[bool, str, dict[str, Any] | None]:
    if isinstance(raw, tuple) and len(raw) == 3:
        return bool(raw[0]), str(raw[1] or ""), raw[2] if isinstance(raw[2], dict) or raw[2] is None else None
    if raw is None:
        return True, "", None
    if isinstance(raw, bool):
        return raw, "", None
    if isinstance(raw, dict):
        return True, "", raw
    return True, "", None

@router.get("/chat/ws-token")
@limiter.limit("60/minute")
async def chat_ws_token(
    request: Request,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
):
    """
    WebSocket auth: Bearer token → ws_token HttpOnly cookie (rövid életű).
    A frontend ezt hívja credentials-szel; utána a /chat/ws kapcsolat a cookie-t küldi (token nem kerül URL-be/logokba).
    """
    if not _ws_enabled():
        raise HTTPException(status_code=503, detail="Websocket chat le van tiltva.")
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization")
    token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    response = Response(status_code=204)
    set_ws_token_cookie(
        response,
        token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
    )
    return response


# Ez az aszinkron függvény a(z) chat logikáját valósítja meg.
@router.post(
    "/chat",
    response_model=AskResponse,
    response_model_exclude_none=True,
)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: AskRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    try:
        limits = _tenant_chat_limits(tenant)
        _normalize_chat_payload(req, limits=limits)
        _validate_chat_payload_or_413(req, limits=limits)
        effective_debug = _effective_debug_for_user(requested=bool(req.debug), user=current_user, limits=limits)
        usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
        allowed, reason = usage_service.can_consume_question(tenant)
        if not allowed:
            raise HTTPException(status_code=402, detail=reason)
        budget_reservation = None
        if hasattr(svc, "acquire_llm_budget"):
            prompt_chars = svc.estimate_prompt_chars(
                question=req.question,
                conversation_history=req.conversation_history,
                retrieval_history=req.retrieval_history,
            )
            budget_allowed, budget_reason, budget_reservation = _normalize_budget_result(svc.acquire_llm_budget(
                tenant_id=int(getattr(tenant, "tenant_id", 0) or 0),
                scope=f"tenant_chat:{str(limits.get('budget_scope') or 'default')}",
                prompt_chars=prompt_chars,
            ))
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
                        debug=effective_debug,
                        conversation_history=req.conversation_history,
                        retrieval_history=req.retrieval_history,
                    )
                except TypeError:
                    # Backward compatibility régi ChatService mock/signature esetére.
                    try:
                        payload = await chat_with_sources(
                            req.question,
                            user_id=current_user.id,
                            user_role=current_user.role,
                            kb_uuid=req.kb_uuid,
                            debug=effective_debug,
                        )
                    except TypeError:
                        payload = await chat_with_sources(req.question)
                finally:
                    if hasattr(svc, "release_llm_budget"):
                        svc.release_llm_budget(budget_reservation)
                usage_service.record_question(tenant, current_user.id)
                response_kwargs = {
                    "answer": str(payload.get("answer") or ""),
                    "query_run_id": payload.get("query_run_id") or None,
                    "sources": (payload.get("sources") or [])[: int(limits["max_sources"])],
                    "answer_mode": str(payload.get("answer_mode") or "no_answer"),
                    "answer_source": str(payload.get("answer_source") or "none"),
                    "confidence": float(payload.get("confidence") or 0.0),
                    "evidence": payload.get("evidence") or [],
                    "cited_claim_ids": payload.get("cited_claim_ids") or [],
                    "cited_sentence_ids": payload.get("cited_sentence_ids") or [],
                    "cited_source_ids": payload.get("cited_source_ids") or [],
                    "query_profile": payload.get("query_profile") or {},
                    "matched_chunks": payload.get("matched_chunks") or [],
                    "claims": payload.get("claims") or [],
                    "context_blocks": payload.get("context_blocks") or [],
                    "encoded_prompt_context": str(payload.get("encoded_prompt_context") or "") if effective_debug else "",
                    "restored_pii_spans": payload.get("restored_pii_spans") or [],
                }
                if effective_debug:
                    response_kwargs.update(
                        {
                            "prompt_context": payload.get("prompt_context") or {},
                            "debug": payload.get("debug"),
                        }
                    )
                return AskResponse(
                    **response_kwargs,
                )
        if hasattr(svc, "release_llm_budget"):
            svc.release_llm_budget(budget_reservation)
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
            # Backward compatibility régi ChatService mock/signature esetére.
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
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ChatPolicyViolationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except PiiDepersonalizationUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    usage_service.record_question(tenant, current_user.id)
    return AskResponse(answer=answer, sources=[], debug=None, answer_source="llm_fallback" if answer else "none")


@router.post("/chat/feedback")
@limiter.limit("60/minute")
async def chat_feedback(
    request: Request,
    req: ChatFeedbackRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    if not hasattr(svc, "capture_retrieval_feedback"):
        return {"status": "skipped", "reason": "feedback_service_not_available"}
    return svc.capture_retrieval_feedback(
        trace_id=req.trace_id,
        helpful=req.helpful,
        note=req.note,
    )


@router.get("/chat/sources/{query_run_id}/{source_id}/download")
@limiter.limit("60/minute")
async def chat_source_download(
    request: Request,
    query_run_id: str,
    source_id: str,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    if not hasattr(svc, "download_answer_source"):
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        download = svc.download_answer_source(
            query_run_id=query_run_id,
            source_id=source_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if download is None:
        raise HTTPException(status_code=404, detail="Source not found")
    filename = str(download.get("filename") or f"aiplaza-context-{source_id[:8]}.txt")
    return Response(
        content=download.get("body") or b"",
        media_type=str(download.get("content_type") or "text/plain; charset=utf-8"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/chat/context/{query_run_id}/download")
@limiter.limit("60/minute")
async def chat_context_download(
    request: Request,
    query_run_id: str,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    if not hasattr(svc, "download_answer_context"):
        raise HTTPException(status_code=404, detail="Context not found")
    try:
        download = svc.download_answer_context(
            query_run_id=query_run_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if download is None:
        raise HTTPException(status_code=404, detail="Context not found")
    filename = str(download.get("filename") or f"aiplaza-llm-context-{query_run_id[:8]}.txt")
    return Response(
        content=download.get("body") or b"",
        media_type=str(download.get("content_type") or "text/plain; charset=utf-8"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def _channel_access_service_or_503(svc):
    channel_svc = getattr(svc, "channel_access_service", None)
    if channel_svc is None:
        raise HTTPException(status_code=503, detail="Channel access service not available")
    return channel_svc


def _parse_iso_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid expires_at format") from exc


def _extract_channel_secret(request: Request) -> str:
    auth = str(request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    api_key = str(request.headers.get("X-API-Key") or "").strip()
    if api_key:
        return api_key
    raise HTTPException(status_code=401, detail="Missing channel credential")


def _tenant_required_id(tenant) -> int:
    tenant_id = int(getattr(tenant, "tenant_id", 0) or 0)
    if tenant_id <= 0:
        raise HTTPException(status_code=400, detail="Tenant context missing")
    return tenant_id


def _channel_session_limits() -> dict[str, int]:
    return {
        "session_per_minute": max(1, int(getattr(settings, "channel_session_max_per_minute", 30) or 30)),
        "session_burst_10s": max(1, int(getattr(settings, "channel_session_max_burst_10s", 5) or 5)),
        "session_min_interval_ms": max(1, int(getattr(settings, "channel_session_min_interval_ms", 1500) or 1500)),
        "session_wait_max_ms": max(0, int(getattr(settings, "channel_session_wait_max_ms", 900) or 900)),
        "session_cookie_max_age_sec": max(60, int(getattr(settings, "channel_session_cookie_max_age_sec", 86400) or 86400)),
    }


def _resolve_or_set_channel_session_id(request: Request, response: MutableResponse) -> str:
    existing = str(request.cookies.get(CHANNEL_CHAT_SESSION_COOKIE_NAME) or "").strip()
    if existing and 12 <= len(existing) <= 200:
        return existing
    session_id = secrets.token_urlsafe(24)
    set_channel_chat_session_cookie(
        response,
        session_id,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=_channel_session_limits()["session_cookie_max_age_sec"],
    )
    return session_id


async def _apply_channel_session_pacing(
    *,
    tenant_id: int,
    credential_id: int,
    session_id: str,
) -> tuple[bool, int, int]:
    limits = _channel_session_limits()
    min_interval_ms = int(limits["session_min_interval_ms"])
    wait_max_ms = int(limits["session_wait_max_ms"])
    now_ms = int(datetime.now().timestamp() * 1000)
    wait_applied_ms = 0
    pace_key = f"quota:channel:pace:{tenant_id}:{credential_id}:{session_id}"

    def _retry_after(delta_ms: int) -> int:
        remaining = max(1, min_interval_ms - max(0, delta_ms))
        return max(1, int((remaining + 999) // 1000))

    redis_client = get_rate_limit_redis()
    if redis_client is not None:
        try:
            prev_raw = redis_client.get(pace_key)
            prev_ms = int(prev_raw) if prev_raw is not None else 0
            if prev_ms > 0:
                delta = now_ms - prev_ms
                if delta < min_interval_ms:
                    wait_applied_ms = min(wait_max_ms, max(0, min_interval_ms - delta))
                    if wait_applied_ms > 0:
                        await asyncio.sleep(wait_applied_ms / 1000.0)
                    now_ms = int(datetime.now().timestamp() * 1000)
                    delta = now_ms - prev_ms
                    if delta < min_interval_ms:
                        return False, _retry_after(delta), wait_applied_ms
            redis_client.set(pace_key, str(now_ms), ex=max(5, int((min_interval_ms * 4) / 1000)))
            return True, 0, wait_applied_ms
        except Exception:
            pass

    with _channel_session_lock:
        prev_ms = int(_channel_session_last_seen_ms.get(pace_key, 0))
    if prev_ms > 0:
        delta = now_ms - prev_ms
        if delta < min_interval_ms:
            wait_applied_ms = min(wait_max_ms, max(0, min_interval_ms - delta))
            if wait_applied_ms > 0:
                await asyncio.sleep(wait_applied_ms / 1000.0)
            now_ms = int(datetime.now().timestamp() * 1000)
            delta = now_ms - prev_ms
            if delta < min_interval_ms:
                return False, _retry_after(delta), wait_applied_ms
    with _channel_session_lock:
        _channel_session_last_seen_ms[pace_key] = now_ms
    return True, 0, wait_applied_ms


@router.post("/channel/credentials")
@limiter.limit("20/minute")
async def create_channel_credential(
    request: Request,
    payload: ChannelCredentialCreateRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    limits = _tenant_chat_limits(tenant)
    if int(payload.daily_limit) > int(limits["channel_daily_limit_cap"]):
        raise HTTPException(status_code=400, detail="A napi limit túl magas ehhez a csomaghoz.")
    if int(payload.per_minute_limit) > int(limits["channel_per_minute_limit_cap"]):
        raise HTTPException(status_code=400, detail="A per-minute limit túl magas ehhez a csomaghoz.")
    try:
        created = channel_svc.create_credential(
            tenant_id=tenant_id,
            channel_type=str(payload.channel_type or "widget").strip().lower(),
            name=payload.name,
            allowed_kb_uuids=payload.allowed_kb_uuids,
            daily_limit=payload.daily_limit,
            per_minute_limit=payload.per_minute_limit,
            allowed_origins=payload.allowed_origins,
            expires_at=_parse_iso_datetime(payload.expires_at),
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    warning = None
    if str(payload.channel_type or "").strip().lower() == "api" and not list(payload.allowed_origins or []):
        warning = "API credential allowed_origins nélkül létrehozva. Javasolt origin scope használata."
    return {"item": created, "warning": warning}


@router.get("/channel/credentials")
@limiter.limit("60/minute")
async def list_channel_credentials(
    request: Request,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"items": channel_svc.list_credentials(tenant_id=tenant_id)}


@router.post("/channel/credentials/{credential_id}/rotate")
@limiter.limit("20/minute")
async def rotate_channel_credential(
    request: Request,
    credential_id: int,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    rotated = channel_svc.rotate_credential(
        tenant_id=tenant_id,
        credential_id=credential_id,
        rotated_by=current_user.id,
    )
    if rotated is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"item": rotated}


@router.post("/channel/credentials/{credential_id}/revoke")
@limiter.limit("20/minute")
async def revoke_channel_credential(
    request: Request,
    credential_id: int,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    if not channel_svc.revoke_credential(tenant_id=tenant_id, credential_id=credential_id, revoked_by=current_user.id):
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"status": "ok"}


@router.put("/channel/credentials/{credential_id}/policy")
@limiter.limit("30/minute")
async def update_channel_credential_policy(
    request: Request,
    credential_id: int,
    payload: ChannelCredentialPolicyUpdateRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    limits = _tenant_chat_limits(tenant)
    if payload.daily_limit is not None and int(payload.daily_limit) > int(limits["channel_daily_limit_cap"]):
        raise HTTPException(status_code=400, detail="A napi limit túl magas ehhez a csomaghoz.")
    if payload.per_minute_limit is not None and int(payload.per_minute_limit) > int(limits["channel_per_minute_limit_cap"]):
        raise HTTPException(status_code=400, detail="A per-minute limit túl magas ehhez a csomaghoz.")
    try:
        updated = channel_svc.update_policy(
            tenant_id=tenant_id,
            credential_id=credential_id,
            allowed_kb_uuids=payload.allowed_kb_uuids,
            daily_limit=payload.daily_limit,
            per_minute_limit=payload.per_minute_limit,
            allowed_origins=payload.allowed_origins,
            updated_by=current_user.id,
            expires_at=_parse_iso_datetime(payload.expires_at),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"item": updated}


@router.get("/channel/credentials/{credential_id}/instructions")
@limiter.limit("60/minute")
async def channel_credential_instructions(
    request: Request,
    credential_id: int,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    items = channel_svc.list_credentials(tenant_id=tenant_id)
    item = next((row for row in items if int(row.get("id") or 0) == credential_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    endpoint = f"{request.base_url}api/channel/chat".replace("//api", "/api")
    embed_snippet = (
        "<script src=\"https://cdn.aiplaza/widget.js\" "
        f"data-endpoint=\"{endpoint}\" data-key=\"<GENERATED_SECRET>\" "
        f"data-tenant=\"{getattr(tenant, 'slug', '') or ''}\"></script>"
    )
    return {
        "credential_id": credential_id,
        "channel_type": item.get("channel_type"),
        "endpoint": endpoint,
        "widget_embed_snippet": embed_snippet,
        "api_example": {
            "curl": (
                f"curl -X POST '{endpoint}' "
                "-H 'Authorization: Bearer <GENERATED_SECRET>' "
                "-H 'Content-Type: application/json' "
                f"-d '{json.dumps({'question': 'Mit tud a tudástár?', 'kb_uuid': None})}'"
            )
        },
    }


@router.post(
    "/channel/chat",
    response_model=AskResponse,
    response_model_exclude_none=True,
)
@limiter.limit("120/minute")
async def channel_chat(
    request: Request,
    req: ChannelAskRequest,
    tenant: RequiredTenantContextDep,
    response: MutableResponse,
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    limits = _tenant_chat_limits(tenant)
    _normalize_chat_payload(req, limits=limits)
    _validate_chat_payload_or_413(req, limits=limits)
    effective_debug = False
    secret = _extract_channel_secret(request)
    principal = channel_svc.authenticate(
        tenant_id=tenant_id,
        secret=secret,
        origin=request.headers.get("Origin"),
    )
    if principal is None:
        increment_metric("channel.chat.rejected.auth", 1.0)
        raise HTTPException(status_code=401, detail="Invalid channel credential")
    kb_uuid = req.kb_uuid
    allowed_kbs = [value for value in principal.allowed_kb_uuids if value]
    if allowed_kbs:
        if kb_uuid and kb_uuid not in allowed_kbs:
            raise HTTPException(status_code=403, detail="A credential nem fér hozzá ehhez a tudástárhoz.")
        if not kb_uuid:
            kb_uuid = allowed_kbs[0]
    session_id = _resolve_or_set_channel_session_id(request, response)
    pace_allowed, retry_after_sec, wait_applied_ms = await _apply_channel_session_pacing(
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
    session_limits = _channel_session_limits()
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
            remote_ip=(request.client.host if request.client else None),
            response_ms=0,
            llm_ms=0,
            context_build_ms=0,
            total_ms=0,
        )
        detail = reason or "Túl sok kérés rövid idő alatt."
        status_code = 503 if "nem elérhető" in str(detail).lower() else 429
        raise HTTPException(status_code=status_code, detail=detail)
    budget_reservation = None
    if hasattr(svc, "acquire_llm_budget"):
        prompt_chars = svc.estimate_prompt_chars(
            question=req.question,
            conversation_history=req.conversation_history,
            retrieval_history=req.retrieval_history,
        )
        budget_allowed, budget_reason, budget_reservation = _normalize_budget_result(svc.acquire_llm_budget(
            tenant_id=tenant_id,
            scope=f"channel:{principal.credential_id}:{str(limits.get('budget_scope') or 'default')}",
            prompt_chars=prompt_chars,
        ))
        if not budget_allowed:
            increment_metric("llm.budget_reject_total", 1.0, tags={"channel": principal.channel_type})
            channel_svc.release_question_slot(quota_reservation)
            quota_reservation = None
            detail = budget_reason or "Túl sok kérés rövid idő alatt."
            status_code = 503 if "nem elérhető" in str(detail).lower() else 429
            raise HTTPException(status_code=status_code, detail=detail)
    try:
        payload = await svc.chat_with_sources(
            req.question,
            user_id=None,
            user_role="channel",
            kb_uuid=kb_uuid,
            debug=effective_debug,
            conversation_history=req.conversation_history,
            retrieval_history=req.retrieval_history,
        )
    except ChatPolicyViolationError as exc:
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PiiDepersonalizationUnavailableError as exc:
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
        raise
    finally:
        if hasattr(svc, "release_llm_budget"):
            svc.release_llm_budget(budget_reservation)
    usage_status = "ok" if str(payload.get("answer") or "").strip() else "empty_answer"
    if usage_status != "ok":
        channel_svc.release_question_slot(quota_reservation)
        quota_reservation = None
    timing = (
        ((payload.get("prompt_context") or {}).get("index_debug") or {}).get("timing_ms")
        if isinstance(payload, dict)
        else {}
    )
    channel_svc.record_usage(
        tenant_id=tenant_id,
        credential_id=principal.credential_id,
        channel_type=principal.channel_type,
        status=usage_status,
        question=req.question,
        kb_uuid=kb_uuid,
        query_run_id=payload.get("query_run_id"),
        origin=request.headers.get("Origin"),
        remote_ip=(request.client.host if request.client else None),
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
    response_kwargs = {
        "answer": str(payload.get("answer") or ""),
        "query_run_id": payload.get("query_run_id") or None,
        "sources": (payload.get("sources") or [])[: int(limits["max_sources"])],
        "answer_mode": str(payload.get("answer_mode") or "no_answer"),
        "answer_source": str(payload.get("answer_source") or "none"),
        "confidence": float(payload.get("confidence") or 0.0),
        "encoded_prompt_context": str(payload.get("encoded_prompt_context") or "") if effective_debug else "",
        "restored_pii_spans": payload.get("restored_pii_spans") or [],
    }
    if effective_debug:
        response_kwargs.update(
            {
                "prompt_context": payload.get("prompt_context") or {},
                "debug": payload.get("debug"),
                "evidence": payload.get("evidence") or [],
                "cited_claim_ids": payload.get("cited_claim_ids") or [],
                "cited_sentence_ids": payload.get("cited_sentence_ids") or [],
                "cited_source_ids": payload.get("cited_source_ids") or [],
                "query_profile": payload.get("query_profile") or {},
                "matched_chunks": payload.get("matched_chunks") or [],
                "claims": payload.get("claims") or [],
                "context_blocks": payload.get("context_blocks") or [],
            }
        )
    return AskResponse(**response_kwargs)


@router.post("/channel/feedback")
@limiter.limit("180/minute")
async def channel_feedback_capture(
    request: Request,
    payload: ChannelFeedbackCaptureRequest,
    tenant: RequiredTenantContextDep,
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    secret = _extract_channel_secret(request)
    principal = channel_svc.authenticate(
        tenant_id=tenant_id,
        secret=secret,
        origin=request.headers.get("Origin"),
    )
    if principal is None:
        increment_metric("channel.feedback.rejected.auth", 1.0)
        raise HTTPException(status_code=401, detail="Invalid channel credential")
    result = channel_svc.record_feedback(
        tenant_id=tenant_id,
        credential_id=principal.credential_id,
        channel_type=principal.channel_type,
        query_run_id=payload.query_run_id,
        trace_id=payload.trace_id,
        helpful=payload.helpful,
        reason=payload.reason,
        note=payload.note,
    )
    increment_metric("channel.feedback.count", 1.0)
    return {"item": result}


@router.post("/channel/feedback/{feedback_id}/triage")
@limiter.limit("60/minute")
async def channel_feedback_triage(
    request: Request,
    feedback_id: int,
    payload: ChannelFeedbackTriageRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    updated = channel_svc.triage_feedback(
        tenant_id=tenant_id,
        feedback_id=feedback_id,
        triage_status=payload.triage_status,
        triage_owner=payload.triage_owner,
        triage_note=payload.triage_note,
        triaged_by=current_user.id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"item": updated}


@router.get("/channel/analytics/summary")
@limiter.limit("120/minute")
async def channel_analytics_summary(
    request: Request,
    tenant: RequiredTenantContextDep,
    days: int = 14,
    current_user: User = Depends(require_permission("chat.channel.analytics")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"summary": channel_svc.analytics_summary(tenant_id=tenant_id, days=days)}


@router.get("/channel/analytics/events")
@limiter.limit("120/minute")
async def channel_analytics_events(
    request: Request,
    tenant: RequiredTenantContextDep,
    limit: int = 100,
    current_user: User = Depends(require_permission("chat.channel.analytics")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"items": channel_svc.analytics_events(tenant_id=tenant_id, limit=limit)}


@router.get("/channel/analytics/feedback")
@limiter.limit("120/minute")
async def channel_analytics_feedback(
    request: Request,
    tenant: RequiredTenantContextDep,
    limit: int = 100,
    current_user: User = Depends(require_permission("chat.channel.analytics")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"items": channel_svc.analytics_feedback(tenant_id=tenant_id, limit=limit)}


@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket):
    """
    WebSocket chat: token HttpOnly cookie (ws_token). Query param NINCS (biztonság: ne kerüljön logokba).
    Opcionálisan tenant=yyy query. Üzenet: {"question": "..."}; válasz: {"chunk": "..."}, majd {"done": true}.
    """
    token = websocket.cookies.get("ws_token")
    if not _ws_enabled():
        await websocket.close(code=4403)
        return
    tenant_slug = websocket.query_params.get("tenant") or None
    if not tenant_slug:
        tenant_slug = str(getattr(settings, "single_tenant_slug", "") or "").strip() or None
    user = await validate_ws_token(token, tenant_slug)
    if not user or not getattr(user, "is_active", True):
        await websocket.close(code=4401)
        return
    remote_ip = websocket.client.host if websocket.client else None
    tenant_repo = get_tenant_repository()
    tenant = tenant_repo.get_by_slug(tenant_slug) if tenant_slug else None
    if tenant is None:
        await websocket.close(code=4404)
        return
    acquired, acquire_reason, conn_reservation = _ws_try_acquire_connection(
        tenant_slug=tenant_slug,
        user_id=getattr(user, "id", None),
    )
    if not acquired:
        increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "conn_limit"})
        await websocket.close(code=4429, reason=acquire_reason[:120] if acquire_reason else "")
        return
    await websocket.accept()
    svc = get_chat_service()
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    limits = _tenant_chat_limits(tenant)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=_ws_idle_timeout_sec())
            except asyncio.TimeoutError:
                await websocket.send_json({"error": "Idle timeout"})
                await websocket.close(code=4408)
                return
            if len(data or "") > _ws_max_message_chars():
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "payload_too_large"})
                await websocket.send_json({"error": "Message too large"})
                continue
            if not _ws_allow_message(tenant_slug=tenant_slug, user_id=getattr(user, "id", None), remote_ip=remote_ip):
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "rate_limit"})
                await websocket.send_json({"error": "Too many websocket messages"})
                continue
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "invalid_json"})
                await websocket.send_json({"error": "Invalid JSON"})
                continue
            question = msg.get("question") if isinstance(msg, dict) else None
            kb_uuid = str(msg.get("kb_uuid") or "").strip() if isinstance(msg, dict) else ""
            if not question or not isinstance(question, str):
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "missing_question"})
                await websocket.send_json({"error": "Missing or invalid question"})
                continue
            question = question.strip()
            if not question:
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "empty_question"})
                await websocket.send_json({"error": "Empty question"})
                continue
            if len(question) > _ws_max_message_chars() or len(question) > int(limits["max_question_chars"]):
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "question_too_large"})
                await websocket.send_json({"error": "Question too large"})
                continue
            allowed, reason = usage_service.can_consume_question(tenant)
            if not allowed:
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "tenant_quota"})
                await websocket.send_json({"error": reason or "Quota exceeded"})
                continue
            budget_reservation = None
            if hasattr(svc, "acquire_llm_budget"):
                prompt_chars = svc.estimate_prompt_chars(
                    question=question,
                    conversation_history=[],
                    retrieval_history=[],
                )
                budget_allowed, budget_reason, budget_reservation = _normalize_budget_result(svc.acquire_llm_budget(
                    tenant_id=int(getattr(tenant, "tenant_id", 0) or 0),
                    scope=f"ws_chat:{str(limits.get('budget_scope') or 'default')}",
                    prompt_chars=prompt_chars,
                ))
                if not budget_allowed:
                    increment_metric("llm.budget_reject_total", 1.0, tags={"channel": "ws_chat"})
                    detail = budget_reason or "LLM budget exceeded"
                    await websocket.send_json({"error": detail})
                    if "nem elérhető" in str(detail).lower():
                        await websocket.close(code=1013, reason="LLM budget service unavailable")
                        return
                    continue
            try:
                async for chunk in svc.chat_stream(
                    question,
                    user_id=user.id,
                    user_role=user.role,
                    kb_uuid=kb_uuid or None,
                ):
                    await websocket.send_json({"chunk": chunk})
            except PiiDepersonalizationUnavailableError as exc:
                await websocket.send_json({"error": str(exc)})
                await websocket.close(code=1013, reason="PII depersonalization unavailable")
                return
            except TypeError:
                async for chunk in svc.chat_stream(question):
                    await websocket.send_json({"chunk": chunk})
            finally:
                if hasattr(svc, "release_llm_budget"):
                    svc.release_llm_budget(budget_reservation)
            usage_service.record_question(tenant, user.id)
            await websocket.send_json({"done": True})
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        _ws_release_connection(conn_reservation)
