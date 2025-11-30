# apps/auth/adapter/http/request.py
from pydantic import BaseModel, Field
from typing import Optional

class LoginReq(BaseModel):
    email: str
    password: str

class UserCreateReq(BaseModel):
    email: str = Field(..., description="User email cím")
    password: str = Field(..., min_length=6, description="Jelszó (min. 6 karakter)")
    role: str = Field(default="user", description="User szerepkör: 'user' vagy 'admin'")
    is_superuser: bool = Field(default=False, description="Superuser státusz (csak admin role-lal)")

class UserUpdateReq(BaseModel):
    email: Optional[str] = Field(None, description="User email cím")
    role: Optional[str] = Field(None, description="User szerepkör: 'user' vagy 'admin'")
    is_active: Optional[bool] = Field(None, description="Aktív státusz")
