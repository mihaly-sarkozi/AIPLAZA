# backend/core/modules/brand/web/responses/brand_response.py
# Feladat: Brand beállításokat visszaadó Pydantic response modellt definiál. A display név, logo URL, primary color, support email és public_enabled mezők egységes HTTP kimenetét adja. Brand web response schema.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pydantic import BaseModel


class BrandResponse(BaseModel):
    display_name: str
    logo_url: str
    primary_color: str
    support_email: str
    public_enabled: bool = True
