# apps/users/adapter/http/request/user_update_req.py
# Adapter (HTTP): user módosítás PUT body. Admin/owner: név, aktív, email, szerepkör (user/admin). Owner célpont: csak név.
# 2026.03.07 - Sárközi Mihály

from typing import Optional
from pydantic import BaseModel, Field


class UserUpdateReq(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Felhasználó neve")
    is_active: Optional[bool] = Field(None, description="Aktív státusz")
    email: Optional[str] = Field(None, max_length=100, description="Email (csak admin/owner módosíthatja; user/admin célpontnál)")
    role: Optional[str] = Field(None, description="Szerepkör: user | admin (csak admin/owner módosíthatja)")
