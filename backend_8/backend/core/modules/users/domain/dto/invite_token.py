# backend/core/modules/users/domain/dto/invite_token.py
# Feladat: A user invite token domain DTO-t definiálja. Meghívó token állapotot, lejáratot, tenant/user kapcsolatot és audit adatokat hordoz az InviteService és repository között. Users invite adatcontract.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class InviteToken:
    id: int # Bejegyzés Azonosító
    user_id: int # User azonosító
    expires_at: datetime # Token lejárat dátuma
    used_at: datetime | None # Token felhasználás dátuma
    created_at: datetime | None = None # Készítés dátum és idő
    created_by: int | None = None # User azonosító
    updated_at: datetime | None = None # Frissítés dátum és idő
    updated_by: int | None = None # User azonosító
