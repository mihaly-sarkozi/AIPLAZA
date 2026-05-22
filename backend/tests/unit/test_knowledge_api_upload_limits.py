from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from apps.knowledge.api import file_ingest_use_cases
from apps.knowledge.api.file_ingest_use_cases import FileIngestEstimateCommand, FileIngestUseCase
from apps.knowledge.api import router as knowledge_api_router
from apps.knowledge.api import upload_support
from apps.knowledge.service.source_storage_service import SourceStorageService
from shared.object_storage.models import StoredObjectRef

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

    @property
    def slug(self) -> str:
        return "tenant-a"


class _ObjectStorage:
    def build_key(self, *parts: str) -> str:
        return "/".join(parts)

    def put_bytes(self, *, key: str, content: bytes, bucket: str | None = None, content_type: str | None = None, metadata=None):
        return StoredObjectRef(
            provider="memory",
            bucket=bucket or "default",
            key=key,
            size_bytes=len(content),
            content_type=content_type,
            metadata=dict(metadata or {}),
        )


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


def test_validate_upload_type_accepts_allowed_pdf_docx_and_txt() -> None:
    knowledge_api_router._validate_upload_type("document.pdf", "application/pdf")
    knowledge_api_router._validate_upload_type(
        "document.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    knowledge_api_router._validate_upload_type("notes.txt", "text/plain")


def test_validate_upload_type_rejects_bad_extension() -> None:
    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._validate_upload_type("payload.exe", "application/octet-stream")

    assert exc.value.status_code == 415


def test_upload_request_validator_rejects_bad_extension() -> None:
    validator = upload_support.UploadRequestValidator()

    with pytest.raises(HTTPException) as exc:
        validator.validate_type("payload.exe", "application/octet-stream")

    assert exc.value.status_code == 415


@pytest.mark.anyio
async def test_read_upload_limited_rejects_oversized_file() -> None:
    upload = _upload("big.txt", b"a" * 6, "text/plain")

    with pytest.raises(HTTPException) as exc:
        await knowledge_api_router._read_upload_limited(upload, max_bytes=5)

    assert exc.value.status_code == 413


def test_assert_file_count_uses_policy_limit() -> None:
    policy = upload_support.IngestUploadPolicy(
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


def test_file_sniffer_rejects_magic_mismatch() -> None:
    sniffer = upload_support.FileSniffer()

    with pytest.raises(HTTPException) as exc:
        sniffer.validate_magic_type("fake.pdf", b"not-a-pdf")

    assert exc.value.status_code == 415


def test_validate_upload_magic_type_rejects_fake_txt_with_nul_bytes() -> None:
    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._validate_upload_magic_type("fake.txt", b"hello\x00world")

    assert exc.value.status_code == 415


def test_validate_upload_magic_type_accepts_docx_zip_structure() -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    payload = buffer.getvalue()

    knowledge_api_router._validate_upload_magic_type("ok.docx", payload)


def test_docx_zip_guard_rejects_suspicious_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.settings, "upload_docx_max_compression_ratio", 2.0, raising=False)
    huge_text = "A" * 200_000
    buffer = io.BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", huge_text)
    payload = buffer.getvalue()

    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._validate_upload_magic_type("bomb.docx", payload)

    assert exc.value.status_code == 415


def test_archive_guard_rejects_docx_zip_bomb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.settings, "upload_docx_max_compression_ratio", 2.0, raising=False)
    buffer = io.BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "A" * 200_000)

    with pytest.raises(upload_support.UploadSecurityError):
        upload_support.ArchiveGuard().inspect_docx_bytes_or_raise(buffer.getvalue())


def test_guard_pdf_limits_rejects_over_page_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.settings, "upload_pdf_max_pages", 2, raising=False)
    raw = b"%PDF-1.7\n/Type /Page\n/Type /Page\n/Type /Page\n"

    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._guard_pdf_limits("sample.pdf", raw)

    assert exc.value.status_code == 413


def test_pdf_guard_rejects_too_many_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.settings, "upload_pdf_max_pages", 1, raising=False)

    with pytest.raises(HTTPException) as exc:
        upload_support.PdfGuard().guard_pdf_limits("sample.pdf", b"%PDF-1.7\n/Type /Page\n/Type /Page\n")

    assert exc.value.status_code == 413


