# backend/apps/chat/application/channel_request_policy.py
# Channel HTTP request and credential policy helpers.

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Request


def channel_access_service_or_503(svc):
    channel_svc = getattr(svc, "channel_access_service", None)
    if channel_svc is None:
        raise HTTPException(status_code=503, detail="Channel access service not available")
    return channel_svc


def parse_iso_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid expires_at format") from exc


def extract_channel_secret(request: Request) -> str:
    auth = str(request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    api_key = str(request.headers.get("X-API-Key") or "").strip()
    if api_key:
        return api_key
    raise HTTPException(status_code=401, detail="Missing channel credential")


def tenant_required_id(tenant) -> int:
    tenant_id = int(getattr(tenant, "tenant_id", 0) or 0)
    if tenant_id <= 0:
        raise HTTPException(status_code=400, detail="Tenant context missing")
    return tenant_id


__all__ = [
    "channel_access_service_or_503",
    "extract_channel_secret",
    "parse_iso_datetime",
    "tenant_required_id",
]
