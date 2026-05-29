from __future__ import annotations

# backend/apps/profile/domain/preferences.py
# Feladat: Frameworkfüggetlen profile preference domain modell és engedélyezett layout típusok.
# Sárközi Mihály - 2026.05.24

from dataclasses import dataclass
from typing import Literal

DashboardLayout = Literal["comfortable", "compact"]


@dataclass(frozen=True)
class ProfilePreferences:
    user_id: int
    dashboard_layout: DashboardLayout = "comfortable"
    show_tips: bool = True


__all__ = ["DashboardLayout", "ProfilePreferences"]
