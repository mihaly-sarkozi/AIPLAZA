from __future__ import annotations

# backend/apps/profile/bootstrap/dependencies.py
# Feladat: FastAPI dependency adapterek a profile facade, aktuális user és tenant kontextus eléréséhez.
# Sárközi Mihály - 2026.05.24

from typing import Annotated

from fastapi import Depends, Request

from apps.profile.service.ports import ProfileFacadePort
from core.modules.users.domain.dto import User
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user


def get_profile_facade(request: Request):
    from core.kernel.http.app_dependencies import get_module_service
    from apps.profile.bootstrap.service_keys import PROFILE_SERVICE

    return get_module_service(PROFILE_SERVICE, request)


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
