# backend/core/modules/users/router/responses/user_response.py
# Feladat: A users HTTP API UserResponse Pydantic modellje. A publikus user mezőket, profil adatokat és security/version mezőket formázza route válaszokhoz. Users web response contract.
# Sárközi Mihály - 2026.05.21

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None = None
    role: str
    is_active: bool | None = None
    created_at: datetime | None = None
    pending_registration: bool = False
