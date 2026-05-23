# backend/apps/knowledge/service/url_fetch_service.py
# Feladat: A knowledge URL ingest validációját, HEAD elérhetőségi ellenőrzését és biztonságos tartalomletöltését kezeli. Leválasztja a KnowledgeFacade-ból az SSRF/DNS/redirect/content-type hardeninggel kapcsolatos URL fetch felelősséget, hogy a facade csak orchestration/kompatibilitási réteg maradjon. Program-specifikus application service boundary.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

import re
import time
from html import unescape
from typing import Callable

from core.kernel.interface.observability import increment_metric, observe_metric
from apps.knowledge.service.url_ingest_security import (
    UrlFetchResult,
    UrlIngestRejected,
    get_url_text,
    request_url_head,
    validate_url_target,
)
from shared.documents import ExtractedDocument, ExtractedParagraph


class UrlFetchService:
    def __init__(self, *, text_normalizer: Callable[[str | None], str]) -> None:
        self._normalize_text = text_normalizer

    def validate_target(self, url: str) -> str:
        try:
            return validate_url_target(url)
        except UrlIngestRejected as exc:
            increment_metric("url_ingest_rejections_total", 1.0, tags={"reason": str(exc.code)})
            raise

    def request_head(self, url: str, *, timeout: int = 15) -> UrlFetchResult:
        try:
            response = request_url_head(url, timeout=timeout)
        except UrlIngestRejected as exc:
            increment_metric("url_ingest_rejections_total", 1.0, tags={"reason": str(exc.code)})
            raise
        if response.status_code >= 400:
            increment_metric("url_ingest_rejections_total", 1.0, tags={"reason": "http_status"})
            raise ValueError(f"URL is not reachable ({response.status_code})")
        return response

    def fetch_document(self, url: str, *, timeout: int = 20) -> ExtractedDocument:
        started = time.perf_counter()
        try:
            fetched = get_url_text(url, timeout=timeout)
        except UrlIngestRejected as exc:
            observe_metric("url_ingest_duration_seconds", time.perf_counter() - started, unit="seconds")
            increment_metric("url_ingest_rejections_total", 1.0, tags={"reason": str(exc.code)})
            raise
        observe_metric("url_ingest_duration_seconds", time.perf_counter() - started, unit="seconds")
        observe_metric("url_ingest_download_bytes", float(len(fetched.body or b"")), unit="bytes")
        html = unescape(fetched.body.decode("utf-8", errors="replace"))
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        normalized = self._normalize_text(text)
        return ExtractedDocument(
            text_content=normalized,
            paragraphs=[ExtractedParagraph(text=normalized)] if normalized else [],
            metadata={
                "source_type": "url",
                "origin_url": url,
                "final_url": fetched.final_url,
                "url_status_code": fetched.status_code,
                "url_content_type": fetched.content_type,
                "extraction_engine": "html_strip_v1",
            },
        )


__all__ = ["UrlFetchService"]
