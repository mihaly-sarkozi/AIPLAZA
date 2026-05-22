# backend/core/modules/users/router/requests/__init__.py
# Feladat: A users router request DTO-k lazy exportfelülete. Password, profile, invite és admin CRUD request modelleket ad tovább routerek és tesztek számára. Users web request contract belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = [
    "UserCreateRequest",
    "UserUpdateRequest",
    "SetPasswordRequest",
    "SetInitialPasswordRequest",
    "DemoUnsubscribeRequest",
    "UpdateMeRequest",
    "ForgotPasswordRequest",
    "ChangePasswordRequest",
]

_LAZY: dict[str, tuple[str, str]] = {
    "ChangePasswordRequest": (
        "core.modules.users.router.requests.change_password_request",
        "ChangePasswordRequest",
    ),
    "SetInitialPasswordRequest": (
        "core.modules.users.router.requests.set_initial_password_request",
        "SetInitialPasswordRequest",
    ),
    "DemoUnsubscribeRequest": (
        "core.modules.users.router.requests.demo_unsubscribe_request",
        "DemoUnsubscribeRequest",
    ),
    "ForgotPasswordRequest": (
        "core.modules.users.router.requests.forgot_password_request",
        "ForgotPasswordRequest",
    ),
    "SetPasswordRequest": (
        "core.modules.users.router.requests.set_password_request",
        "SetPasswordRequest",
    ),
    "UpdateMeRequest": (
        "core.modules.users.router.requests.update_me_request",
        "UpdateMeRequest",
    ),
    "UserCreateRequest": (
        "core.modules.users.router.requests.user_create_request",
        "UserCreateRequest",
    ),
    "UserUpdateRequest": (
        "core.modules.users.router.requests.user_update_request",
        "UserUpdateRequest",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
