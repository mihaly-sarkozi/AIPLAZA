# backend/apps/knowledge/service/url_ingest_security.py
# Feladat: URL ingest SSRF védelmi helper logikát tartalmaz. HTTP/HTTPS validációt, DNS/IP tiltólistát, DNS rebinding ellenőrzést, redirect policyt, content-type allowlistet és streaming méretlimitet kényszerít ki a knowledge URL ingest folyamatban. Program-specifikus biztonsági guard külső URL fetchhez.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import ParseResult, urljoin, urlparse

import requests
from core.kernel.config.config_loader import settings
from core.kernel.http.app_errors import AppError


class UrlIngestError(AppError):
    code = "URL_INGEST_REJECTED"
    status_code = 400
    safe_message = "The provided URL is not allowed."

    def __init__(self, code: str, message: str):
        super().__init__(
            message or self.safe_message,
            code=str(code or self.code).strip() or self.code,
            status_code=self.status_code,
        )


class UrlIngestRejected(UrlIngestError):
    pass


class UrlIngestSecurityError(UrlIngestRejected):
    pass


@dataclass(frozen=True)
class UrlFetchResult:
    url: str
    status_code: int
    content_type: str
    body: bytes = b""
    final_url: str | None = None


@dataclass(frozen=True)
class UrlTarget:
    url: str
    parsed: ParseResult
    addresses: tuple[str, ...]


_DEFAULT_ALLOWED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "application/json",
)

_REQUEST_HEADERS = {
    # A szerver gzipet ettől még küldhet, ezért a streamelt, kicsomagolt méretet is limitáljuk.
    "Accept-Encoding": "identity",
}


def max_url_response_bytes() -> int:
    return max(1024, int(getattr(settings, "knowledge_url_ingest_max_response_bytes", 2 * 1024 * 1024) or (2 * 1024 * 1024)))


def max_url_redirects() -> int:
    return max(0, min(5, int(getattr(settings, "knowledge_url_ingest_max_redirects", 3) or 3)))


def allowed_content_types() -> tuple[str, ...]:
    raw = getattr(settings, "knowledge_url_ingest_allowed_content_types", None)
    if isinstance(raw, str) and raw.strip():
        values = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
        return values or _DEFAULT_ALLOWED_CONTENT_TYPES
    if isinstance(raw, (list, tuple, set)):
        values = tuple(str(item).strip().lower() for item in raw if str(item).strip())
        return values or _DEFAULT_ALLOWED_CONTENT_TYPES
    return _DEFAULT_ALLOWED_CONTENT_TYPES


def validate_url_syntax(url: str) -> str:
    return UrlValidator().validate_syntax(url)


