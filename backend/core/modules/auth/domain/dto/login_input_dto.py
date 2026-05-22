# backend/core/modules/auth/domain/dto/login_input_dto.py
# Feladat: A login use case bemeneti DTO-ját definiálja. Egy objektumban hordozza az első lépéshez szükséges email/jelszó adatokat, a második 2FA lépés pending token/kód adatait, request kontextust és tenant auth contextet. Auth domain DTO, amelyet a router alakít ki és a LoginService dolgoz fel.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass
from typing import Optional

from core.modules.auth.domain.dto.tenant_auth_context import TenantAuthContext


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
