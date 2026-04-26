# Felhasználó response model
# 2026.04.03 - Sárközi Mihály

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
