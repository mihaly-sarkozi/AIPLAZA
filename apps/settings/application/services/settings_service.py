# apps/settings/application/services/settings_service.py
# Rendszer beállítások kezelése. Cak az owner állíthatja, egyenlőre csak a 2FA van itt, de majd a fizetés és egyéb beállítások is itt lesznek.
# 2026.03.07 - Sárközi Mihály

from apps.settings.domain.setting import Setting
from apps.settings.ports import SettingsRepositoryInterface


class SettingsService:
    TWO_FACTOR_ENABLED_KEY = "two_factor_enabled"

    def __init__(self, repo: SettingsRepositoryInterface):
        self.repo = repo

    def is_two_factor_enabled(self) -> bool:
        setting = self.repo.get_by_key(self.TWO_FACTOR_ENABLED_KEY)
        if not setting:
            return True
        return setting.value.lower() == "true"

    def set_two_factor_enabled(self, enabled: bool, updated_by: int | None = None) -> None:
        value = "true" if enabled else "false"
        existing = self.repo.get_by_key(self.TWO_FACTOR_ENABLED_KEY)
        if existing:
            updated = existing.with_value(value, updated_by=updated_by)
        else:
            updated = Setting.new(key=self.TWO_FACTOR_ENABLED_KEY, value=value, updated_by=updated_by)
        self.repo.create_or_update(updated)
