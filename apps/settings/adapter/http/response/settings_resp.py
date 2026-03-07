# apps/settings/adapter/http/response/settings_resp.py
# Adapter (HTTP): beállítások válasz.
# 2026.03.07 - Sárközi Mihály

from pydantic import BaseModel


class SettingsResp(BaseModel):
    two_factor_enabled: bool
