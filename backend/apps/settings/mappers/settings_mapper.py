from __future__ import annotations

from apps.settings.domain.settings_state import SettingsState


def build_settings_response(state: SettingsState) -> dict[str, object]:
    return {
        "two_factor_enabled": state.two_factor_enabled,
        "timezone": state.timezone,
        "date_format": state.date_format,
        "time_format": state.time_format,
    }


def build_settings_section_response(section) -> dict[str, object]:
    return {
        "key": section.key,
        "label": section.label,
        "path": section.path,
        "permission": section.permission,
        "order": section.order,
        "description": section.description,
        "source": section.source,
    }


__all__ = ["build_settings_response", "build_settings_section_response"]
