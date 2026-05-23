# backend/apps/knowledge/api/upload_support.py
# Feladat: Knowledge ingest feltöltések request oldali biztonsági és kvóta segédeit tartalmazza. MIME/magic sniffinget, DOCX/PDF alap guardokat, malware scan hívást, upload méretkorlátokat, hashinget és training usage kvóta kezelést választ le az API routerről; a nehéz text extraction worker oldali feladat. Program-specifikus knowledge upload support réteg.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import unescape
import io
import logging
import multiprocessing
import os
import pickle
import re
import resource
import tempfile
from typing import Any, BinaryIO
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile

from core.kernel.config.config_loader import get_app_env, settings
from core.kernel.config.environment import is_production_env
from core.kernel.deps.facade import get_login_service, get_service
from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE
from apps.knowledge.api.upload_malware_scanner import (
    FileSecurityScanner as _BaseFileSecurityScanner,
    scan_file_with_clamav,
    scan_with_clamav,
)
from shared.documents.text_extraction import extract_text_from_upload

logger = logging.getLogger(__name__)

UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
DEFAULT_ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}
GENERIC_ALLOWED_MIME = {"application/octet-stream"}
ALLOWED_MIME_BY_EXT: dict[str, set[str]] = {
    ".txt": {"text/plain"},
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
}


class UploadSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class IngestUploadPolicy:
    profile: str
    max_files: int
    max_file_bytes: int
    max_total_bytes: int
    max_training_chars: int | None


@dataclass(frozen=True)
class StreamedUpload:
    filename: str
    content_type: str
    fileobj: BinaryIO
    size_bytes: int
    checksum_sha256: str
    estimated_char_count: int


class FileSecurityScanner(_BaseFileSecurityScanner):
    def scan_bytes_or_raise(self, *, filename: str, raw: bytes) -> None:
        return _scan_bytes_with_compat_hooks(filename=filename, raw=raw)

    def scan_file_or_raise(self, *, filename: str, fileobj: BinaryIO) -> None:
        return _scan_file_with_compat_hooks(filename=filename, fileobj=fileobj)


def _scan_bytes_with_compat_hooks(*, filename: str, raw: bytes) -> None:
    provider = str(getattr(settings, "upload_malware_scan_provider", "none") or "none").strip().lower()
    required_prod = bool(getattr(settings, "upload_malware_scan_required_in_prod", True))
    try:
        env = get_app_env()
    except (RuntimeError, ValueError):
        env = "dev"
    if provider == "none":
        if is_production_env(env) and required_prod:
            raise HTTPException(status_code=503, detail="Malware scan service unavailable for upload.")
        return
    if provider != "clamav":
        raise HTTPException(status_code=503, detail="Unsupported malware scan provider.")
    try:
        clean, engine_message = scan_with_clamav(raw)
    except (OSError, TimeoutError, RuntimeError) as exc:
        if is_production_env(env) and required_prod:
            raise HTTPException(status_code=503, detail="Malware scan service unavailable for upload.") from exc
        logger.warning("Malware scan failed, continuing in non-prod mode.", extra={"error_type": type(exc).__name__})
        return
    if not clean:
        logger.warning("Upload rejected by malware scanner.", extra={"filename": filename, "engine": engine_message})
        raise HTTPException(status_code=415, detail="Upload rejected by malware scan policy.")


def _scan_file_with_compat_hooks(*, filename: str, fileobj: BinaryIO) -> None:
    provider = str(getattr(settings, "upload_malware_scan_provider", "none") or "none").strip().lower()
    required_prod = bool(getattr(settings, "upload_malware_scan_required_in_prod", True))
    try:
        env = get_app_env()
    except (RuntimeError, ValueError):
        env = "dev"
    if provider == "none":
        if is_production_env(env) and required_prod:
            raise HTTPException(status_code=503, detail="Malware scan service unavailable for upload.")
        return
    if provider != "clamav":
        raise HTTPException(status_code=503, detail="Unsupported malware scan provider.")
    try:
        clean, engine_message = scan_file_with_clamav(fileobj)
    except (OSError, TimeoutError, RuntimeError) as exc:
        if is_production_env(env) and required_prod:
            raise HTTPException(status_code=503, detail="Malware scan service unavailable for upload.") from exc
        logger.warning("Malware scan failed, continuing in non-prod mode.", extra={"error_type": type(exc).__name__})
        return
    if not clean:
        logger.warning("Upload rejected by malware scanner.", extra={"filename": filename, "engine": engine_message})
        raise HTTPException(status_code=415, detail="Upload rejected by malware scan policy.")


