# backend/core/modules/users/web/helpers/profile_helper.py
# Feladat: Profil helper re-export a locale/theme policyhoz. A web réteg számára kényelmes importpontot ad az effective_locale_theme számításhoz. Users web helper adapter.
# Sárközi Mihály - 2026.05.21

from core.modules.users.domain.dto.user import User
from core.modules.users.domain.policies.profile_policy import effective_locale_theme

__all__ = ["effective_locale_theme"]
