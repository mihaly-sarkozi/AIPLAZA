from __future__ import annotations

import json
from typing import Any

from lang.messages import get_message

from core.kernel.config.config_loader import get_app_env
from core.kernel.config.environment import is_production_env

_STACK_KEYS = {"stack", "trace", "traceback", "exception_trace", "exception_stack"}
_SECURITY_HINT_KEYWORDS = (
    "signature",
    "nonce",
    "body hash",
    "ip allowlist",
    "credential",
)


def _request_id_from_state(state: Any) -> str | None:
    if state is None:
        return None
    return str(getattr(state, "request_id", "") or getattr(state, "correlation_id", "") or "").strip() or None


def request_id_from_request(request: Any) -> str | None:
    return _request_id_from_state(getattr(request, "state", None))


def request_id_from_scope(scope: dict[str, Any]) -> str | None:
    state = (scope or {}).get("state")
    if isinstance(state, dict):
        return str(state.get("request_id") or state.get("correlation_id") or "").strip() or None
    return _request_id_from_state(state)


def is_production_runtime() -> bool:
    try:
        return is_production_env(get_app_env())
    except Exception:
        return False


def _default_code(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(int(status_code), "REQUEST_ERROR")


def _default_message(status_code: int) -> str:
    mapping = {
        400: "The request is invalid.",
        401: "Authentication failed.",
        403: "Access denied.",
        404: "Resource not found.",
        409: "Request conflict.",
        413: "Payload too large.",
        415: "Unsupported media type.",
        422: "Validation failed.",
        429: "Too many requests. Please try again later.",
        500: "Internal server error.",
        503: "Service unavailable.",
    }
    return mapping.get(int(status_code), "Request failed.")


def _sanitize_details(details: Any) -> Any:
    if isinstance(details, dict):
        sanitized: dict[str, Any] = {}
        for key, value in details.items():
            if str(key).strip().lower() in _STACK_KEYS:
                continue
            sanitized[key] = _sanitize_details(value)
        return sanitized
    if isinstance(details, list):
        return [_sanitize_details(value) for value in details]
    return details


def _looks_sensitive_security_detail(status_code: int, detail: Any) -> bool:
    if int(status_code) not in {401, 403}:
        return False
    if not isinstance(detail, str):
        return False
    text = str(detail or "").lower()
    return any(keyword in text for keyword in _SECURITY_HINT_KEYWORDS)


def build_error_payload(
    *,
    status_code: int,
    request_id: str | None,
    detail: Any = None,
    code: str | None = None,
    message: str | None = None,
    lang: str | None = None,
    include_legacy_detail: bool = True,
) -> dict[str, Any]:
    production = is_production_runtime()
    status_code = int(status_code)
    effective_code = str(code or "")
    effective_message = str(message or "")
    sanitized_detail = _sanitize_details(detail)

    if isinstance(sanitized_detail, dict):
        if not effective_code:
            effective_code = str(sanitized_detail.get("code") or "")
        if not effective_message:
            effective_message = str(sanitized_detail.get("message") or "")
    if effective_code and not effective_message:
        effective_message = get_message(effective_code, lang)
    if not effective_code:
        effective_code = _default_code(status_code)
    if not effective_message:
        if isinstance(sanitized_detail, str) and sanitized_detail.strip():
            effective_message = sanitized_detail.strip()
        else:
            effective_message = _default_message(status_code)

    expose_details = True
    if status_code >= 500 and production:
        expose_details = False
    if _looks_sensitive_security_detail(status_code, sanitized_detail):
        effective_message = _default_message(status_code)
        expose_details = False

    payload: dict[str, Any] = {
        "code": effective_code,
        "message": effective_message,
        "request_id": request_id,
    }

    if expose_details and sanitized_detail not in (None, "", {}, []):
        payload["details"] = sanitized_detail

    if include_legacy_detail:
        if not expose_details:
            payload["detail"] = effective_message
        elif isinstance(sanitized_detail, dict) and sanitized_detail or isinstance(sanitized_detail, list):
            payload["detail"] = sanitized_detail
        elif isinstance(sanitized_detail, str) and sanitized_detail.strip():
            payload["detail"] = sanitized_detail.strip()
        else:
            payload["detail"] = effective_message

    return payload


def build_security_error_detail(
    *,
    code: str = "PERMISSION_DENIED",
    message: str = "You are not allowed to access this resource.",
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "_security_error": True,
    }


def build_error_body_bytes_for_scope(
    *,
    scope: dict[str, Any],
    status_code: int,
    detail: Any = None,
    code: str | None = None,
    message: str | None = None,
) -> bytes:
    payload = build_error_payload(
        status_code=status_code,
        request_id=request_id_from_scope(scope),
        detail=detail,
        code=code,
        message=message,
    )
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


__all__ = [
    "build_error_body_bytes_for_scope",
    "build_error_payload",
    "build_security_error_detail",
    "request_id_from_request",
    "request_id_from_scope",
]
