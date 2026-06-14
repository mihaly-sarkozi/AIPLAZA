from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from apps.kb.kb_search.enums.SearchErrorCode import SearchErrorCode
from apps.kb.kb_search.errors.SearchNotReadyError import SearchNotReadyError
from apps.kb.kb_search.errors.SearchQdrantFailedError import SearchQdrantFailedError


def raise_if_blocked_search_result(result: dict[str, Any]) -> None:
    answer_mode = str(result.get("answer_mode") or "").strip().upper()
    if answer_mode != "BLOCKED_NOT_READY":
        return
    readiness = dict(result.get("readiness") or {})
    raise HTTPException(
        status_code=423,
        detail={
            "code": SearchErrorCode.KB_NOT_READY.value,
            "message": str(result.get("error_message") or "A kiválasztott tudástár még nem kereshető."),
            "blocked_reasons": list(readiness.get("blocking_issues") or readiness.get("blocked_reasons") or []),
            "readiness": readiness,
            "query_run_id": result.get("query_run_id"),
        },
    )


def map_search_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, SearchNotReadyError):
        return HTTPException(
            status_code=423,
            detail={
                "code": SearchErrorCode.KB_NOT_READY.value,
                "message": exc.message,
                "blocked_reasons": list(exc.blocked_reasons),
            },
        )
    if isinstance(exc, PermissionError):
        return HTTPException(
            status_code=403,
            detail={
                "code": SearchErrorCode.PERMISSION_DENIED.value,
                "message": str(exc),
            },
        )
    if isinstance(exc, SearchQdrantFailedError):
        return HTTPException(
            status_code=503,
            detail={
                "code": SearchErrorCode.QDRANT_FAILED.value,
                "message": exc.message,
            },
        )
    message = str(exc)
    if SearchErrorCode.QDRANT_FAILED.value in message:
        return HTTPException(
            status_code=503,
            detail={"code": SearchErrorCode.QDRANT_FAILED.value, "message": message},
        )
    if SearchErrorCode.PERMISSION_DENIED.value in message:
        return HTTPException(
            status_code=403,
            detail={"code": SearchErrorCode.PERMISSION_DENIED.value, "message": message},
        )
    if SearchErrorCode.KB_NOT_READY.value in message:
        return HTTPException(
            status_code=423,
            detail={"code": SearchErrorCode.KB_NOT_READY.value, "message": message},
        )
    return HTTPException(status_code=500, detail={"code": "SEARCH_INTERNAL_ERROR", "message": message})


__all__ = ["map_search_exception", "raise_if_blocked_search_result"]
