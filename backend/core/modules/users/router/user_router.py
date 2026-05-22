# backend/core/modules/users/router/user_router.py
# Feladat: A users root router aggregátora. Admin és profile routereket fog össze egy közös APIRouter alatt, hogy a kernel route registry egyetlen users routert köthessen be. Users HTTP router composition réteg.
# Sárközi Mihály - 2026.05.21

from fastapi import APIRouter

from core.modules.users.router.admin_users_router import router as _admin_router
from core.modules.users.router.profile_router import router as _profile_router

router = APIRouter()
router.include_router(_profile_router)
router.include_router(_admin_router)
