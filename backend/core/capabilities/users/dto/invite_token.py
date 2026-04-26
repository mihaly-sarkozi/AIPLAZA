# Regisztráció esetén emailben küldött meghívó token DTO.
# 2026.03.26 - Sárközi Mihály

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
