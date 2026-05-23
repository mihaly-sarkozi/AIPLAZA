# backend/core/kernel/http/app_errors.py
# Feladat: Alkalmazasszintu, biztonsagosan HTTP valaszra mapelheto hibak kozos
# contractja. Modulok AppError alosztalyokat dobhatnak, az ErrorMapper pedig
# egyseges {code, message, request_id, details?} valaszt keszit beloluk.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.kernel.http.error_payloads import build_error_payload


class AppError(Exception):
    code: str = "APP_ERROR"
    status_code: int = 500
    safe_message: str = "Unexpected error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        self.code = str(code or self.code)
        self.status_code = int(status_code or self.status_code)
        self.safe_message = str(message or self.safe_message)
        self.safe_details = dict(safe_details or {})
        super().__init__(self.safe_message)


class TenantAccessDenied(AppError):
    code = "TENANT_ACCESS_DENIED"
    status_code = 403
    safe_message = "You are not allowed to access this tenant."


class KnowledgeBaseNotFound(AppError):
    code = "KNOWLEDGE_BASE_NOT_FOUND"
    status_code = 404
    safe_message = "Knowledge base not found."


@dataclass(frozen=True)
class ErrorResponse:
    status_code: int
    payload: dict[str, Any] = field(default_factory=dict)


class ErrorMapper:
    def to_response_payload(self, error: AppError, *, request_id: str | None, include_legacy_detail: bool = False) -> ErrorResponse:
        detail = dict(error.safe_details) if error.safe_details else None
        payload = build_error_payload(
            status_code=error.status_code,
            request_id=request_id,
            detail=detail,
            code=error.code,
            message=error.safe_message,
            include_legacy_detail=include_legacy_detail,
        )
        return ErrorResponse(status_code=error.status_code, payload=payload)


__all__ = [
    "AppError",
    "ErrorMapper",
    "ErrorResponse",
    "KnowledgeBaseNotFound",
    "TenantAccessDenied",
]
