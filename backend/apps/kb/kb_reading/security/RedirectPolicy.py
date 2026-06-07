from __future__ import annotations

# backend/apps/kb/kb_reading/security/RedirectPolicy.py
# Feladat: Átirányítások szabályai.
# Sárközi Mihály - 2026.06.07

from typing import Any
from urllib.parse import urljoin

from apps.kb.kb_reading.security.ReadingUrlSecurityError import ReadingUrlSecurityError
from apps.kb.kb_reading.security.UrlSecurityLimits import max_url_redirects
from apps.kb.kb_reading.security.UrlSecurityValidator import UrlSecurityValidator
from apps.kb.kb_reading.security.UrlTarget import UrlTarget
from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig


class RedirectPolicy:
    """Átirányítások szabályai letöltéskor."""

    def __init__(self, *, config: ReadingConfig | None = None) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._config = config or DEFAULT_READING_CONFIG
        self._validator = UrlSecurityValidator(config=self._config)

    def response_location(self, response: Any, current_url: str) -> str | None:
        """Kinyeri az átirányítás cél címét a válaszból."""
        location = response.headers.get("location")
        if not location:
            return None
        return urljoin(current_url, location)

    def next_target(self, response: Any, current_target: UrlTarget) -> UrlTarget:
        """Meghatározza a következő letöltési célt."""
        next_url = self.response_location(response, current_target.url)
        if not next_url:
            raise ReadingUrlSecurityError(
                "REDIRECT_LIMIT_EXCEEDED",
                "The URL redirect target is invalid.",
            )
        next_target = self._validator.validate_target(next_url)
        if (
            current_target.parsed.scheme.lower() == "https"
            and next_target.parsed.scheme.lower() == "http"
        ):
            raise ReadingUrlSecurityError(
                "REDIRECT_DOWNGRADE_BLOCKED",
                "HTTPS to HTTP redirect is not allowed.",
            )
        return next_target

    def assert_can_follow(self, *, redirect_count: int) -> None:
        """A modul egyik műveletét hajtja végre."""
        if redirect_count >= max_url_redirects(config=self._config):
            raise ReadingUrlSecurityError("REDIRECT_LIMIT_EXCEEDED", "Redirect limit exceeded.")

    def assert_not_loop(self, *, current_url: str, visited: set[str]) -> None:
        """A modul egyik műveletét hajtja végre."""
        if current_url in visited:
            raise ReadingUrlSecurityError("REDIRECT_LIMIT_EXCEEDED", "Redirect loop detected.")


__all__ = ["RedirectPolicy"]
