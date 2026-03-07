# apps/users/adapter/http/response/user_out.py
# Adapter (HTTP): user részletes kimenet (pl. user list, GET user).
# 2026.03.07 - Sárközi Mihály

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: Optional[str] = None
    role: str  # user | admin | owner
    is_active: bool
    created_at: datetime
    # True = még nem regisztrált (linket kapott, megerősítésre vár); False = már regisztrált vagy aktív
    pending_registration: bool = False
