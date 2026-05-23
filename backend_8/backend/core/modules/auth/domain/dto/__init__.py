# backend/core/modules/auth/domain/dto/__init__.py
# Feladat: Az auth domain DTO-k lazy exportfelülete. Login input, login siker, 2FA challenge, session, tenant auth context és 2FA code objektumokat ad ki úgy, hogy az importok ne töltsék be feleslegesen a teljes auth réteget. Auth domain DTO csomagbelépő.
# Sárközi Mihály - 2026.05.21

"""Auth DTO-k: lazy re-export, hogy ne húzza be a dataclass/pydantic modulokat importáláskor.

Exportált nevek:
  LoginInput, LoginSuccess, LoginTwoFactorRequired, LoginResult,
  Session, TenantAuthContext, TwoFactorCode
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional
    from core.modules.auth.domain.dto.login_input_dto import LoginInput
    from core.modules.auth.domain.dto.login_success_dto import LoginSuccess
    from core.modules.auth.domain.dto.login_two_factor_required_dto import LoginTwoFactorRequired
    from core.modules.auth.domain.dto.session import Session
    from core.modules.auth.domain.dto.tenant_auth_context import TenantAuthContext
    from core.modules.auth.domain.dto.two_factor_code import TwoFactorCode

_LAZY: dict[str, tuple[str, str]] = {
    "LoginInput": ("core.modules.auth.domain.dto.login_input_dto", "LoginInput"),
    "LoginSuccess": ("core.modules.auth.domain.dto.login_success_dto", "LoginSuccess"),
    "LoginTwoFactorRequired": (
        "core.modules.auth.domain.dto.login_two_factor_required_dto",
        "LoginTwoFactorRequired",
    ),
    "Session": ("core.modules.auth.domain.dto.session", "Session"),
    "TenantAuthContext": ("core.modules.auth.domain.dto.tenant_auth_context", "TenantAuthContext"),
    "TwoFactorCode": ("core.modules.auth.domain.dto.two_factor_code", "TwoFactorCode"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        module_path, attr = _LAZY[name]
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    if name == "LoginResult":
        from typing import Optional
        from core.modules.auth.domain.dto.login_success_dto import LoginSuccess
        from core.modules.auth.domain.dto.login_two_factor_required_dto import LoginTwoFactorRequired

        return Optional[LoginSuccess | LoginTwoFactorRequired]
    raise AttributeError(name)


__all__ = [
    "LoginInput",
    "LoginSuccess",
    "LoginTwoFactorRequired",
    "LoginResult",
    "Session",
    "TenantAuthContext",
    "TwoFactorCode",
]
