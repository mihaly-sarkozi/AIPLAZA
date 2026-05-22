# backend/core/modules/auth/web/dependencies/__init__.py
# Feladat: Az auth FastAPI dependency helperök exportfelülete. Current user, opcionális user, permission, role és WebSocket token validáció dependency-ket ad routereknek, hogy ne közvetlenül a middleware state-et kezeljék. Auth web dependency csomagbelépő.
# Sárközi Mihály - 2026.05.21

from core.modules.auth.web.dependencies.auth_dependencies import (
    get_current_user,
    get_current_user_optional,
    has_permission,
    require_all_permissions,
    require_any_permission,
    require_permission,
    require_role,
    validate_ws_token,
)

__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "has_permission",
    "require_all_permissions",
    "require_any_permission",
    "require_permission",
    "require_role",
    "validate_ws_token",
]
