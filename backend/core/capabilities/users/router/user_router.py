# Felhasználói router – összeállítás
#
# Felelősség: a két al-router (profil + admin user CRUD) összegyűjtése egyetlen
# APIRouter-be, amelyet az app_factory beköthet.
# Üzleti logika és route definíciók → profile_router.py / admin_users_router.py.

from fastapi import APIRouter

from core.capabilities.users.router.admin_users_router import router as _admin_router
from core.capabilities.users.router.profile_router import router as _profile_router

router = APIRouter()
router.include_router(_profile_router)
router.include_router(_admin_router)
