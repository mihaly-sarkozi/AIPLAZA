from __future__ import annotations

# backend/apps/settings/api/SettingsUpdateRequest.py
# Feladat: Legacy kompatibilitási export a settings API request sémákhoz (új hely: api/schemas.py).
# Sárközi Mihály - 2026.05.24

from apps.settings.api.schemas import (
    BillingSettingsUpdateRequest,
    LocaleSettingsUpdateRequest,
    SettingsUpdateRequest,
    TwoFactorSettingsUpdateRequest,
)


__all__ = [
    "BillingSettingsUpdateRequest",
    "LocaleSettingsUpdateRequest",
    "SettingsUpdateRequest",
    "TwoFactorSettingsUpdateRequest",
]
