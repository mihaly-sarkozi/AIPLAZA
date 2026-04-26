from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from apps.profile.service.ports import ProfileFacadePort
from core.capabilities.users.dto import User
from core.di import RequiredTenantContextDep
from core.platform.auth.auth_dependencies import get_current_user


def get_profile_facade():
    from apps.di import get_service
    from apps.profile.contracts import PROFILE_SERVICE

    return get_service(PROFILE_SERVICE)


get_profile_service = get_profile_facade

CurrentProfileUserDep = Annotated[User, Depends(get_current_user)]
ProfileFacadeDep = Annotated[ProfileFacadePort, Depends(get_profile_facade)]
ProfileTenantDep = RequiredTenantContextDep

__all__ = [
    "CurrentProfileUserDep",
    "ProfileFacadeDep",
    "ProfileTenantDep",
    "get_profile_facade",
    "get_profile_service",
]
