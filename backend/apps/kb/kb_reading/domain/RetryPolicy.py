from __future__ import annotations

# backend/apps/kb/kb_reading/domain/RetryPolicy.py
# Feladat: Újrapróbálás szabályai sikertelen elemeknél.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass, field

from apps.kb.kb_reading.domain.ReadingErrorCode import ReadingErrorCode


@dataclass(frozen=True)
class RetryPolicy:
    """Újrapróbálás szabályai és késleltetései."""
    max_retry_count: int = 3
    retryable_error_codes: frozenset[ReadingErrorCode] = field(
        default_factory=lambda: frozenset(
            {
                ReadingErrorCode.FETCH_TIMEOUT,
                ReadingErrorCode.FETCH_FAILED,
                ReadingErrorCode.STORAGE_ERROR,
                ReadingErrorCode.RATE_LIMITED,
                ReadingErrorCode.INTERNAL_ERROR,
            }
        ),
    )

    def is_retryable(self, error_code: ReadingErrorCode | None) -> bool:
        """Eldönti, hogy újrapróbálható-e a hiba."""
        if error_code is None:
            return False
        return error_code in self.retryable_error_codes


DEFAULT_RETRY_POLICY = RetryPolicy()

__all__ = ["DEFAULT_RETRY_POLICY", "RetryPolicy"]
