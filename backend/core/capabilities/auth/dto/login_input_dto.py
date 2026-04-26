# Login bemenetből egy DTO osztályt készít
# 2026.02.28 - Sárközi Mihály

from dataclasses import dataclass
from typing import Optional

from core.capabilities.auth.dto.tenant_auth_context import TenantAuthContext


@dataclass(frozen=True)
class LoginInput:
    email: Optional[str] # Email cím
    password: Optional[str] # Jelszó
    pending_token: Optional[str] # Pending token, amit kiküldünk a usernek 2FA kód küldésére
    two_factor_code: Optional[str] # 2FA kód, amit a user beír a 2. lépésben
    ip: Optional[str] # IP cím
    ua: Optional[str] # User agent, amit a user küld a belépéskor
    auto_login: bool = False # Automatikus belépés, ha true akkor 30 napig érvényes a belépés
    tenant: TenantAuthContext | None = None