def test_scan_upload_rejects_malware_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upload_support.settings, "upload_malware_scan_provider", "clamav", raising=False)
    monkeypatch.setattr(upload_support, "get_app_env", lambda: "local")
    monkeypatch.setattr(upload_support, "scan_with_clamav", lambda raw: (False, "Eicar-Test-Signature FOUND"))
    monkeypatch.setattr(upload_support.logger, "warning", lambda *args, **kwargs: None)

    with pytest.raises(HTTPException) as exc:
        knowledge_api_router._scan_upload_or_raise(filename="bad.txt", raw=b"virus")

    assert exc.value.status_code == 415


def test_malware_scanner_fail_rejects_in_production_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upload_support.settings, "upload_malware_scan_provider", "clamav", raising=False)
    monkeypatch.setattr(upload_support.settings, "upload_malware_scan_required_in_prod", True, raising=False)
    monkeypatch.setattr(upload_support, "get_app_env", lambda: "production")
    monkeypatch.setattr(upload_support, "scan_with_clamav", lambda raw: (_ for _ in ()).throw(RuntimeError("down")))

    with pytest.raises(HTTPException) as exc:
        upload_support.FileSecurityScanner().scan_bytes_or_raise(filename="file.txt", raw=b"hello")

    assert exc.value.status_code == 503


@pytest.mark.anyio
async def test_stream_upload_to_spooled_file_accepts_txt_and_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.settings, "upload_malware_scan_provider", "none", raising=False)
    upload = _upload("ok.txt", b"hello world", "text/plain")

    streamed = await knowledge_api_router._stream_upload_to_spooled_file(upload, max_bytes=1024)

    assert streamed.filename == "ok.txt"
    assert streamed.size_bytes == len(b"hello world")
    assert streamed.checksum_sha256
    assert streamed.fileobj.read() == b"hello world"
    streamed.fileobj.close()


@pytest.mark.anyio
async def test_stream_upload_to_spooled_file_rejects_pdf_with_too_many_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.settings, "upload_malware_scan_provider", "none", raising=False)
    monkeypatch.setattr(knowledge_api_router.settings, "upload_pdf_max_pages", 1, raising=False)
    upload = _upload("too-many.pdf", b"%PDF-1.7\n/Type /Page\n/Type /Page\n", "application/pdf")

    with pytest.raises(HTTPException) as exc:
        await knowledge_api_router._stream_upload_to_spooled_file(upload, max_bytes=1024)

    assert exc.value.status_code == 413


def test_same_upload_bytes_produce_same_hash_for_deduplication() -> None:
    first = hashlib.sha256(b"same content").hexdigest()
    second = hashlib.sha256(b"same content").hexdigest()

    assert first == second


def test_source_storage_rejects_duplicate_content_hash_in_batch() -> None:
    service = SourceStorageService(_ObjectStorage())
    seen = set()
    checksum = hashlib.sha256(b"same content").hexdigest()

    service.store_uploaded_source(
        tenant="tenant-a",
        corpus_uuid="kb-1",
        run_id="run-1",
        item_id="item-1",
        filename="one.txt",
        mime_type="text/plain",
        content=b"same content",
        checksum_sha256=checksum,
        seen_content_hashes=seen,
    )
    with pytest.raises(ValueError, match="Duplicate content hash"):
        service.store_uploaded_source(
            tenant="tenant-a",
            corpus_uuid="kb-1",
            run_id="run-1",
            item_id="item-2",
            filename="two.txt",
            mime_type="text/plain",
            content=b"same content",
            checksum_sha256=checksum,
            seen_content_hashes=seen,
        )


@pytest.mark.anyio
async def test_file_ingest_use_case_estimate_builds_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api_router.settings, "upload_malware_scan_provider", "none", raising=False)
    monkeypatch.setattr(file_ingest_use_cases, "training_quota_status", lambda tenant, *, char_count: (True, None))
    tenant = _Tenant(config=_TenantConfig(package="starter", feature_flags={}))

    response = await FileIngestUseCase().estimate(
        FileIngestEstimateCommand(
            tenant=tenant,
            files=[_upload("ok.txt", b"hello world", "text/plain")],
        )
    )

    assert response["file_count"] == 1
    assert response["total_storage_bytes"] == len(b"hello world")
    assert response["can_start"] is True


def test_extracted_text_validator_rejects_empty_parser_output() -> None:
    validator = upload_support.ExtractedTextValidator()

    with pytest.raises(HTTPException) as exc:
        validator.validate("   ")

    assert exc.value.status_code == 400


def test_extracted_text_validator_rejects_too_large_output() -> None:
    with pytest.raises(HTTPException) as exc:
        upload_support.ExtractedTextValidator(max_chars=5).validate("too long")

    assert exc.value.status_code == 413
