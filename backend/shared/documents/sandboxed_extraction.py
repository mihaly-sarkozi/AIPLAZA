# backend/shared/documents/sandboxed_extraction.py
# Feladat: Dokumentum-extrakció futtatása izolált subprocessben memória/CPU limittel és timeouttal.
# A parser (pdfplumber/python-docx) nem megbízható inputot dolgoz fel, ezért rosszindulatú fájl
# nem foghatja meg a web/worker processt (parser DoS védelem).
# Sárközi Mihály - 2026.06.11

from __future__ import annotations

import multiprocessing
import os
import pickle
import tempfile

from shared.documents.models import ExtractedDocument
from shared.documents.text_extraction import extract_document_from_upload

DEFAULT_PARSER_TIMEOUT_SEC = 20
DEFAULT_PARSER_MEMORY_LIMIT_MB = 256


class DocumentParserTimeoutError(Exception):
    """A parser nem végzett a megadott időkereten belül."""


class DocumentParserResourceError(Exception):
    """A parser erőforrás-limitbe (memória/CPU) ütközött."""


def _apply_parser_resource_limits(timeout_sec: int, memory_limit_mb: int) -> None:
    import resource

    memory_limit_bytes = max(32, int(memory_limit_mb)) * 1024 * 1024
    for limit_name in ("RLIMIT_AS", "RLIMIT_DATA"):
        limit = getattr(resource, limit_name, None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, (memory_limit_bytes, memory_limit_bytes))
        except (OSError, ValueError):
            pass
    cpu_limit = max(1, int(timeout_sec) + 1)
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    except (OSError, ValueError, AttributeError):
        pass


def _write_result(result_path: str, status: str, payload: object) -> None:
    with open(result_path, "wb") as result_file:
        pickle.dump((status, payload), result_file)


def _extraction_worker(
    filename: str,
    raw: bytes,
    timeout_sec: int,
    memory_limit_mb: int,
    result_path: str,
) -> None:
    try:
        if os.name == "posix":
            _apply_parser_resource_limits(timeout_sec, memory_limit_mb)
        _write_result(result_path, "ok", extract_document_from_upload(filename, raw))
    except ValueError as exc:
        _write_result(result_path, "value_error", str(exc))
    except MemoryError:
        _write_result(result_path, "resource_error", "Document parser memory limit exceeded.")
    except Exception as exc:  # noqa: BLE001 — a worker minden hibát statuszként ad vissza
        _write_result(result_path, "error", str(exc))


def _parser_context():
    if os.name == "posix":
        return multiprocessing.get_context("fork")
    return multiprocessing.get_context("spawn")


def extract_document_with_limits(
    filename: str,
    raw: bytes,
    *,
    timeout_sec: int = DEFAULT_PARSER_TIMEOUT_SEC,
    memory_limit_mb: int = DEFAULT_PARSER_MEMORY_LIMIT_MB,
) -> ExtractedDocument:
    """`extract_document_from_upload` futtatása subprocessben timeout + rlimit védelemmel."""
    effective_timeout = max(1, int(timeout_sec))
    ctx = _parser_context()
    result_path = ""
    try:
        with tempfile.NamedTemporaryFile(prefix="document-parser-", suffix=".pkl", delete=False) as result_file:
            result_path = result_file.name
        process = ctx.Process(
            target=_extraction_worker,
            args=(filename, raw, effective_timeout, memory_limit_mb, result_path),
            daemon=True,
        )
        process.start()
        process.join(effective_timeout)
        if process.is_alive():
            process.terminate()
            process.join(2)
            if process.is_alive():
                process.kill()
                process.join(1)
            raise DocumentParserTimeoutError("Document parser timeout.")
        if not os.path.exists(result_path) or os.path.getsize(result_path) <= 0:
            raise DocumentParserResourceError("Document parser failed without result.")
        with open(result_path, "rb") as result_file:
            status, payload = pickle.load(result_file)  # noqa: S301 — saját worker írta temp fájl
        if status == "ok":
            return payload
        if status == "value_error":
            raise ValueError(str(payload))
        if status == "resource_error":
            raise DocumentParserResourceError(str(payload))
        raise DocumentParserResourceError(str(payload))
    finally:
        if result_path and os.path.exists(result_path):
            try:
                os.unlink(result_path)
            except OSError:
                pass


__all__ = [
    "DEFAULT_PARSER_MEMORY_LIMIT_MB",
    "DEFAULT_PARSER_TIMEOUT_SEC",
    "DocumentParserResourceError",
    "DocumentParserTimeoutError",
    "extract_document_with_limits",
]
