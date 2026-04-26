# A felhasználók modul DI container-je.
# 2026.04.03 - Sárközi Mihály

from __future__ import annotations

from dataclasses import dataclass

from core.capabilities.auth.repositories.session_repository import SessionRepository
from core.capabilities.audit.service.audit_service import AuditService
from core.capabilities.email.email_service import EmailService
from core.capabilities.users.repositories.invite_token_repository import InviteTokenRepository
from core.capabilities.users.repositories.user_repository import UserRepository
from core.capabilities.users.service.invite_service import InviteService
from core.capabilities.users.service.profile_service import UserProfileService
from core.capabilities.users.service.user_service import UserService


@dataclass(frozen=True)
class UsersFeatureContainer:
    # Felhasználó modul üzleti logikája
    service: UserService
    profile_service: UserProfileService
    # Felhasználó meghívásos regisztrációs üzleti logikája
    invite_service: InviteService


# Ez a függvény felépíti a(z) felhasználók feature logikáját.
def build_users_feature(
    *,
    user_repo: UserRepository,
    invite_token_repo: InviteTokenRepository,
    audit_service: AuditService | None = None,
    session_repo: SessionRepository | None = None,
    email_service: EmailService | None = None,
    transaction_manager=None,
) -> UsersFeatureContainer:
    service = UserService(
        user_repository=user_repo,
        invite_token_repository=invite_token_repo,
        audit_service=audit_service,
        session_repository=session_repo,
        email_service=email_service,
        transaction_manager=transaction_manager,
    )
    profile_service = UserProfileService(user_repository=user_repo)
    invite_service = InviteService(
        user_repository=user_repo,
        invite_token_repository=invite_token_repo,
        audit_service=audit_service,
        email_service=email_service,
        transaction_manager=transaction_manager,
    )

    return UsersFeatureContainer(service=service, profile_service=profile_service, invite_service=invite_service)
