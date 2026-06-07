from __future__ import annotations

# backend/apps/kb/kb_reading/security/UrlContentPolicy.py
# Feladat: Letöltött tartalom szabályai.
# Sárközi Mihály - 2026.06.07

from typing import Any

from apps.kb.kb_reading.security.ReadingUrlSecurityError import ReadingUrlSecurityError
from apps.kb.kb_reading.security.UrlSecurityLimits import allowed_content_types, max_url_response_bytes
from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig


class UrlContentPolicy:
    """Letöltött tartalom típus és méret szabályai."""

    def __init__(self, *, config: ReadingConfig | None = None) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._config = config or DEFAULT_READING_CONFIG

    def is_allowed_content_type(self, content_type: str | None) -> bool:
        """Eldönti, hogy engedélyezett-e a tartalom típusa."""
        normalized = str(content_type or "").split(";", 1)[0].strip().lower()
        if not normalized:
            return False
        return any(
            normalized == allowed
            or normalized.endswith("+xml")
            and allowed in {"application/xml", "text/xml"}
            for allowed in allowed_content_types()
        )

    def looks_like_allowed_text_payload(self, chunk: bytes) -> bool:
        """Eldönti, hogy szöveges tartalomnak tűnik-e."""
        sample = bytes(chunk or b"")[:512].lstrip()
        if not sample:
            return False
        lowered = sample[:64].lower()
        if lowered.startswith((b"<!doctype html", b"<html", b"<?xml", b"{", b"[")):
            return True
        if b"\x00" in sample:
            return False
        printable = sum(
            1 for byte in sample if byte in {9, 10, 13} or 32 <= byte <= 126 or byte >= 128
        )
        return printable / max(len(sample), 1) >= 0.90

    def validate_declared_content_length(self, response: Any) -> None:
        """A modul egyik műveletét hajtja végre."""
        raw_length = response.headers.get("content-length")
        if not raw_length:
            return
        try:
            declared_length = int(str(raw_length).strip())
        except ValueError as exc:
            raise ReadingUrlSecurityError(
                "CONTENT_LENGTH_TOO_LARGE",
                "The URL response size header is invalid.",
            ) from exc
        if declared_length > max_url_response_bytes(config=self._config):
            raise ReadingUrlSecurityError("CONTENT_LENGTH_TOO_LARGE", "The URL response is too large.")

    def assert_streaming_size(self, total_bytes: int) -> None:
        """A modul egyik műveletét hajtja végre."""
        if total_bytes > max_url_response_bytes(config=self._config):
            raise ReadingUrlSecurityError("RESPONSE_TOO_LARGE", "The URL response body is too large.")


__all__ = ["UrlContentPolicy"]
