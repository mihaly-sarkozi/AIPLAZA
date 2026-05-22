# backend/core/modules/users/repository/persistence/__init__.py
# Feladat: A users persistence repository csomag lazy re-export felülete. UserRepository és InviteTokenRepository osztályokat ad tovább stabil importpontként a bootstrap, tesztek és modul assembly számára. Users repository belépési pont.
# Sárközi Mihály - 2026.05.21

"""Lazy re-export: SQLAlchemy-függő repository-k csak igény szerint töltődnek be."""
from __future__ import annotations


def __getattr__(name: str):
    if name == "UserRepository":
        from core.modules.users.repository.persistence.user_repository import UserRepository

        return UserRepository
    if name == "InviteTokenRepository":
        from core.modules.users.repository.persistence.invite_token_repository import InviteTokenRepository

        return InviteTokenRepository
    raise AttributeError(name)


__all__ = ["UserRepository", "InviteTokenRepository"]
