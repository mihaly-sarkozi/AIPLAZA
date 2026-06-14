# backend/core/kernel/config/settings_infra_validators.py
# Feladat: Az infrastruktúrához és technikai alrendszerekhez tartozó settings validációkat tartalmazza. Ellenőrzi az upload biztonsági limiteket, observability histogram/tracing beállításokat és embedding provider mezőket. A base.py közvetetten hívja, ezért ez belső config helper, nem üzleti logika.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.kernel.config.settings_constants import (
    ALLOWED_EMBEDDING_PROVIDERS,
    ALLOWED_MALWARE_SCAN_PROVIDERS,
)


def validate_upload_security(settings: Any) -> None:
    if int(settings.upload_spool_max_memory_bytes) < 64 * 1024:
        raise ValueError("upload_spool_max_memory_bytes legalább 65536 legyen.")
    if int(settings.upload_parser_timeout_sec) <= 0:
        raise ValueError("upload_parser_timeout_sec pozitívnak kell lennie.")
    if int(settings.upload_parser_memory_limit_mb) < 32:
        raise ValueError("upload_parser_memory_limit_mb legalább 32 legyen.")
    if int(settings.upload_pdf_max_pages) <= 0:
        raise ValueError("upload_pdf_max_pages pozitívnak kell lennie.")
    if int(settings.upload_docx_max_zip_entries) <= 0:
        raise ValueError("upload_docx_max_zip_entries pozitívnak kell lennie.")
    if int(settings.upload_docx_max_decompressed_bytes) <= 0:
        raise ValueError("upload_docx_max_decompressed_bytes pozitívnak kell lennie.")
    if float(settings.upload_docx_max_compression_ratio) <= 1.0:
        raise ValueError("upload_docx_max_compression_ratio értéke legyen > 1.0.")
    provider = str(settings.upload_malware_scan_provider or "none").strip().lower()
    if provider not in ALLOWED_MALWARE_SCAN_PROVIDERS:
        raise ValueError("upload_malware_scan_provider értéke: none vagy clamav.")
    if int(settings.upload_malware_scan_timeout_sec) <= 0:
        raise ValueError("upload_malware_scan_timeout_sec pozitívnak kell lennie.")
    socket_path = str(settings.upload_clamav_unix_socket_path or "").strip()
    if provider == "clamav" and not socket_path:
        raise ValueError("clamav providerhez upload_clamav_unix_socket_path kötelező.")
    if provider == "clamav" and socket_path:
        # Path check csak formai, tényleges elérhetőség runtime.
        _ = Path(socket_path)


def validate_observability(settings: Any) -> None:
    if not (0.0 <= float(settings.observability_trace_sample_ratio) <= 1.0):
        raise ValueError("observability_trace_sample_ratio értéke 0.0 és 1.0 között legyen.")
    if not (0.0 <= float(settings.sentry_traces_sample_rate) <= 1.0):
        raise ValueError("sentry_traces_sample_rate értéke 0.0 és 1.0 között legyen.")
    buckets_raw = str(settings.observability_metrics_histogram_buckets_ms or "").strip()
    if not buckets_raw:
        raise ValueError("observability_metrics_histogram_buckets_ms nem lehet üres.")
    try:
        parsed = [float(item.strip()) for item in buckets_raw.split(",") if item.strip()]
    except Exception as exc:
        raise ValueError("observability_metrics_histogram_buckets_ms csak számokat tartalmazhat.") from exc
    if not parsed or any(value <= 0 for value in parsed):
        raise ValueError("observability histogram bucket értékek legyenek pozitív számok.")
    if parsed != sorted(parsed):
        raise ValueError("observability histogram bucket lista legyen növekvő sorrendben.")


def validate_embedding(settings: Any) -> None:
    provider = (settings.embedding_provider or "").strip().lower()
    if provider not in ALLOWED_EMBEDDING_PROVIDERS:
        raise ValueError("embedding_provider érvénytelen. Megengedett értékek: local, openai, dummy.")
    if settings.embedding_vector_size <= 0:
        raise ValueError("embedding_vector_size pozitívnak kell lennie.")
    if settings.embedding_batch_size <= 0:
        raise ValueError("embedding_batch_size pozitívnak kell lennie.")
    if settings.embedding_worker_concurrency <= 0:
        raise ValueError("embedding_worker_concurrency pozitívnak kell lennie.")
    device = str(getattr(settings, "embedding_device", "cpu") or "cpu").strip().lower()
    if device not in {"cpu", "cuda", "mps"}:
        raise ValueError("embedding_device érvénytelen. Megengedett: cpu, cuda, mps.")
    if provider == "dummy" and not bool(getattr(settings, "embedding_allow_dummy", False)):
        raise ValueError("embedding_provider=dummy csak embedding_allow_dummy=true esetén engedélyezett.")


__all__ = [
    "validate_embedding",
    "validate_observability",
    "validate_upload_security",
]