def _is_forbidden_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def _resolve_public_host(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlIngestSecurityError("DNS_RESOLUTION_FAILED", "The provided URL host could not be resolved.") from exc
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        address = str(sockaddr[0])
        if address in addresses:
            continue
        if _is_forbidden_ip(address):
            raise UrlIngestSecurityError("PRIVATE_IP_BLOCKED", "The provided URL points to a blocked private IP.")
        addresses.append(address)
    if not addresses:
        raise UrlIngestSecurityError("DNS_RESOLUTION_FAILED", "The provided URL host could not be resolved.")
    return addresses


class UrlValidator:
    def validate_syntax(self, url: str) -> str:
        normalized = str(url or "").strip()
        if not normalized:
            raise UrlIngestSecurityError("INVALID_SCHEME", "The provided URL is not allowed.")
        if len(normalized) > 2048:
            raise UrlIngestSecurityError("INVALID_SCHEME", "The provided URL is not allowed.")
        parsed = urlparse(normalized)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise UrlIngestSecurityError("INVALID_SCHEME", "The provided URL scheme is not allowed.")
        if not parsed.hostname:
            raise UrlIngestSecurityError("DNS_RESOLUTION_FAILED", "The provided URL host could not be resolved.")
        if parsed.username or parsed.password:
            raise UrlIngestSecurityError("USERINFO_NOT_ALLOWED", "The provided URL must not contain userinfo.")
        return normalized

    def resolve_public_host_or_raise(self, hostname: str) -> list[str]:
        return resolve_public_host_or_raise(hostname)

    def validate_target_details(self, url: str) -> UrlTarget:
        normalized = self.validate_syntax(url)
        parsed = urlparse(normalized)
        addresses = tuple(self.resolve_public_host_or_raise(str(parsed.hostname or "")))
        return UrlTarget(url=normalized, parsed=parsed, addresses=addresses)

    def assert_dns_still_matches(self, target: UrlTarget) -> None:
        current_addresses = tuple(self.resolve_public_host_or_raise(str(target.parsed.hostname or "")))
        if set(current_addresses) != set(target.addresses):
            raise UrlIngestSecurityError("DNS_REBINDING_DETECTED", "The URL host DNS mapping changed during validation.")


class RedirectPolicy:
    def response_location(self, response: requests.Response, current_url: str) -> str | None:
        location = response.headers.get("location")
        if not location:
            return None
        return urljoin(current_url, location)

    def next_target(self, response: requests.Response, current_target: UrlTarget) -> UrlTarget:
        next_url = self.response_location(response, current_target.url)
        if not next_url:
            raise UrlIngestSecurityError("REDIRECT_LIMIT_EXCEEDED", "The URL redirect target is invalid.")
        next_target = _validate_url_target_details(next_url)
        if current_target.parsed.scheme.lower() == "https" and next_target.parsed.scheme.lower() == "http":
            raise UrlIngestSecurityError("REDIRECT_DOWNGRADE_BLOCKED", "HTTPS to HTTP redirect is not allowed.")
        return next_target

    def assert_can_follow(self, *, redirect_count: int) -> None:
        if redirect_count >= max_url_redirects():
            raise UrlIngestSecurityError("REDIRECT_LIMIT_EXCEEDED", "Redirect limit exceeded.")

    def assert_not_loop(self, *, current_url: str, visited: set[str]) -> None:
        if current_url in visited:
            raise UrlIngestSecurityError("REDIRECT_LIMIT_EXCEEDED", "Redirect loop detected.")


class UrlContentPolicy:
    def is_allowed_content_type(self, content_type: str | None) -> bool:
        normalized = str(content_type or "").split(";", 1)[0].strip().lower()
        if not normalized:
            return False
        return any(
            normalized == allowed or normalized.endswith("+xml") and allowed in {"application/xml", "text/xml"}
            for allowed in allowed_content_types()
        )

    def looks_like_allowed_text_payload(self, chunk: bytes) -> bool:
        sample = bytes(chunk or b"")[:512].lstrip()
        if not sample:
            return False
        lowered = sample[:64].lower()
        if lowered.startswith((b"<!doctype html", b"<html", b"<?xml", b"{", b"[")):
            return True
        if b"\x00" in sample:
            return False
        printable = sum(1 for byte in sample if byte in {9, 10, 13} or 32 <= byte <= 126 or byte >= 128)
        return printable / max(len(sample), 1) >= 0.90

    def validate_declared_content_length(self, response: requests.Response) -> None:
        raw_length = response.headers.get("content-length")
        if not raw_length:
            return
        try:
            declared_length = int(str(raw_length).strip())
        except ValueError as exc:
            raise UrlIngestSecurityError("CONTENT_LENGTH_TOO_LARGE", "The URL response size header is invalid.") from exc
        if declared_length > max_url_response_bytes():
            raise UrlIngestSecurityError("CONTENT_LENGTH_TOO_LARGE", "The URL response is too large.")

    def assert_streaming_size(self, total_bytes: int) -> None:
        if total_bytes > max_url_response_bytes():
            raise UrlIngestSecurityError("RESPONSE_TOO_LARGE", "The URL response body is too large.")


def resolve_public_host_or_raise(hostname: str) -> list[str]:
    return _resolve_public_host(hostname)


def _validate_url_target_details(url: str) -> UrlTarget:
    return UrlValidator().validate_target_details(url)


def validate_url_target(url: str) -> str:
    return _validate_url_target_details(url).url


def is_allowed_content_type(content_type: str | None) -> bool:
    return UrlContentPolicy().is_allowed_content_type(content_type)


def _looks_like_allowed_text_payload(chunk: bytes) -> bool:
    return UrlContentPolicy().looks_like_allowed_text_payload(chunk)


def _validate_declared_content_length(response: requests.Response) -> None:
    UrlContentPolicy().validate_declared_content_length(response)


def _response_location(response: requests.Response, current_url: str) -> str | None:
    return RedirectPolicy().response_location(response, current_url)


def _assert_dns_still_matches(target: UrlTarget) -> None:
    UrlValidator().assert_dns_still_matches(target)


def _request_once(session: requests.Session, *, method: str, target: UrlTarget, stream: bool, timeout: int) -> requests.Response:
    _assert_dns_still_matches(target)
    try:
        return session.request(
            method,
            target.url,
            allow_redirects=False,
            headers=_REQUEST_HEADERS,
            stream=stream,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise UrlIngestSecurityError("DOWNLOAD_TIMEOUT", "The URL download timed out.") from exc
    except requests.RequestException as exc:
        raise UrlIngestSecurityError("DNS_RESOLUTION_FAILED", "The provided URL host could not be resolved.") from exc


def _next_redirect_target(response: requests.Response, current_target: UrlTarget) -> UrlTarget:
    return RedirectPolicy().next_target(response, current_target)


def request_url_head(url: str, *, timeout: int = 15) -> UrlFetchResult:
    current_target = _validate_url_target_details(url)
    session = requests.Session()
    visited: set[str] = set()
    redirect_count = 0
    redirect_policy = RedirectPolicy()
    content_policy = UrlContentPolicy()
    while True:
        redirect_policy.assert_not_loop(current_url=current_target.url, visited=visited)
        visited.add(current_target.url)
        response = _request_once(session, method="HEAD", target=current_target, stream=False, timeout=timeout)
        if response.is_redirect or response.is_permanent_redirect:
            redirect_policy.assert_can_follow(redirect_count=redirect_count)
            redirect_count += 1
            current_target = redirect_policy.next_target(response, current_target)
            continue
        content_type = response.headers.get("content-type") or ""
        if response.status_code < 400 and content_type and not content_policy.is_allowed_content_type(content_type):
            raise UrlIngestSecurityError("CONTENT_TYPE_NOT_ALLOWED", "The URL content type is not allowed.")
        if response.status_code < 400:
            content_policy.validate_declared_content_length(response)
        return UrlFetchResult(
            url=url,
            final_url=current_target.url,
            status_code=int(response.status_code),
            content_type=content_type,
        )


def get_url_text(url: str, *, timeout: int = 20) -> UrlFetchResult:
    current_target = _validate_url_target_details(url)
    session = requests.Session()
    visited: set[str] = set()
    redirect_count = 0
    redirect_policy = RedirectPolicy()
    content_policy = UrlContentPolicy()
    while True:
        redirect_policy.assert_not_loop(current_url=current_target.url, visited=visited)
        visited.add(current_target.url)
        response = _request_once(session, method="GET", target=current_target, stream=True, timeout=timeout)
        if response.is_redirect or response.is_permanent_redirect:
            redirect_policy.assert_can_follow(redirect_count=redirect_count)
            redirect_count += 1
            current_target = redirect_policy.next_target(response, current_target)
            continue
        response.raise_for_status()
        content_type = response.headers.get("content-type") or ""
        content_type_allowed = content_policy.is_allowed_content_type(content_type)
        content_policy.validate_declared_content_length(response)
        if content_type and not content_type_allowed:
            raise UrlIngestSecurityError("CONTENT_TYPE_NOT_ALLOWED", "The URL content type is not allowed.")
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            if not chunks and not content_type and not content_policy.looks_like_allowed_text_payload(chunk):
                raise UrlIngestSecurityError("CONTENT_TYPE_NOT_ALLOWED", "The URL content type is not allowed.")
            total += len(chunk)
            content_policy.assert_streaming_size(total)
            chunks.append(chunk)
        return UrlFetchResult(
            url=url,
            final_url=current_target.url,
            status_code=int(response.status_code),
            content_type=content_type,
            body=b"".join(chunks),
        )


__all__ = [
    "RedirectPolicy",
    "UrlContentPolicy",
    "UrlFetchResult",
    "UrlIngestError",
    "UrlIngestRejected",
    "UrlIngestSecurityError",
    "UrlTarget",
    "UrlValidator",
    "get_url_text",
    "request_url_head",
    "validate_url_target",
]
