# backend/apps/profile/infra/__init__.py
# Feladat: A profile infrastruktúra exportjai, jelenleg a preference repository publikus belépési pontja.
# Sárközi Mihály - 2026.05.24

from apps.profile.infra.preferences_repository import ProfilePreferencesRepository

__all__ = ["ProfilePreferencesRepository"]
