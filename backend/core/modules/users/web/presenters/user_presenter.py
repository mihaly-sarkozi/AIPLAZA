# backend/core/modules/users/web/presenters/user_presenter.py
# Feladat: User domain DTO és HTTP response közötti presenter logikát tartalmaz. Role, profil, security és optional mezők konzisztens response formátumát állítja elő. Users presentation adapter.
# Sárközi Mihály - 2026.05.21

"""User HTTP prezentációs segédfüggvények.

Felelősség: User domain objektum → UserResponse HTTP DTO konverzió.

A ``pending_registration`` üzleti szabály itt él egy helyen:
  - Ha a user még nem állított be saját jelszót → regisztráció folyamatban
  - Ha a user admin által inaktív → pending_registration = False
  - Ha nincs id (nem persistált) → pending_registration = False

Ezt a modult importálja az admin_users_router és az invite_router egyaránt,
hogy ne kelljen a logikát két helyen fenntartani.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.modules.users.domain.dto.user import User
    from core.modules.users.router.responses.user_response import UserResponse


def is_pending_registration(user: "User") -> bool:
    """Meghatározza, hogy a user regisztrációja még folyamatban van-e.

    A user akkor számít „pending registration" állapotban lévőnek, ha:
    - van id-ja (persistált felhasználó)
    - még nincs saját jelszava
    - nincs admin által inaktiválva
    """
    if not user.id:
        return False
    return bool(user.is_active) and not bool(getattr(user, "credentials_password_set", True))


def user_to_response(
    user: "User",
    *,
    pending_registration: bool | None = None,
) -> "UserResponse":
    """User domain objektumból UserResponse HTTP DTO.

    Args:
        user: Domain User objektum.
        pending_registration: Ha explicit értéket kap, azt használja;
            különben ``is_pending_registration(user)`` alapján határozza meg.
    """
    from core.modules.users.router.responses.user_response import UserResponse

    user_dict = asdict(user)
    user_dict.pop("password_hash", None)
    user_dict.pop("registration_completed_at", None)
    if pending_registration is None:
        pending_registration = is_pending_registration(user)
    user_dict["pending_registration"] = pending_registration
    return UserResponse.model_validate(user_dict)
