# Ez a fájl a függőség-injektálási belépési pontokat és helper függvényeket tartalmazza.
from __future__ import annotations

from core.di import service_dependency
from core.platform.service_keys import (
    PLATFORM_USERS_INVITE_SERVICE,
    PLATFORM_USERS_PROFILE_SERVICE,
    PLATFORM_USERS_SERVICE,
)


get_user_service = service_dependency(PLATFORM_USERS_SERVICE)
get_invite_service = service_dependency(PLATFORM_USERS_INVITE_SERVICE)
get_user_profile_service = service_dependency(PLATFORM_USERS_PROFILE_SERVICE)

__all__ = ["get_user_service", "get_invite_service", "get_user_profile_service"]
