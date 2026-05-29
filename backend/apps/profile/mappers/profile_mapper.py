from __future__ import annotations

# backend/apps/profile/mappers/profile_mapper.py
# Feladat: Core profile payload és app-specifikus preference adatok response payloadba rendezése.
# Sárközi Mihály - 2026.05.24

from apps.profile.domain.preferences import ProfilePreferences


def build_profile_preferences_response(prefs: ProfilePreferences) -> dict[str, object]:
    return {
        "app_preferences": {
            "dashboard_layout": prefs.dashboard_layout,
            "show_tips": prefs.show_tips,
        }
    }


def build_profile_response(core_payload: dict[str, object], prefs: ProfilePreferences) -> dict[str, object]:
    return {
        **core_payload,
        **build_profile_preferences_response(prefs),
    }


__all__ = ["build_profile_preferences_response", "build_profile_response"]
