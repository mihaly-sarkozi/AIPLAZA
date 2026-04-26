"""Platform auth: token szolgáltatás, dependency-k, domain szintű auth policy.

Itt él az auth **domain** policy és a tokenhez / sessionhöz kapcsolódó üzleti
szabályok (pl. `security_policy.py`, 2FA policy, `auth_dependencies` jogosultság
ellenőrzések). Edge-védelem (CSRF middleware, trusted host, nyers JWT secret
ellenőrzés) a `core.kernel.security` és `core.kernel.middleware.security`
alatt marad — ne duplikáld a policy döntéseket ott.
"""

_EXPORT_MAP = {
    "TokenService": ("core.platform.auth.token_service", "TokenService"),
    "add": ("core.platform.auth.token_allowlist", "add"),
    "is_allowed": ("core.platform.auth.token_allowlist", "is_allowed"),
    "remove_by_user": ("core.platform.auth.token_allowlist", "remove_by_user"),
    "get_current_user": ("core.platform.auth.auth_dependencies", "get_current_user"),
    "get_current_user_optional": ("core.platform.auth.auth_dependencies", "get_current_user_optional"),
    "has_permission": ("core.platform.auth.auth_dependencies", "has_permission"),
    "require_permission": ("core.platform.auth.auth_dependencies", "require_permission"),
    "require_any_permission": ("core.platform.auth.auth_dependencies", "require_any_permission"),
    "require_all_permissions": ("core.platform.auth.auth_dependencies", "require_all_permissions"),
    "require_role": ("core.platform.auth.auth_dependencies", "require_role"),
    "validate_ws_token": ("core.platform.auth.auth_dependencies", "validate_ws_token"),
    "get_2fa_attempt_window_minutes": ("core.platform.auth.two_factor_policy", "get_2fa_attempt_window_minutes"),
    "get_2fa_code_expiry_minutes": ("core.platform.auth.two_factor_policy", "get_2fa_code_expiry_minutes"),
    "get_2fa_max_attempts": ("core.platform.auth.two_factor_policy", "get_2fa_max_attempts"),
}


def __getattr__(name: str):
    if name in _EXPORT_MAP:
        module_name, attr_name = _EXPORT_MAP[name]
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)
    raise AttributeError(name)

__all__ = [
    "TokenService",
    "add",
    "is_allowed",
    "remove_by_user",
    "get_current_user",
    "get_current_user_optional",
    "has_permission",
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
    "require_role",
    "validate_ws_token",
    "get_2fa_attempt_window_minutes",
    "get_2fa_code_expiry_minutes",
    "get_2fa_max_attempts",
]
