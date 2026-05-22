from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.knowledge.service import url_fetch_service
from apps.knowledge.service.url_fetch_service import UrlFetchService
from apps.knowledge.service.url_ingest_security import UrlIngestSecurityError

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_fetch_document_strips_html_and_preserves_fetch_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        url_fetch_service,
        "get_url_text",
        lambda url, timeout=20: SimpleNamespace(
            body=b"<html><script>bad()</script><style>.x{}</style><body>Hello <b>world</b></body></html>",
            final_url="https://example.test/final",
            status_code=200,
            content_type="text/html",
        ),
    )
    service = UrlFetchService(text_normalizer=lambda value: " ".join(str(value or "").split()))

    result = service.fetch_document("https://example.test/page")

    assert result.text_content == "Hello world"
    assert result.paragraphs[0].text == "Hello world"
    assert result.metadata["final_url"] == "https://example.test/final"
    assert result.metadata["url_content_type"] == "text/html"


def test_request_head_wraps_unreachable_status_as_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        url_fetch_service,
        "request_url_head",
        lambda url, timeout=15: SimpleNamespace(status_code=404, content_type="text/plain", final_url=url),
    )
    service = UrlFetchService(text_normalizer=lambda value: str(value or ""))

    with pytest.raises(ValueError, match="404"):
        service.request_head("https://example.test/missing")


def test_validate_target_preserves_machine_readable_error_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        url_fetch_service,
        "validate_url_target",
        lambda _url: (_ for _ in ()).throw(UrlIngestSecurityError("INVALID_SCHEME", "The provided URL scheme is not allowed.")),
    )
    service = UrlFetchService(text_normalizer=lambda value: str(value or ""))

    with pytest.raises(UrlIngestSecurityError) as exc:
        service.validate_target("ftp://example.test/file.txt")
    assert exc.value.code == "INVALID_SCHEME"
