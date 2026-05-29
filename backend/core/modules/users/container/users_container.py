# backend/core/modules/users/container/users_container.py
# Feladat: A users modul belső dependency assembly objektuma. UserRepository, InviteTokenRepository, UserService, UserProfileService és InviteService példányokat köt össze audit, email és auth adapterekkel. Users composition réteg a UsersCoreModule alatt.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass

from core.modules.auth.repository.persistence.session_repository import SessionRepository
from core.infrastructure.audit.service.audit_service import AuditService
from core.infrastructure.email.email_service import EmailService
from core.modules.users.repository.persistence.invite_token_repository import InviteTokenRepository
from core.modules.users.repository.persistence.user_repository import UserRepository
from core.modules.users.service.invite_service import InviteService
from core.modules.users.service.profile_service import UserProfileService
from core.modules.users.service.user_service import UserService


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
    profile_service = UserProfileService(
        user_repository=user_repo,
        email_service=email_service,
        session_repository=session_repo,
        audit_service=audit_service,
    )
    invite_service = InviteService(
        user_repository=user_repo,
        invite_token_repository=invite_token_repo,
        audit_service=audit_service,
        email_service=email_service,
        transaction_manager=transaction_manager,
    )

    return UsersFeatureContainer(service=service, profile_service=profile_service, invite_service=invite_service)
