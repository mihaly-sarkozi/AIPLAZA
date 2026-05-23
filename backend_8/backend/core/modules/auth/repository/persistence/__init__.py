# backend/core/modules/auth/repository/persistence/__init__.py
# Feladat: Az auth tenant-séma persistence repositoryk lazy exportfelülete. Session, 2FA code, 2FA attempt, pending 2FA és user authenticator repositorykat ad ki, miközben elkerüli az összes ORM adapter eager importját. Auth perzisztencia csomagbelépő bootstrap és use case wiring számára.
# Sárközi Mihály - 2026.05.21


def __getattr__(name: str):
    if name == "SessionRepository":
        from core.modules.auth.repository.persistence.session_repository import SessionRepository

        return SessionRepository
    if name == "TwoFactorRepository":
        from core.modules.auth.repository.persistence.two_factor_repository import TwoFactorRepository

        return TwoFactorRepository
    if name == "TwoFactorAttemptRepository":
        from core.modules.auth.repository.persistence.two_factor_attempt_repository import TwoFactorAttemptRepository

        return TwoFactorAttemptRepository
    if name == "Pending2FARepository":
        from core.modules.auth.repository.persistence.pending_2fa_repository import Pending2FARepository

        return Pending2FARepository
    if name == "UserAuthenticatorRepository":
        from core.modules.auth.repository.persistence.user_authenticator_repository import UserAuthenticatorRepository

        return UserAuthenticatorRepository
    raise AttributeError(name)

__all__ = [
    "SessionRepository",
    "TwoFactorRepository",
    "TwoFactorAttemptRepository",
    "Pending2FARepository",
    "UserAuthenticatorRepository",
]
