from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

from apps.knowledge.service import url_ingest_security as security

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _Response:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"hello",
        chunks: list[bytes] | None = None,
        redirect: bool = False,
    ) -> None:
        self.status_code = status_code
        self.headers = {"content-type": "text/plain"} if headers is None else headers
        self._body = body
        self._chunks = chunks
        self.is_redirect = redirect
        self.is_permanent_redirect = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def iter_content(self, chunk_size: int):  # type: ignore[no-untyped-def]
        if self._chunks is not None:
            yield from self._chunks
            return
        yield self._body


def test_invalid_scheme_returns_machine_code() -> None:
    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.validate_url_target("ftp://example.test/file.txt")
    assert exc.value.code == "INVALID_SCHEME"


def test_url_validator_rejects_userinfo_with_machine_code() -> None:
    validator = security.UrlValidator()

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        validator.validate_syntax("https://user:pass@example.test/page")

    assert exc.value.code == "USERINFO_NOT_ALLOWED"


def test_dns_resolution_failure_returns_machine_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken_getaddrinfo(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise socket.gaierror("dns failed")

    monkeypatch.setattr(security.socket, "getaddrinfo", _broken_getaddrinfo)
    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.validate_url_target("http://example.test")
    assert exc.value.code == "DNS_RESOLUTION_FAILED"


def test_download_timeout_returns_machine_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])

    class _Session:
        def request(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise security.requests.Timeout("slow")

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security._request_once(
            _Session(),  # type: ignore[arg-type]
            method="GET",
            target=security._validate_url_target_details("https://example.test/page"),
            stream=True,
            timeout=1,
        )
    assert exc.value.code == "DOWNLOAD_TIMEOUT"


@pytest.mark.parametrize(
    ("url", "host_ip"),
    [
        ("http://127.0.0.1", "127.0.0.1"),
        ("http://localhost", "127.0.0.1"),
        ("http://0.0.0.0", "0.0.0.0"),
        ("http://169.254.169.254", "169.254.169.254"),
        ("http://10.0.0.1", "10.0.0.1"),
        ("http://172.16.0.1", "172.16.0.1"),
        ("http://192.168.1.1", "192.168.1.1"),
        ("http://[::1]", "::1"),
    ],
)
def test_private_loopback_and_metadata_targets_are_rejected(monkeypatch: pytest.MonkeyPatch, url: str, host_ip: str) -> None:
    def _fake_getaddrinfo(hostname, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        family = socket.AF_INET6 if ":" in host_ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (host_ip, 80))]

    monkeypatch.setattr(security.socket, "getaddrinfo", _fake_getaddrinfo)

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.validate_url_target(url)
    assert exc.value.code == "PRIVATE_IP_BLOCKED"


def test_userinfo_smuggling_to_private_host_is_rejected() -> None:
    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.validate_url_target("http://example.com@127.0.0.1")
    assert exc.value.code == "USERINFO_NOT_ALLOWED"


def test_public_domain_redirecting_to_localhost_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def _resolve(hostname: str) -> list[str]:
        if hostname == "localhost":
            raise security.UrlIngestSecurityError("PRIVATE_IP_BLOCKED", "The provided URL points to a blocked private IP.")
        return ["93.184.216.34"]

    monkeypatch.setattr(security, "resolve_public_host_or_raise", _resolve)
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(status_code=302, headers={"location": "http://localhost/private"}, redirect=True),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://public-domain.test/page")
    assert exc.value.code == "PRIVATE_IP_BLOCKED"


def test_dns_rebinding_is_rejected_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = iter([["203.0.113.10"], ["203.0.113.11"]])
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: next(calls))

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("https://example.test/page")
    assert exc.value.code == "DNS_REBINDING_DETECTED"


def test_https_to_http_redirect_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(
            status_code=302,
            headers={"location": "http://example.test/plain"},
            redirect=True,
        ),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("https://example.test/page")
    assert exc.value.code == "REDIRECT_DOWNGRADE_BLOCKED"


def test_redirect_policy_blocks_https_to_http_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    policy = security.RedirectPolicy()
    current = security.UrlTarget(
        url="https://example.test/page",
        parsed=security.urlparse("https://example.test/page"),
        addresses=("203.0.113.10",),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        policy.next_target(
            _Response(status_code=302, headers={"location": "http://example.test/plain"}, redirect=True),
            current,
        )

    assert exc.value.code == "REDIRECT_DOWNGRADE_BLOCKED"


def test_redirect_loop_has_explicit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(status_code=302, headers={"location": "/page"}, redirect=True),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://example.test/page")
    assert exc.value.code == "REDIRECT_LIMIT_EXCEEDED"


def test_too_many_redirects_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(security, "settings", SimpleNamespace(knowledge_url_ingest_max_redirects=1))
    locations = iter(["/first", "/second"])
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(status_code=302, headers={"location": next(locations)}, redirect=True),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://example.test/page")
    assert exc.value.code == "REDIRECT_LIMIT_EXCEEDED"


def test_disallowed_content_type_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(headers={"content-type": "application/octet-stream"}, body=b"binary"),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://example.test/page")
    assert exc.value.code == "CONTENT_TYPE_NOT_ALLOWED"


def test_declared_content_length_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(security, "settings", SimpleNamespace(knowledge_url_ingest_max_response_bytes=1024))
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(headers={"content-type": "text/plain", "content-length": "2048"}),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://example.test/page")
    assert exc.value.code == "CONTENT_LENGTH_TOO_LARGE"


def test_url_content_policy_rejects_large_declared_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "settings", SimpleNamespace(knowledge_url_ingest_max_response_bytes=1024))
    policy = security.UrlContentPolicy()

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        policy.validate_declared_content_length(
            _Response(headers={"content-type": "text/plain", "content-length": "2048"}),
        )

    assert exc.value.code == "CONTENT_LENGTH_TOO_LARGE"


def test_url_content_policy_rejects_streaming_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "settings", SimpleNamespace(knowledge_url_ingest_max_response_bytes=1024))
    policy = security.UrlContentPolicy()

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        policy.assert_streaming_size(1200)

    assert exc.value.code == "RESPONSE_TOO_LARGE"


def test_chunked_response_over_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(security, "settings", SimpleNamespace(knowledge_url_ingest_max_response_bytes=1024))
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(
            headers={"content-type": "text/plain"},
            chunks=[b"a" * 600, b"b" * 600],
        ),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://example.test/page")
    assert exc.value.code == "RESPONSE_TOO_LARGE"


def test_decompressed_gzip_bomb_over_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(security, "settings", SimpleNamespace(knowledge_url_ingest_max_response_bytes=1024))
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(
            headers={"content-type": "text/plain", "content-encoding": "gzip"},
            chunks=[b"x" * 2048],
        ),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://example.test/page")
    assert exc.value.code == "RESPONSE_TOO_LARGE"


def test_missing_content_type_requires_text_like_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security, "resolve_public_host_or_raise", lambda hostname: ["203.0.113.10"])
    monkeypatch.setattr(
        security,
        "_request_once",
        lambda *args, **kwargs: _Response(headers={}, body=b"\x00\x01\x02binary"),
    )

    with pytest.raises(security.UrlIngestSecurityError) as exc:
        security.get_url_text("http://example.test/page")
    assert exc.value.code == "CONTENT_TYPE_NOT_ALLOWED"
