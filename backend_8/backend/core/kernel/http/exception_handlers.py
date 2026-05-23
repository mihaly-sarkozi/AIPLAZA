# backend/core/kernel/http/exception_handlers.py
# Feladat: Globális FastAPI exception handlereket regisztrál. Egységes JSON választ ad rate limit, HTTP és váratlan hibákra, közben metricet és strukturált logot ír observability célra. Core HTTP hibakezelési adapter, amelyet az app_factory köt be.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from core.kernel.http.app_errors import AppError, ErrorMapper
from core.kernel.http.error_payloads import build_error_payload, request_id_from_request
from core.kernel.logging.observability import increment_metric, log_exception_event, log_structured_event
from lang.messages import get_message, lang_from_request


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        if exc.status_code >= 500:
            log_exception_event(
                "core.http",
                "request.app_error",
                exc,
                path=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                error_code=exc.code,
                tenant_slug=getattr(request.state, "tenant_slug", None),
                tenant_id=getattr(request.state, "tenant_id", None),
                user_id=getattr(getattr(request.state, "user", None), "id", None),
            )
        mapped = ErrorMapper().to_response_payload(exc, request_id=request_id_from_request(request))
        return JSONResponse(status_code=mapped.status_code, content=mapped.payload)

    @app.exception_handler(RateLimitExceeded)
    def rate_limit_handler(request, exc):
        increment_metric("platform.rate_limit.hit.count", 1.0)
        increment_metric("rate_limit_rejections_total", 1.0)
        log_structured_event(
            "core.http",
            "request.rate_limited",
            level=logging.WARNING,
            path=str(getattr(request, "url", "")),
            method=getattr(request, "method", None),
            tenant_slug=getattr(getattr(request, "state", object()), "tenant_slug", None),
            tenant_id=getattr(getattr(request, "state", object()), "tenant_id", None),
            user_id=getattr(getattr(getattr(request, "state", object()), "user", None), "id", None),
        )
        return JSONResponse(
            status_code=429,
            content=build_error_payload(
                status_code=429,
                request_id=request_id_from_request(request),
                code="RATE_LIMITED",
                message="Too many requests. Please try again later.",
                detail="Túl sok kérés. Próbáld újra később.",
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code >= 500:
            log_exception_event(
                "core.http",
                "request.http_exception",
                exc,
                path=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                tenant_slug=getattr(request.state, "tenant_slug", None),
                tenant_id=getattr(request.state, "tenant_id", None),
                user_id=getattr(getattr(request.state, "user", None), "id", None),
            )
        if isinstance(exc.detail, dict) and exc.detail.get("_security_error"):
            lang = lang_from_request(request)
            content = dict(exc.detail)
            return JSONResponse(
                status_code=exc.status_code,
                content=build_error_payload(
                    status_code=exc.status_code,
                    request_id=request_id_from_request(request),
                    code=str(content.get("code") or "PERMISSION_DENIED"),
                    message=str(content.get("message") or "You are not allowed to access this resource."),
                    lang=lang,
                    include_legacy_detail=False,
                ),
            )
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            lang = lang_from_request(request)
            content = dict(exc.detail)
            if not str(content.get("message") or "").strip():
                content["message"] = get_message(content["code"], lang)
            return JSONResponse(
                status_code=exc.status_code,
                content=build_error_payload(
                    status_code=exc.status_code,
                    request_id=request_id_from_request(request),
                    detail=content,
                    code=str(content.get("code") or ""),
                    message=str(content.get("message") or ""),
                    lang=lang,
                ),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(
                status_code=exc.status_code,
                request_id=request_id_from_request(request),
                detail=exc.detail,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code >= 500:
            log_exception_event(
                "core.http",
                "request.starlette_http_exception",
                exc,
                path=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                tenant_slug=getattr(request.state, "tenant_slug", None),
                tenant_id=getattr(request.state, "tenant_id", None),
                user_id=getattr(getattr(request.state, "user", None), "id", None),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(
                status_code=exc.status_code,
                request_id=request_id_from_request(request),
                detail=exc.detail,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        increment_metric("platform.request.unhandled_error.count", 1.0)
        log_exception_event(
            "core.http",
            "request.unhandled_exception",
            exc,
            path=str(request.url.path),
            method=request.method,
            status_code=500,
            tenant_slug=getattr(request.state, "tenant_slug", None),
            tenant_id=getattr(request.state, "tenant_id", None),
            user_id=getattr(getattr(request.state, "user", None), "id", None),
        )
        return JSONResponse(
            status_code=500,
            content=build_error_payload(
                status_code=500,
                request_id=request_id_from_request(request),
                code="INTERNAL_ERROR",
                message="Internal server error.",
                detail="Internal server error",
            ),
        )


__all__ = ["register_exception_handlers"]
