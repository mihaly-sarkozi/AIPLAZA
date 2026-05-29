# backend/core/modules/users/service/_user_service_helpers.py
# Feladat: Users service helper függvényeket tartalmaz. Meghívó/initial password token payloadot és set-password linket épít, hogy a UserService és InviteService közös token URL logikát használjon. Users service shared helper réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.kernel.config.config_loader import settings
from core.kernel.runtime.clock import utc_now

# Meghívó token lejárati idő
def invite_ttl_hours() -> int:
    return max(1, min(24, getattr(settings, "invite_ttl_hours", 4)))

# Jelszó beállító link készítése
def build_set_password_link(request_base_url: str | None, token: str) -> str:
    base = (request_base_url or "").strip().rstrip("/")
    path = (settings.frontend_set_password_path or "/set-password").strip()
    if path and not path.startswith("/"):
        path = "/" + path
    if not base:
        return ""
    return f"{base}{path}?token={token}"


def build_confirm_email_link(request_base_url: str | None, token: str) -> str:
    base = (request_base_url or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/confirm-email?token={token}"

# Meghívó token adatstruktúra
@dataclass(frozen=True)
class InviteTokenPayload:
    raw_token: str
    token_hash: str
    expires_at: datetime

# Meghívó token adatstruktúra létrehozása
def new_invite_token_payload() -> InviteTokenPayload:
    raw_token = secrets.token_urlsafe(32)
    return InviteTokenPayload(
        raw_token=raw_token,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=utc_now() + timedelta(hours=invite_ttl_hours()),
    )
