# backend/core/modules/users/router/requests/update_me_request.py
# Feladat: Saját profil módosítás HTTP request DTO. Név, locale, theme és kapcsolódó profilmezők részleges frissítését hordozza. Users web request contract.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel, Field


class UpdateMeRequest(BaseModel):
    name: str | None = Field(None, max_length=100, description="Felhasználó neve")
    preferred_locale: str | None = None
    preferred_theme: str | None = None
