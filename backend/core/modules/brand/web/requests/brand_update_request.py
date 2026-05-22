# backend/core/modules/brand/web/requests/brand_update_request.py
# Feladat: Brand beállítások frissítéséhez használt Pydantic request modellt definiál. Display név, logo URL, primary color, support email és public_enabled mezőket fogad a PATCH /platform/brand endpointtól. Brand web request schema.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pydantic import BaseModel


class BrandUpdateRequest(BaseModel):
    display_name: str = ""
    logo_url: str = ""
    primary_color: str = "#2563eb"
    support_email: str = ""
    public_enabled: bool = True
