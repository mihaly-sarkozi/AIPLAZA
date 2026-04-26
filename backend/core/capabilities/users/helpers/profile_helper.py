# Felhasználó beállítások (locale, theme) effektív értékeinek kiszámítása.

from core.capabilities.users.dto.user import User
from core.capabilities.users.policies.profile_policy import effective_locale_theme

__all__ = ["effective_locale_theme"]
