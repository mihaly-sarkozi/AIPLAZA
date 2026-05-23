# backend/core/modules/users/dependencies.py
# Feladat: FastAPI dependency helper réteg a users modulhoz. A UserService, UserProfileService és InviteService dependency providerjeit adja a routerek és külső endpointok számára. HTTP integrációs contract a users service-ekhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.deps.facade import service_dependency
from core.kernel.interface.keys import (
    PLATFORM_USERS_INVITE_SERVICE,
    PLATFORM_USERS_PROFILE_SERVICE,
    PLATFORM_USERS_SERVICE,
)


get_user_service = service_dependency(PLATFORM_USERS_SERVICE)
get_invite_service = service_dependency(PLATFORM_USERS_INVITE_SERVICE)
get_user_profile_service = service_dependency(PLATFORM_USERS_PROFILE_SERVICE)

__all__ = ["get_user_service", "get_invite_service", "get_user_profile_service"]
