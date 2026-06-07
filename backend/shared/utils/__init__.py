# backend/shared/utils/__init__.py
# Feladat: A shared utils csomag publikus exportfelülete. Időkezelési, UTC normalizálási, hash, log sanitization és slug helper funkciókat ad tovább core, infrastructure és app moduloknak. Általános, modulfuggetlen utility belépési pont.
# Sárközi Mihály - 2026.05.21

"""
Altalanos, modulfuggetlen segedek gyujto csomagja.
"""

from shared.utils.datetime_utils import normalize_utc_datetime
from shared.utils.hash import sha256_bytes, sha256_hex, sha256_text
from shared.utils.idempotency import (
    DEFAULT_IDEMPOTENCY_PIPELINE_VERSION,
    build_idempotency_key,
    content_hash_from_idempotency_key,
)
from shared.utils.clock import Clock, SystemClock, get_default_clock, set_default_clock, utc_now, utc_now_naive, utc_today
from shared.utils.sanitization import sanitize_log_data
from shared.utils.slug import normalize_slug, slug_is_valid
from shared.utils.tenant_slug import tenant_slug_or_default

__all__ = [
    "DEFAULT_IDEMPOTENCY_PIPELINE_VERSION",
    "Clock",
    "SystemClock",
    "build_idempotency_key",
    "content_hash_from_idempotency_key",
    "get_default_clock",
    "normalize_utc_datetime",
    "normalize_slug",
    "sanitize_log_data",
    "set_default_clock",
    "sha256_bytes",
    "sha256_hex",
    "sha256_text",
    "slug_is_valid",
    "tenant_slug_or_default",
    "utc_now",
    "utc_now_naive",
    "utc_today",
]
