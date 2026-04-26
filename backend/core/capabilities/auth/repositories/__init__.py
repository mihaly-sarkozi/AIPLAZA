# Ez a fájl a(z) core/capabilities/auth/repositories csomag exportjait és inicializálási pontjait fogja össze.


def __getattr__(name: str):
    if name == "SessionRepository":
        from core.capabilities.auth.repositories.session_repository import SessionRepository

        return SessionRepository
    if name == "TwoFactorRepository":
        from core.capabilities.auth.repositories.two_factor_repository import TwoFactorRepository

        return TwoFactorRepository
    if name == "TwoFactorAttemptRepository":
        from core.capabilities.auth.repositories.two_factor_attempt_repository import TwoFactorAttemptRepository

        return TwoFactorAttemptRepository
    if name == "Pending2FARepository":
        from core.capabilities.auth.repositories.pending_2fa_repository import Pending2FARepository

        return Pending2FARepository
    raise AttributeError(name)

__all__ = [
    "SessionRepository",
    "TwoFactorRepository",
    "TwoFactorAttemptRepository",
    "Pending2FARepository",
]
