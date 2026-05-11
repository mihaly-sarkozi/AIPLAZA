from __future__ import annotations

import io
from dataclasses import dataclass
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from apps.knowledge.api import router as knowledge_api_router

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass(frozen=True)
class _TenantConfig:
    package: str
    feature_flags: dict[str, bool]


@dataclass(frozen=True)
class _Tenant:
    config: _TenantConfig


def _upload(filename: str, body: bytes, content_type: str) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(body), headers={"content-type": content_type})


def test_resolve_ingest_upload_policy_demo() -> None:
    tenant = _Tenant(config=_TenantConfig(package="free", feature_flags={"demo_mode": True}))

    policy = knowledge_api_router._resolve_ingest_upload_policy(tenant)

    assert policy.profile == "demo"
    assert policy.max_files == 3
    assert policy.max_file_bytes == 5 * 1024 * 1024
    assert policy.max_total_bytes == 15 * 1024 * 1024
    assert policy.max_training_chars == 100_000


def test_validate_upload_type_rejects_mime_extension_mismatch() -> None:
    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._validate_upload_type("document.pdf", "text/plain")

    assert exc.value.status_code == 415
    assert "not allowed" in str(exc.value.detail)


@pytest.mark.anyio
async def test_read_upload_limited_rejects_oversized_file() -> None:
    upload = _upload("big.txt", b"a" * 6, "text/plain")

    with pytest.raises(HTTPException) as exc:
        await knowledge_api_router._read_upload_limited(upload, max_bytes=5)

    assert exc.value.status_code == 413


def test_assert_file_count_uses_policy_limit() -> None:
    policy = knowledge_api_router.IngestUploadPolicy(
        profile="demo",
        max_files=1,
        max_file_bytes=10,
        max_total_bytes=10,
        max_training_chars=100,
    )
    files = [
        _upload("one.txt", b"a", "text/plain"),
        _upload("two.txt", b"b", "text/plain"),
    ]

    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._assert_file_count(files, policy=policy)

    assert exc.value.status_code == 413


def test_validate_upload_magic_type_rejects_fake_pdf() -> None:
    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._validate_upload_magic_type("fake.pdf", b"not-a-pdf")

    assert exc.value.status_code == 415


def test_validate_upload_magic_type_accepts_docx_zip_structure() -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    payload = buffer.getvalue()

    knowledge_api_router._validate_upload_magic_type("ok.docx", payload)


def test_docx_zip_guard_rejects_suspicious_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.app_settings, "upload_docx_max_compression_ratio", 2.0, raising=False)
    huge_text = "A" * 200_000
    buffer = io.BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", huge_text)
    payload = buffer.getvalue()

    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._validate_upload_magic_type("bomb.docx", payload)

    assert exc.value.status_code == 415


def test_guard_pdf_limits_rejects_over_page_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.app_settings, "upload_pdf_max_pages", 2, raising=False)
    raw = b"%PDF-1.7\n/Type /Page\n/Type /Page\n/Type /Page\n"

    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._guard_pdf_limits("sample.pdf", raw)

    assert exc.value.status_code == 413
