from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from apps.settings.service.ports import SettingsFacadePort
from core.capabilities.users.dto import User
from core.platform.auth.auth_dependencies import require_permission


def get_settings_facade():
    from apps.di import get_service
    from apps.settings.contracts import SETTINGS_SERVICE

    return get_service(SETTINGS_SERVICE)


get_settings_service = get_settings_facade

SettingsFacadeDep = Annotated[SettingsFacadePort, Depends(get_settings_facade)]
SettingsReadUserDep = Annotated[User, Depends(require_permission("settings.read"))]
SettingsWriteUserDep = Annotated[User, Depends(require_permission("settings.write"))]

__all__ = [
    "SettingsFacadeDep",
    "SettingsReadUserDep",
    "SettingsWriteUserDep",
    "get_settings_facade",
    "get_settings_service",
]
