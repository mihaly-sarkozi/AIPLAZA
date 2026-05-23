from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from apps.settings.service.ports import SettingsFacadePort
from core.modules.users.domain.dto import User
from core.modules.auth.web.dependencies.auth_dependencies import require_permission


def get_settings_facade(request: Request):
    from core.kernel.http.app_dependencies import get_module_service
    from apps.settings.contracts import SETTINGS_SERVICE

    return get_module_service(SETTINGS_SERVICE, request)


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
