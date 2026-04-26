# Túl sok sikertelen 2FA próbálkozás kivétel
# 2026.03.07 - Sárközi Mihály

class TwoFactorTooManyAttemptsError(Exception):
    """Túl sok sikertelen 2FA próbálkozás."""

    pass
