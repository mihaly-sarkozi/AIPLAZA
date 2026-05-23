# backend/core/modules/settings/service/__init__.py
# Feladat: A settings service réteg exportfelülete. A SettingsService-t adja tovább az auth modul, app settings API és tesztek számára. Vékony csomag belépési pont, üzleti logikát nem tartalmaz.
# Sárközi Mihály - 2026.05.21
from core.modules.settings.service.settings_service import SettingsService

__all__ = ["SettingsService"]
