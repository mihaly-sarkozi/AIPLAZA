# Ez a fájl a(z) core/capabilities/users/repositories csomag exportjait és inicializálási pontjait fogja össze.
"""Lazy re-export: SQLAlchemy-függő repository-k csak igény szerint töltődnek be."""
from __future__ import annotations


def __getattr__(name: str):
    if name == "UserRepository":
        from core.capabilities.users.repositories.user_repository import UserRepository

        return UserRepository
    if name == "InviteTokenRepository":
        from core.capabilities.users.repositories.invite_token_repository import InviteTokenRepository

        return InviteTokenRepository
    raise AttributeError(name)


__all__ = ["UserRepository", "InviteTokenRepository"]
