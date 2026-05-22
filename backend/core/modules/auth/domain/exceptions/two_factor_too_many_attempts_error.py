# backend/core/modules/auth/domain/exceptions/two_factor_too_many_attempts_error.py
# Feladat: Túl sok sikertelen 2FA próbálkozást jelző domain exception. A TwoFactorService dobja brute-force limit túllépésekor, a router pedig 429 válasszá alakítja. Auth domain exception a 2FA policy enforcementhez.
# Sárközi Mihály - 2026.05.21

class TwoFactorTooManyAttemptsError(Exception):
    """Túl sok sikertelen 2FA próbálkozás."""

    pass
