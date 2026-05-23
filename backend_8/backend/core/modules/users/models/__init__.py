# backend/core/modules/users/models/__init__.py
# Feladat: Users perzisztencia ORM modellek exportfelulete. Ez a csomag
# tartalmazhat SQLAlchemy modelleket; a domain csomag tiszta marad.

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY: dict[str, tuple[str, str]] = {
    "UserORM": ("core.modules.users.models.user_orm", "UserORM"),
    "UserInviteTokenORM": ("core.modules.users.models.user_invite_token_orm", "UserInviteTokenORM"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = list(_LAZY)
