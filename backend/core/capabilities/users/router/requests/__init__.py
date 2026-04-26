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
        "core.capabilities.users.router.requests.change_password_request",
        "ChangePasswordRequest",
    ),
    "SetInitialPasswordRequest": (
        "core.capabilities.users.router.requests.set_initial_password_request",
        "SetInitialPasswordRequest",
    ),
    "DemoUnsubscribeRequest": (
        "core.capabilities.users.router.requests.demo_unsubscribe_request",
        "DemoUnsubscribeRequest",
    ),
    "ForgotPasswordRequest": (
        "core.capabilities.users.router.requests.forgot_password_request",
        "ForgotPasswordRequest",
    ),
    "SetPasswordRequest": (
        "core.capabilities.users.router.requests.set_password_request",
        "SetPasswordRequest",
    ),
    "UpdateMeRequest": (
        "core.capabilities.users.router.requests.update_me_request",
        "UpdateMeRequest",
    ),
    "UserCreateRequest": (
        "core.capabilities.users.router.requests.user_create_request",
        "UserCreateRequest",
    ),
    "UserUpdateRequest": (
        "core.capabilities.users.router.requests.user_update_request",
        "UserUpdateRequest",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
