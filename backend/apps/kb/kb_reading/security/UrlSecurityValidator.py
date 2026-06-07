from __future__ import annotations

# backend/apps/kb/kb_reading/security/UrlSecurityValidator.py
# Feladat: Hálózati cím biztonság: belső címek kiszűrése.
# Sárközi Mihály - 2026.06.07

from urllib.parse import urlparse

from apps.kb.kb_reading.security.ReadingUrlSecurityError import ReadingUrlSecurityError
from apps.kb.kb_reading.security.UrlSecurityLimits import _map_validation_error, resolve_public_host
from apps.kb.kb_reading.security.UrlTarget import UrlTarget
from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig
from apps.kb.kb_reading.validation.ValidateUrl import validate_url_scheme
from apps.kb.shared.errors import KbValidationError


class UrlSecurityValidator:
    """Hálózati cím biztonsági ellenőrző."""

    def __init__(self, *, config: ReadingConfig | None = None) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._config = config or DEFAULT_READING_CONFIG

    def validate_syntax(self, url: str) -> str:
        """A modul egyik műveletét hajtja végre."""
        try:
            return validate_url_scheme(url, config=self._config)
        except KbValidationError as exc:
            code = _map_validation_error(str(exc))
            raise ReadingUrlSecurityError(code, str(exc)) from exc

    def resolve_public_host_or_raise(self, hostname: str) -> list[str]:
        """Feloldja a gazdagép nevét vagy hibát dob."""
        return resolve_public_host(hostname)

    def validate_target(self, url: str) -> UrlTarget:
        """A modul egyik műveletét hajtja végre."""
        normalized = self.validate_syntax(url)
        parsed = urlparse(normalized)
        hostname = str(parsed.hostname or "").strip()
        if not hostname:
            raise ReadingUrlSecurityError(
                "DNS_RESOLUTION_FAILED",
                "The provided URL host could not be resolved.",
            )
        addresses = tuple(self.resolve_public_host_or_raise(hostname))
        return UrlTarget(url=normalized, parsed=parsed, addresses=addresses)

    def assert_dns_still_matches(self, target: UrlTarget) -> None:
        """A modul egyik műveletét hajtja végre."""
        hostname = str(target.parsed.hostname or "").strip()
        current_addresses = tuple(self.resolve_public_host_or_raise(hostname))
        if set(current_addresses) != set(target.addresses):
            raise ReadingUrlSecurityError(
                "DNS_REBINDING_DETECTED",
                "The URL host DNS mapping changed during validation.",
            )


__all__ = ["UrlSecurityValidator"]
