from __future__ import annotations

# backend/apps/kb/kb_reading/security/UrlFetcher.py
# Feladat: Biztonságos letöltés hálózati címről.
# Sárközi Mihály - 2026.06.07

import requests

from apps.kb.kb_reading.security.ReadingUrlSecurityError import ReadingUrlSecurityError
from apps.kb.kb_reading.security.RedirectPolicy import RedirectPolicy
from apps.kb.kb_reading.security.UrlContentPolicy import UrlContentPolicy
from apps.kb.kb_reading.security.UrlFetchResult import UrlFetchResult
from apps.kb.kb_reading.security.UrlSecurityValidator import UrlSecurityValidator
from apps.kb.kb_reading.security.UrlTarget import UrlTarget
from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig

_REQUEST_HEADERS = {
    "Accept-Encoding": "identity",
}


class UrlFetcher:
    """Biztonságos letöltő a hálózati címekhez."""
    def __init__(
        self,
        *,
        config: ReadingConfig | None = None,
        validator: UrlSecurityValidator | None = None,
        redirect_policy: RedirectPolicy | None = None,
        content_policy: UrlContentPolicy | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Összeállítja a szükséges függőségeket."""
        self._config = config or DEFAULT_READING_CONFIG
        self._validator = validator or UrlSecurityValidator(config=self._config)
        self._redirect_policy = redirect_policy or RedirectPolicy(config=self._config)
        self._content_policy = content_policy or UrlContentPolicy(config=self._config)
        self._session = session

    def fetch(self, url: str, *, timeout: int = 20) -> UrlFetchResult:
        """Letölti a tartalmat a megadott címről."""
        origin_url = self._validator.validate_syntax(url)
        current_target = self._validator.validate_target(origin_url)
        session = self._session or requests.Session()
        visited: set[str] = set()
        redirect_count = 0

        while True:
            self._redirect_policy.assert_not_loop(current_url=current_target.url, visited=visited)
            visited.add(current_target.url)
            response = self._request_once(
                session,
                method="GET",
                target=current_target,
                timeout=timeout,
            )
            if response.is_redirect or response.is_permanent_redirect:
                self._redirect_policy.assert_can_follow(redirect_count=redirect_count)
                redirect_count += 1
                current_target = self._redirect_policy.next_target(response, current_target)
                continue

            content_type = response.headers.get("content-type") or None
            content_type_allowed = self._content_policy.is_allowed_content_type(content_type)
            self._content_policy.validate_declared_content_length(response)
            if content_type and not content_type_allowed:
                raise ReadingUrlSecurityError(
                    "CONTENT_TYPE_NOT_ALLOWED",
                    "The URL content type is not allowed.",
                )

            body, size_bytes = self._read_response_body(response, content_type=content_type)
            return UrlFetchResult(
                origin_url=origin_url,
                final_url=current_target.url,
                status_code=int(response.status_code),
                content_type=content_type,
                body=body,
                size_bytes=size_bytes,
            )

    def _request_once(
        self,
        session: requests.Session,
        *,
        method: str,
        target: UrlTarget,
        timeout: int,
    ) -> requests.Response:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        self._validator.assert_dns_still_matches(target)
        try:
            return session.request(
                method,
                target.url,
                allow_redirects=False,
                headers=_REQUEST_HEADERS,
                stream=True,
                timeout=timeout,
            )
        except requests.Timeout as exc:
            raise ReadingUrlSecurityError(
                "DOWNLOAD_TIMEOUT",
                "The URL download timed out.",
            ) from exc
        except requests.RequestException as exc:
            raise ReadingUrlSecurityError(
                "DNS_RESOLUTION_FAILED",
                "The provided URL host could not be resolved.",
            ) from exc

    def _read_response_body(
        self,
        response: requests.Response,
        *,
        content_type: str | None,
    ) -> tuple[bytes, int]:
        """Belső segédfüggvény a folyamat egy lépéséhez."""
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            if (
                not chunks
                and not content_type
                and not self._content_policy.looks_like_allowed_text_payload(chunk)
            ):
                raise ReadingUrlSecurityError(
                    "CONTENT_TYPE_NOT_ALLOWED",
                    "The URL content type is not allowed.",
                )
            total += len(chunk)
            self._content_policy.assert_streaming_size(total)
            chunks.append(chunk)
        body = b"".join(chunks)
        return body, len(body)
__all__ = ["UrlFetchResult", "UrlFetcher"]
