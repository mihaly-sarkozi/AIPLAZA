# Profil módosítás request model.
# 2026.04.03 - Sárközi Mihály

from pydantic import BaseModel, Field


class UpdateMeRequest(BaseModel):
    name: str | None = Field(None, max_length=100, description="Felhasználó neve")
    preferred_locale: str | None = None
    preferred_theme: str | None = None
