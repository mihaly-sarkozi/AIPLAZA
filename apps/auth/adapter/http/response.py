# apps/auth/adapter/http/response.py
from pydantic import BaseModel
from datetime import datetime

class UserInfo(BaseModel):
    id: int
    email: str
    role: str
    is_superuser: bool = False

class UserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResp(BaseModel):
    access_token: str
    user: UserInfo