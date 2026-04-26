"""User HTTP prezentációs segédfüggvények.

Felelősség: User domain objektum → UserResponse HTTP DTO konverzió.

A ``pending_registration`` üzleti szabály itt él egy helyen:
  - Ha a user inaktív ÉS nincs registration_completed_at → regisztráció folyamatban
  - Ha a user aktív → pending_registration = False
  - Ha nincs id (nem persistált) → pending_registration = False

Ezt a modult importálja az admin_users_router és az invite_router egyaránt,
hogy ne kelljen a logikát két helyen fenntartani.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.capabilities.users.dto.user import User
    from core.capabilities.users.router.responses.user_response import UserResponse


def is_pending_registration(user: "User") -> bool:
    """Meghatározza, hogy a user regisztrációja még folyamatban van-e.

    A user akkor számít „pending registration" állapotban lévőnek, ha:
    - van id-ja (persistált felhasználó)
    - inaktív (is_active=False)
    - a regisztráció nem lett befejezve (registration_completed_at is None)
    """
    if not user.id:
        return False
    return not user.is_active and (getattr(user, "registration_completed_at", None) is None)


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
    from core.capabilities.users.router.responses.user_response import UserResponse

    user_dict = asdict(user)
    user_dict.pop("password_hash", None)
    user_dict.pop("registration_completed_at", None)
    if pending_registration is None:
        pending_registration = is_pending_registration(user)
    user_dict["pending_registration"] = pending_registration
    return UserResponse.model_validate(user_dict)
