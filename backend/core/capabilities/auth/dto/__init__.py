# Ez a fájl a(z) core/capabilities/auth/dto csomag exportjait és inicializálási pontjait fogja össze.
"""Auth DTO-k: lazy re-export, hogy ne húzza be a dataclass/pydantic modulokat importáláskor.

Exportált nevek:
  LoginInput, LoginSuccess, LoginTwoFactorRequired, LoginResult,
  Session, TenantAuthContext, TwoFactorCode
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional
    from core.capabilities.auth.dto.login_input_dto import LoginInput
    from core.capabilities.auth.dto.login_success_dto import LoginSuccess
    from core.capabilities.auth.dto.login_two_factor_required_dto import LoginTwoFactorRequired
    from core.capabilities.auth.dto.session import Session
    from core.capabilities.auth.dto.tenant_auth_context import TenantAuthContext
    from core.capabilities.auth.dto.two_factor_code import TwoFactorCode

_LAZY: dict[str, tuple[str, str]] = {
    "LoginInput": ("core.capabilities.auth.dto.login_input_dto", "LoginInput"),
    "LoginSuccess": ("core.capabilities.auth.dto.login_success_dto", "LoginSuccess"),
    "LoginTwoFactorRequired": (
        "core.capabilities.auth.dto.login_two_factor_required_dto",
        "LoginTwoFactorRequired",
    ),
    "Session": ("core.capabilities.auth.dto.session", "Session"),
    "TenantAuthContext": ("core.capabilities.auth.dto.tenant_auth_context", "TenantAuthContext"),
    "TwoFactorCode": ("core.capabilities.auth.dto.two_factor_code", "TwoFactorCode"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        module_path, attr = _LAZY[name]
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    if name == "LoginResult":
        from typing import Optional
        from core.capabilities.auth.dto.login_success_dto import LoginSuccess
        from core.capabilities.auth.dto.login_two_factor_required_dto import LoginTwoFactorRequired

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
