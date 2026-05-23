# backend/apps/knowledge/service/ingest_run_creation_service.py
# Owns application-level ingest run creation for text, file, and URL inputs.

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Any

from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.service.facade_helpers import normalize_text_payload as _normalize_text_payload
from apps.knowledge.service.ingest_progress_service import IngestProgressService
from core.kernel.interface.observability import increment_metric as increment_platform_metric

logger = logging.getLogger(__name__)


class IngestRunCreationService:
    def __init__(self, facade: Any, *, progress_service: IngestProgressService) -> None:
        self._facade = facade
        self._progress_service = progress_service

    def __getattr__(self, name: str) -> Any:
        return getattr(self._facade, name)

    @staticmethod
    def ingest_pipeline_version() -> str:
        return "source_parser.v1"

    @classmethod
    def ingest_idempotency_key(
        cls,
        *,
        corpus_uuid: str,
        content_hash: str,
        pipeline_version: str | None = None,
    ) -> str:
        version = pipeline_version or cls.ingest_pipeline_version()
        return f"{corpus_uuid}:{version}:{content_hash}"

    def record_ingest_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        item_id: str | None = None,
        message: str | None = None,
        created_by: int | None = None,
        **details: Any,
    ) -> IngestEvent:
        return self._knowledge_audit_service.record_ingest_event(
            run_id=run_id,
            event_type=event_type,
            status=status,
            item_id=item_id,
            message=message,
            created_by=created_by,
            **details,
        )

    @staticmethod
    def _sha256_text(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _sha256_bytes(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def create_text_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        title: str,
        text: str,
        created_by: int | None,
    ) -> IngestRun:
        self._require_corpus(corpus_uuid)
        payload = _normalize_text_payload(text)
        if not payload.strip():
            raise ValueError("Text input is required")
        run = self._ingest_runs().create_run(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            input_channel="text",
            batch_size=1,
            pipeline_route="source_parser",
            created_by=created_by,
            metadata={"input_types": ["text"]},
        )
        self.record_ingest_event(
            run_id=run.id,
            event_type="ingest_run_created",
            status="ok",
            message="Szöveges ingest run létrehozva.",
            created_by=created_by,
            batch_size=1,
        )
        pipeline_version = self.ingest_pipeline_version()
        content_hash = self._sha256_text(payload)
        item = IngestItem(
            ingest_run_id=run.id,
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            queue_order=1,
            input_type="text",
            display_name=self._ensure_title(title, fallback="Text input"),
            title=self._ensure_title(title, fallback="Text input"),
            origin="manual:text",
            status="queued",
            progress_message="Várakozik a háttérfeldolgozásra.",
            pipeline_route="source_parser",
            pipeline_version=pipeline_version,
            content_hash=content_hash,
            idempotency_key=self.ingest_idempotency_key(
                corpus_uuid=corpus_uuid,
                content_hash=content_hash,
                pipeline_version=pipeline_version,
            ),
            created_by=created_by,
            metadata={"char_count": len(payload), "text_preview": payload[:160], "text_encoding": "utf-8"},
        )
        ingest_input = IngestInput(
            ingest_item_id=item.id,
            tenant=tenant,
            input_type="text",
            text_content=payload,
            size_bytes=len(payload.encode("utf-8")),
            encoding="utf-8",
            metadata={"title": item.title},
        )
        self._ingest_item_store.create_many([item])
        self._ingest_input_store.create_many([ingest_input])
        self.record_ingest_event(
            run_id=run.id,
            item_id=item.id,
            event_type="item_received",
            status="ok",
            message="Szöveges input rögzítve.",
            created_by=created_by,
            input_type="text",
            title=item.title,
        )
        return self._refresh_ingest_run(run.id)

    def create_file_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        files: list[dict[str, Any]],
        created_by: int | None,
    ) -> IngestRun:
        self._require_corpus(corpus_uuid)
        if not files:
            increment_platform_metric("file_upload_rejections_total", 1.0, tags={"reason": "empty_batch"})
            raise ValueError("At least one file is required")
        run = self._ingest_runs().create_run(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            input_channel="file",
            batch_size=len(files),
            pipeline_route="source_parser",
            created_by=created_by,
            metadata={"input_types": ["file"], "batch_size": len(files)},
        )
        self.record_ingest_event(
            run_id=run.id,
            event_type="ingest_run_created",
            status="ok",
            message="Fájlos ingest run létrehozva.",
            created_by=created_by,
            batch_size=len(files),
        )
        try:
            items: list[IngestItem] = []
            inputs: list[IngestInput] = []
            pipeline_version = self.ingest_pipeline_version()
            seen_content_hashes: set[str] = set()
            for index, file_info in enumerate(files, start=1):
                filename = str(file_info.get("filename") or f"upload-{index}.bin")
                fileobj = file_info.get("fileobj")
                content = bytes(file_info.get("content") or b"") if fileobj is None else b""
                size_bytes = int(file_info.get("size_bytes") or 0)
                if fileobj is None and not content:
                    increment_platform_metric("file_upload_rejections_total", 1.0, tags={"reason": "empty_file"})
                    raise ValueError(f"Empty file input: {filename}")
                if fileobj is not None and size_bytes <= 0:
                    increment_platform_metric("file_upload_rejections_total", 1.0, tags={"reason": "empty_file"})
                    raise ValueError(f"Empty file input: {filename}")
                estimated_char_count = int(
                    file_info.get("estimated_char_count")
                    or file_info.get("char_count")
                    or self._progress_service.estimate_file_character_count_from_size(size_bytes)
                )
                checksum_sha256 = str(file_info.get("checksum_sha256") or "").strip()
                if not checksum_sha256 and fileobj is None and content:
                    checksum_sha256 = self._sha256_bytes(content)
                item = IngestItem(
                    ingest_run_id=run.id,
                    tenant=tenant,
                    corpus_uuid=corpus_uuid,
                    queue_order=index,
                    input_type="file",
                    display_name=filename,
                    title=self._ensure_title(str(file_info.get("title") or filename), fallback=filename),
                    origin=filename,
                    status="queued",
                    progress_message="Fájl rögzítve, háttérben feldolgozásra vár.",
                    pipeline_route="source_parser",
                    pipeline_version=pipeline_version,
                    content_hash=checksum_sha256 or None,
                    idempotency_key=(
                        self.ingest_idempotency_key(
                            corpus_uuid=corpus_uuid,
                            content_hash=checksum_sha256,
                            pipeline_version=pipeline_version,
                        )
                        if checksum_sha256
                        else None
                    ),
                    created_by=created_by,
                    metadata={
                        "filename": filename,
                        "size_bytes": size_bytes,
                        "estimated_char_count": estimated_char_count,
                    },
                )
                try:
                    stored_ref = self._source_storage_service.store_uploaded_source(
                        tenant=tenant,
                        corpus_uuid=corpus_uuid,
                        run_id=run.id,
                        item_id=item.id,
                        filename=filename,
                        mime_type=str(file_info.get("mime_type") or "application/octet-stream"),
                        fileobj=fileobj,
                        content=content,
                        size_bytes=size_bytes,
                        checksum_sha256=checksum_sha256,
                        seen_content_hashes=seen_content_hashes,
                    )
                except ValueError as exc:
                    if "Object storage adapter does not support streaming file uploads." in str(exc):
                        increment_platform_metric("file_upload_rejections_total", 1.0, tags={"reason": "storage_adapter"})
                    raise
                checksum_sha256 = str(stored_ref.checksum_sha256 or checksum_sha256 or "").strip()
                if checksum_sha256 and item.content_hash != checksum_sha256:
                    item = replace(
                        item,
                        content_hash=checksum_sha256,
                        idempotency_key=self.ingest_idempotency_key(
                            corpus_uuid=corpus_uuid,
                            content_hash=checksum_sha256,
                            pipeline_version=pipeline_version,
                        ),
                    )
                items.append(item)
                inputs.append(
                    IngestInput(
                        ingest_item_id=item.id,
                        tenant=tenant,
                        input_type="file",
                        storage_provider=stored_ref.storage_provider,
                        bucket_name=stored_ref.bucket_name,
                        object_key=stored_ref.object_key,
                        original_filename=filename,
                        mime_type=stored_ref.mime_type,
                        size_bytes=stored_ref.size_bytes or size_bytes,
                        checksum_sha256=checksum_sha256,
                        metadata={
                            "etag": stored_ref.etag,
                            "estimated_char_count": estimated_char_count,
                            "source_metadata": stored_ref.source_metadata,
                        },
                    )
                )
            created_items = self._ingest_item_store.create_many(items)
            self._ingest_input_store.create_many(inputs)
            for item in created_items:
                self.record_ingest_event(
                    run_id=run.id,
                    item_id=item.id,
                    event_type="stored_to_object_storage",
                    status="ok",
                    message="Fájl mentve object storage-ba.",
                    created_by=created_by,
                    display_name=item.display_name,
                )
            return self._refresh_ingest_run(run.id)
        except Exception as exc:
            failed_run = self._ingest_runs().mark_run_failed(
                run=run,
                error_message=str(exc),
                failed_count=len(files),
            )
            self.record_ingest_event(
                run_id=run.id,
                event_type="storage_failed",
                status="failed",
                message=str(exc),
                created_by=created_by,
            )
            self._log_step(
                "ingest.file.create_failed",
                status="error",
                tenant=tenant,
                ingest_run_id=failed_run.id,
            )
            raise

    def create_url_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        urls: list[dict[str, Any]],
        created_by: int | None,
    ) -> IngestRun:
        self._require_corpus(corpus_uuid)
        normalized_urls = [item for item in urls if str(item.get("url") or "").strip()]
        if not normalized_urls:
            raise ValueError("At least one URL is required")
        run = self._ingest_runs().create_run(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            input_channel="url",
            batch_size=len(normalized_urls),
            pipeline_route="source_parser",
            created_by=created_by,
            metadata={"input_types": ["url"], "batch_size": len(normalized_urls)},
        )
        self.record_ingest_event(
            run_id=run.id,
            event_type="ingest_run_created",
            status="ok",
            message="URL ingest run létrehozva.",
            created_by=created_by,
            batch_size=len(normalized_urls),
        )
        items: list[IngestItem] = []
        inputs: list[IngestInput] = []
        pipeline_version = self.ingest_pipeline_version()
        for index, url_info in enumerate(normalized_urls, start=1):
            url = self._url_fetch_service.validate_target(str(url_info.get("url") or "").strip())
            display_name = str(url_info.get("title") or url)
            content_hash = self._sha256_text(url)
            item = IngestItem(
                ingest_run_id=run.id,
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                queue_order=index,
                input_type="url",
                display_name=display_name[:255],
                title=self._ensure_title(str(url_info.get("title") or display_name), fallback=url),
                origin=url,
                status="queued",
                progress_message="URL rögzítve, elérhetőség ellenőrzésre vár.",
                pipeline_route="source_parser",
                pipeline_version=pipeline_version,
                content_hash=content_hash,
                idempotency_key=self.ingest_idempotency_key(
                    corpus_uuid=corpus_uuid,
                    content_hash=content_hash,
                    pipeline_version=pipeline_version,
                ),
                created_by=created_by,
                metadata={"url": url},
            )
            items.append(item)
            inputs.append(
                IngestInput(
                    ingest_item_id=item.id,
                    tenant=tenant,
                    input_type="url",
                    origin_url=url,
                    metadata={"title": item.title},
                )
            )
        self._ingest_item_store.create_many(items)
        self._ingest_input_store.create_many(inputs)
        for item in items:
            self.record_ingest_event(
                run_id=run.id,
                item_id=item.id,
                event_type="item_received",
                status="ok",
                message="URL input rögzítve.",
                created_by=created_by,
                origin=item.origin,
            )
        return self._refresh_ingest_run(run.id)


__all__ = ["IngestRunCreationService"]
