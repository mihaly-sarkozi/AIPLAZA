from __future__ import annotations

from pydantic import BaseModel


class BrandResponse(BaseModel):
    display_name: str
    logo_url: str
    primary_color: str
    support_email: str
    public_enabled: bool = True


class BrandUpdateRequest(BaseModel):
    display_name: str = ""
    logo_url: str = ""
    primary_color: str = "#2563eb"
    support_email: str = ""
    public_enabled: bool = True
