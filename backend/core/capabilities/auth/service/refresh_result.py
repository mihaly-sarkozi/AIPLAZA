"""RefreshService.refresh() visszatérési értékének típusdefiníciói.

A route handler NE ágazzon nyers tuple-on vagy None-on – ehelyett
kizárólag ezeket a típusokat vizsgálja.

Siker:   RefreshSuccess
Hiba:    RefreshFailed  (reason-nal)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.capabilities.users.dto.user import User


class RefreshFailReason(str, Enum):
    """A token-megújítás lehetséges sikertelenségi okai."""

    EXPIRED_TOKEN = "expired_token"
    INVALID_TOKEN = "invalid_token"
    WRONG_TOKEN_TYPE = "wrong_token_type"
    SECURITY_VERSION_MISMATCH = "security_version_mismatch"
    UNKNOWN_SESSION = "unknown_session"
    PERMISSIONS_CHANGED = "permissions_changed"
    SESSION_REUSE_DETECTED = "session_reuse_detected"
    SESSION_EXPIRED = "session_expired"
    RE_2FA_REQUIRED = "re_2fa_required"


@dataclass(frozen=True)
class RefreshFailed:
    """A token-megújítás sikertelen volt."""

    reason: RefreshFailReason


@dataclass(frozen=True)
class RefreshSuccess:
    """A token-megújítás sikeres volt."""

    access_token: str
    refresh_token: str
    access_jti: str
    user: "User | None"
    """A felhasználó domain objektum (opcionális gyorsítótárazáshoz)."""
    auto_login: bool = False
    """Az eredeti session auto_login (állandó) beállítása (refresh cookie max_age-hez)."""


RefreshResult = RefreshFailed | RefreshSuccess
"""Union típus: RefreshService.refresh() visszatérési értéke."""