class UploadRequestValidator:
    def extension_from_filename(self, filename: str) -> str:
        name = str(filename or "").strip().lower()
        if "." not in name:
            return ""
        return f".{name.rsplit('.', 1)[1]}"

    def validate_type(self, filename: str, mime_type: str | None) -> None:
        ext = self.extension_from_filename(filename)
        if ext not in DEFAULT_ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Unsupported file extension. Allowed: .txt, .pdf, .docx")
        normalized_mime = str(mime_type or "").strip().lower()
        if not normalized_mime:
            return
        allowed_for_ext = ALLOWED_MIME_BY_EXT.get(ext, set())
        if normalized_mime in allowed_for_ext or normalized_mime in GENERIC_ALLOWED_MIME:
            return
        raise HTTPException(status_code=415, detail=f"MIME type '{normalized_mime}' is not allowed for '{ext}'")

    def assert_file_count(self, files: list[UploadFile], *, policy: IngestUploadPolicy) -> None:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided.")
        if len(files) > policy.max_files:
            raise HTTPException(
                status_code=413,
                detail=f"Too many files in one upload for '{policy.profile}' plan. Max: {policy.max_files}.",
            )

    def assert_file_size(self, total_bytes: int, *, max_bytes: int) -> None:
        if total_bytes > max_bytes:
            raise HTTPException(status_code=413, detail=f"File too large (max {max_bytes // (1024 * 1024)} MB).")

    def assert_total_storage_limit(self, total_bytes: int, *, policy: IngestUploadPolicy) -> None:
        if total_bytes > policy.max_total_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload size exceeds limit for '{policy.profile}' plan ({policy.max_total_bytes // (1024 * 1024)} MB).",
            )

    def assert_training_char_limit(self, total_chars: int, *, policy: IngestUploadPolicy) -> None:
        if policy.max_training_chars is None:
            return
        if total_chars > policy.max_training_chars:
            raise HTTPException(
                status_code=413,
                detail=f"Estimated training text too large for '{policy.profile}' plan. Max: {policy.max_training_chars} characters.",
            )


class FileSniffer:
    def sniff_magic_type(self, raw: bytes) -> str:
        if raw.startswith(b"%PDF-"):
            return "application/pdf"
        if raw.startswith(b"PK\x03\x04") or raw.startswith(b"PK\x05\x06") or raw.startswith(b"PK\x07\x08"):
            return "application/zip"
        if b"\x00" in raw[:4096]:
            return "application/octet-stream"
        try:
            raw[:8192].decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            return "application/octet-stream"

    def validate_magic_sample(self, filename: str, sample: bytes) -> None:
        if not bool(getattr(settings, "upload_magic_sniff_enabled", True)):
            return
        ext = extension_from_filename(filename)
        magic_type = self.sniff_magic_type(sample)
        if ext == ".pdf" and magic_type != "application/pdf":
            raise HTTPException(status_code=415, detail="Uploaded file content does not match PDF format.")
        if ext == ".txt" and magic_type not in {"text/plain"}:
            raise HTTPException(status_code=415, detail="Uploaded file content does not match text format.")
        if ext == ".docx" and magic_type != "application/zip":
            raise HTTPException(status_code=415, detail="Uploaded file content does not match DOCX format.")

    def validate_magic_type(self, filename: str, raw: bytes) -> None:
        self.validate_magic_sample(filename, raw)
        if extension_from_filename(filename) == ".docx":
            ArchiveGuard().inspect_docx_bytes_or_raise(raw)


class ArchiveGuard:
    def inspect_docx_bytes_or_raise(self, raw: bytes) -> dict[str, Any]:
        max_entries = max(1, int(getattr(settings, "upload_docx_max_zip_entries", 5000) or 5000))
        max_decompressed = max(1, int(getattr(settings, "upload_docx_max_decompressed_bytes", 30 * 1024 * 1024) or (30 * 1024 * 1024)))
        max_ratio = float(getattr(settings, "upload_docx_max_compression_ratio", 120.0) or 120.0)
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                return self._inspect_zip_or_raise(archive, max_entries=max_entries, max_decompressed=max_decompressed, max_ratio=max_ratio)
        except BadZipFile as exc:
            raise UploadSecurityError("Invalid DOCX archive.") from exc

    def inspect_docx_file_or_raise(self, fileobj: BinaryIO) -> dict[str, Any]:
        max_entries = max(1, int(getattr(settings, "upload_docx_max_zip_entries", 5000) or 5000))
        max_decompressed = max(1, int(getattr(settings, "upload_docx_max_decompressed_bytes", 30 * 1024 * 1024) or (30 * 1024 * 1024)))
        max_ratio = float(getattr(settings, "upload_docx_max_compression_ratio", 120.0) or 120.0)
        try:
            fileobj.seek(0)
            with ZipFile(fileobj) as archive:
                return self._inspect_zip_or_raise(archive, max_entries=max_entries, max_decompressed=max_decompressed, max_ratio=max_ratio)
        except BadZipFile as exc:
            raise UploadSecurityError("Invalid DOCX archive.") from exc
        finally:
            fileobj.seek(0)

    def guard_docx_file_limits(self, filename: str, fileobj: BinaryIO) -> None:
        if not (filename or "").lower().endswith(".docx"):
            return
        try:
            self.inspect_docx_file_or_raise(fileobj)
        except UploadSecurityError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc

    def _inspect_zip_or_raise(self, archive: ZipFile, *, max_entries: int, max_decompressed: int, max_ratio: float) -> dict[str, Any]:
        infos = archive.infolist()
        if len(infos) > max_entries:
            raise UploadSecurityError("DOCX archive too complex (too many entries).")
        total_uncompressed = 0
        total_compressed = 0
        has_word_document = False
        has_content_types = False
        for info in infos:
            total_uncompressed += int(info.file_size or 0)
            total_compressed += int(info.compress_size or 0)
            filename = str(info.filename or "")
            if filename == "[Content_Types].xml":
                has_content_types = True
            if filename == "word/document.xml":
                has_word_document = True
            if total_uncompressed > max_decompressed:
                raise UploadSecurityError("DOCX uncompressed size exceeds allowed limit.")
        compressed_baseline = max(1, total_compressed)
        ratio = float(total_uncompressed) / float(compressed_baseline)
        if ratio > max_ratio:
            raise UploadSecurityError("DOCX compression ratio is suspiciously high.")
        if not (has_word_document and has_content_types):
            raise UploadSecurityError("DOCX archive structure invalid.")
        return {
            "entries": len(infos),
            "total_uncompressed": total_uncompressed,
            "total_compressed": total_compressed,
            "ratio": ratio,
        }


class PdfGuard:
    def page_count_heuristic(self, raw: bytes) -> int:
        return max(0, int(raw.count(b"/Type /Page")))

    def guard_pdf_limits(self, filename: str, raw: bytes) -> int:
        if not (filename or "").lower().endswith(".pdf"):
            return 0
        estimated_pages = self.page_count_heuristic(raw)
        self.guard_pdf_page_count(filename, estimated_pages)
        return estimated_pages

    def guard_pdf_page_count(self, filename: str, estimated_pages: int) -> None:
        if not (filename or "").lower().endswith(".pdf"):
            return
        max_pages = max(1, int(getattr(settings, "upload_pdf_max_pages", 200) or 200))
        if int(estimated_pages) > max_pages:
            raise HTTPException(status_code=413, detail=f"PDF too large: page count exceeds limit ({max_pages}).")


class ExtractedTextValidator:
    def __init__(self, *, max_chars: int | None = None) -> None:
        self._max_chars = max_chars

    def validate(self, text: str | None) -> str:
        normalized = str(text or "")
        if not normalized.strip():
            raise HTTPException(status_code=400, detail="Extracted text is empty.")
        max_chars = max(1, int(self._max_chars or getattr(settings, "upload_parser_max_extracted_text_chars", 2_000_000) or 2_000_000))
        if len(normalized) > max_chars:
            raise HTTPException(status_code=413, detail="Extracted text is too large.")
        return normalized


def tenant_plan_code(tenant: Any) -> str:
    config = getattr(tenant, "config", None)
    package = str(getattr(config, "package", "") or "").strip().lower()
    if package:
        return package
    return "free"


def is_demo_tenant(tenant: Any) -> bool:
    flags = getattr(getattr(tenant, "config", None), "feature_flags", None) or {}
    return bool(flags.get("demo_mode"))


def resolve_ingest_upload_policy(tenant: Any) -> IngestUploadPolicy:
    if is_demo_tenant(tenant):
        return IngestUploadPolicy(
            profile="demo",
            max_files=3,
            max_file_bytes=5 * 1024 * 1024,
            max_total_bytes=15 * 1024 * 1024,
            max_training_chars=100_000,
        )
    plan = tenant_plan_code(tenant)
    if plan == "starter":
        return IngestUploadPolicy(
            profile="starter",
            max_files=10,
            max_file_bytes=10 * 1024 * 1024,
            max_total_bytes=50 * 1024 * 1024,
            max_training_chars=None,
        )
    return IngestUploadPolicy(
        profile="pro",
        max_files=20,
        max_file_bytes=25 * 1024 * 1024,
        max_total_bytes=250 * 1024 * 1024,
        max_training_chars=None,
    )


def extension_from_filename(filename: str) -> str:
    return UploadRequestValidator().extension_from_filename(filename)


def validate_upload_type(filename: str, mime_type: str | None) -> None:
    UploadRequestValidator().validate_type(filename, mime_type)


def sniff_magic_type(raw: bytes) -> str:
    return FileSniffer().sniff_magic_type(raw)


def inspect_docx_zip_or_raise(raw: bytes) -> dict[str, Any]:
    return ArchiveGuard().inspect_docx_bytes_or_raise(raw)


def validate_upload_magic_type(filename: str, raw: bytes) -> None:
    try:
        FileSniffer().validate_magic_type(filename, raw)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc


def validate_upload_magic_sample(filename: str, sample: bytes) -> None:
    FileSniffer().validate_magic_sample(filename, sample)


def pdf_page_count_heuristic(raw: bytes) -> int:
    return PdfGuard().page_count_heuristic(raw)


def guard_pdf_limits(filename: str, raw: bytes) -> int:
    return PdfGuard().guard_pdf_limits(filename, raw)


def guard_pdf_page_count(filename: str, estimated_pages: int) -> None:
    PdfGuard().guard_pdf_page_count(filename, estimated_pages)


def inspect_docx_file_or_raise(fileobj: BinaryIO) -> dict[str, Any]:
    return ArchiveGuard().inspect_docx_file_or_raise(fileobj)


def guard_docx_file_limits(filename: str, fileobj: BinaryIO) -> None:
    ArchiveGuard().guard_docx_file_limits(filename, fileobj)


def scan_upload_or_raise(*, filename: str, raw: bytes) -> None:
    FileSecurityScanner().scan_bytes_or_raise(filename=filename, raw=raw)


def scan_file_or_raise(*, filename: str, fileobj: BinaryIO) -> None:
    FileSecurityScanner().scan_file_or_raise(filename=filename, fileobj=fileobj)


def _apply_parser_resource_limits(timeout_sec: int) -> None:
    memory_limit_mb = max(32, int(getattr(settings, "upload_parser_memory_limit_mb", 256) or 256))
    memory_limit_bytes = memory_limit_mb * 1024 * 1024
    for limit_name in ("RLIMIT_AS", "RLIMIT_DATA"):
        limit = getattr(resource, limit_name, None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, (memory_limit_bytes, memory_limit_bytes))
        except (OSError, ValueError):
            logger.warning("Parser resource memory limit could not be applied.", extra={"limit": limit_name})
    cpu_limit = max(1, timeout_sec + 1)
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    except (OSError, ValueError, AttributeError):
        logger.warning("Parser CPU limit could not be applied.")


def _write_parser_result(result_path: str, status: str, payload: str) -> None:
    with open(result_path, "wb") as result_file:
        pickle.dump((status, payload), result_file)


def _parser_worker(filename: str, raw: bytes, timeout_sec: int, result_path: str) -> None:
    try:
        if os.name == "posix":
            _apply_parser_resource_limits(timeout_sec)
        _write_parser_result(result_path, "ok", str(extract_text_from_upload(filename, raw) or ""))
    except ValueError as exc:
        _write_parser_result(result_path, "value_error", str(exc))
    except MemoryError:
        _write_parser_result(result_path, "resource_error", "Document parser memory limit exceeded.")
    except BaseException as exc:
        _write_parser_result(result_path, "error", str(exc) or exc.__class__.__name__)


def _parser_context() -> multiprocessing.context.BaseContext:
    if os.name == "posix":
        return multiprocessing.get_context("fork")
    return multiprocessing.get_context("spawn")


def extract_text_with_timeout(filename: str, raw: bytes) -> str:
    timeout_sec = max(1, int(getattr(settings, "upload_parser_timeout_sec", 20) or 20))
    ctx = _parser_context()
    result_path = ""
    try:
        with tempfile.NamedTemporaryFile(prefix="knowledge-parser-", suffix=".pkl", delete=False) as result_file:
            result_path = result_file.name
        process = ctx.Process(
            target=_parser_worker,
            args=(filename, raw, timeout_sec, result_path),
            daemon=True,
        )
        process.start()
        process.join(timeout_sec)
        if process.is_alive():
            process.terminate()
            process.join(2)
            if process.is_alive():
                process.kill()
                process.join(1)
            raise HTTPException(status_code=408, detail="Document parser timeout.")
        if not os.path.exists(result_path) or os.path.getsize(result_path) <= 0:
            raise HTTPException(status_code=400, detail="Document parser failed.")
        with open(result_path, "rb") as result_file:
            status, payload = pickle.load(result_file)
        if status == "ok":
            return ExtractedTextValidator().validate(str(payload or ""))
        if status == "value_error":
            raise HTTPException(status_code=400, detail=str(payload))
        if status == "resource_error":
            raise HTTPException(status_code=413, detail=str(payload))
        raise HTTPException(status_code=400, detail="Document parser failed.")
    finally:
        if result_path:
            try:
                os.unlink(result_path)
            except OSError:
                pass


async def read_upload_limited(upload: UploadFile, *, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail=f"File too large (max {max_bytes // (1024 * 1024)} MB).")
        chunks.append(chunk)
    return b"".join(chunks)


def estimate_training_chars_from_size(filename: str, *, size_bytes: int, sample: bytes) -> int:
    if size_bytes <= 0:
        return 0
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return int(size_bytes)
    if name.endswith(".pdf"):
        return max(1, int(round(size_bytes * 0.06)))
    if name.endswith(".docx"):
        return max(1, int(round(size_bytes * 0.20)))
    return max(1, int(round(size_bytes * 0.35)))


async def stream_upload_to_spooled_file(
    upload: UploadFile,
    *,
    max_bytes: int,
    spool_max_size: int | None = None,
) -> StreamedUpload:
    filename = upload.filename or "upload.bin"
    content_type = upload.content_type or "application/octet-stream"
    max_spool = max(1024 * 1024, int(spool_max_size or getattr(settings, "upload_spool_max_memory_bytes", 1024 * 1024) or (1024 * 1024)))
    sink = tempfile.SpooledTemporaryFile(max_size=max_spool, mode="w+b")
    digest = hashlib.sha256()
    total = 0
    sample = bytearray()
    estimated_pdf_pages = 0
    try:
        while True:
            chunk = await upload.read(UPLOAD_READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(status_code=413, detail=f"File too large (max {max_bytes // (1024 * 1024)} MB).")
            digest.update(chunk)
            sink.write(chunk)
            if len(sample) < 8192:
                sample.extend(chunk[: 8192 - len(sample)])
            if filename.lower().endswith(".pdf"):
                estimated_pdf_pages += pdf_page_count_heuristic(chunk)
        if total <= 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        sample_bytes = bytes(sample)
        validate_upload_magic_sample(filename, sample_bytes)
        guard_pdf_page_count(filename, estimated_pdf_pages)
        sink.seek(0)
        guard_docx_file_limits(filename, sink)
        scan_file_or_raise(filename=filename, fileobj=sink)
        sink.seek(0)
        return StreamedUpload(
            filename=filename,
            content_type=content_type,
            fileobj=sink,
            size_bytes=total,
            checksum_sha256=digest.hexdigest(),
            estimated_char_count=estimate_training_chars_from_size(filename, size_bytes=total, sample=sample_bytes),
        )
    except Exception:
        try:
            sink.close()
        except Exception:
            pass
        raise


def assert_file_count(files: list[UploadFile], *, policy: IngestUploadPolicy) -> None:
    UploadRequestValidator().assert_file_count(files, policy=policy)


def assert_total_storage_limit(total_bytes: int, *, policy: IngestUploadPolicy) -> None:
    UploadRequestValidator().assert_total_storage_limit(total_bytes, policy=policy)


def assert_training_char_limit(total_chars: int, *, policy: IngestUploadPolicy) -> None:
    UploadRequestValidator().assert_training_char_limit(total_chars, policy=policy)


def estimate_training_chars_for_file(filename: str, raw: bytes) -> int:
    if not raw:
        return 0
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return len(raw.decode("utf-8", errors="replace"))
    if name.endswith(".docx"):
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                text_parts: list[str] = []
                for member in archive.namelist():
                    if not member.startswith("word/") or not member.endswith(".xml"):
                        continue
                    xml = archive.read(member).decode("utf-8", errors="ignore")
                    text_parts.extend(unescape(value) for value in re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.DOTALL))
                joined = re.sub(r"\s+", " ", " ".join(text_parts)).strip()
                if joined:
                    return len(joined)
        except (BadZipFile, KeyError, OSError, UnicodeDecodeError):
            pass
    if name.endswith(".pdf"):
        return max(1, int(round(len(raw) * 0.06)))
    return max(1, int(round(len(raw) * 0.35)))


def count_training_chars_for_file(filename: str, raw: bytes) -> int:
    try:
        return len(extract_text_with_timeout(filename, raw))
    except HTTPException:
        return estimate_training_chars_for_file(filename, raw)


def training_quota_status(tenant: Any, *, char_count: int) -> tuple[bool, str | None]:
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    allowed, reason = usage_service.can_consume_training_chars(tenant, char_count)
    return bool(allowed), reason


def ensure_training_quota(tenant: Any, *, char_count: int) -> None:
    allowed, reason = training_quota_status(tenant, char_count=char_count)
    if not allowed:
        raise HTTPException(status_code=402, detail=reason or "Training quota exceeded")


def record_training_usage(tenant: Any, *, char_count: int, storage_bytes: int) -> None:
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    usage_service.record_training_ingest(
        tenant,
        char_count=max(0, int(char_count)),
        storage_bytes=max(0, int(storage_bytes)),
    )


def ensure_training_mfa(current_user: Any) -> None:
    if not bool(getattr(settings, "training_mfa_required", True)):
        return
    login_service = get_login_service()
    status = login_service.authenticator_status(int(getattr(current_user, "id", 0) or 0))
    if not bool(status.get("enabled")):
        raise HTTPException(
            status_code=403,
            detail="MFA kötelező a tanítási műveletekhez. Aktiváld az authenticator MFA-t.",
        )


__all__ = [
    "ArchiveGuard",
    "ExtractedTextValidator",
    "FileSecurityScanner",
    "FileSniffer",
    "IngestUploadPolicy",
    "PdfGuard",
    "StreamedUpload",
    "UploadRequestValidator",
    "UploadSecurityError",
    "assert_file_count",
    "assert_total_storage_limit",
    "assert_training_char_limit",
    "count_training_chars_for_file",
    "ensure_training_mfa",
    "ensure_training_quota",
    "estimate_training_chars_for_file",
    "extract_text_with_timeout",
    "guard_pdf_limits",
    "read_upload_limited",
    "record_training_usage",
    "resolve_ingest_upload_policy",
    "scan_upload_or_raise",
    "stream_upload_to_spooled_file",
    "training_quota_status",
    "validate_upload_magic_type",
    "validate_upload_type",
]
