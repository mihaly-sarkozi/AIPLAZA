from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DashboardLayout = Literal["comfortable", "compact"]


@dataclass(frozen=True)
class ProfilePreferences:
    user_id: int
    dashboard_layout: DashboardLayout = "comfortable"
    show_tips: bool = True


__all__ = ["DashboardLayout", "ProfilePreferences"]
