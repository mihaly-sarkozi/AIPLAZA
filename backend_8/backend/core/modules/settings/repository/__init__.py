# backend/core/modules/settings/repository/__init__.py
# Feladat: A settings repository réteg exportfelülete. A SettingsRepository-t adja tovább a module assembly és service réteg számára. Vékony adapter csomag belépési pont.
# Sárközi Mihály - 2026.05.21
from core.modules.settings.repository.settings_repository import SettingsRepository

__all__ = ["SettingsRepository"]
