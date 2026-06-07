from __future__ import annotations

# backend/apps/kb/kb_reading/validation/url.py
# Feladat: Hálózati cím formátum ellenőrzés.
# Sárközi Mihály - 2026.06.07

from urllib.parse import urlparse

from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from apps.kb.shared.errors import KbValidationError


def validate_url_syntax(url: str | None, *, config: ReadingConfig | None = None) -> str:
    """A modul egyik műveletét hajtja végre."""
    cfg = config or DEFAULT_READING_CONFIG
    raw = str(url or "").strip()
    if not raw:
        raise KbValidationError("URL is required")
    if len(raw) > cfg.max_url_length:
        raise KbValidationError("URL is too long")
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise KbValidationError("Invalid URL")
    if parsed.username or parsed.password:
        raise KbValidationError("URL must not contain credentials")
    return raw


def validate_url_scheme(url: str, *, config: ReadingConfig | None = None) -> str:
    """A modul egyik műveletét hajtja végre."""
    cfg = config or DEFAULT_READING_CONFIG
    validated = validate_url_syntax(url, config=cfg)
    scheme = urlparse(validated).scheme.lower()
    if scheme not in cfg.allowed_url_schemes:
        allowed = ", ".join(sorted(cfg.allowed_url_schemes))
        raise KbValidationError(f"Unsupported URL scheme. Allowed: {allowed}")
    return validated


__all__ = ["validate_url_scheme", "validate_url_syntax"]
