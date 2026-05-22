# backend/apps/knowledge/api/file_ingest_use_cases.py
# Feladat: Knowledge file ingest HTTP-use-case orchestration. A routerbol
# kiszervezett upload validalas, streaming, malware/format guard, quota osszegzes
# es file command payload epites, hogy az endpoint csak request/response adapter legyen.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import UploadFile

from apps.knowledge.api.upload_support import (
    StreamedUpload,
    assert_file_count,
    assert_total_storage_limit,
    assert_training_char_limit,
    ensure_training_quota,
    record_training_usage,
    resolve_ingest_upload_policy,
    stream_upload_to_spooled_file,
    training_quota_status,
    validate_upload_type,
)
from apps.knowledge.application import KnowledgeIngestApplicationService


@dataclass
class FileIngestEstimateCommand:
    tenant: Any
    files: list[UploadFile]


@dataclass
class FileIngestRunCommand:
    tenant: Any
    corpus_uuid: str
    files: list[UploadFile]
    character_counts: list[int]
    created_by: int | None


@dataclass
class PreparedFileIngestPayload:
    file_payloads: list[dict[str, object]] = field(default_factory=list)
    total_char_count: int = 0
    total_storage_bytes: int = 0

    def close(self) -> None:
        for file_payload in self.file_payloads:
            fileobj = file_payload.get("fileobj")
            close = getattr(fileobj, "close", None)
            if callable(close):
                close()


class FileIngestUseCase:
    async def estimate(self, command: FileIngestEstimateCommand) -> dict[str, object]:
        policy = resolve_ingest_upload_policy(command.tenant)
        assert_file_count(command.files, policy=policy)
        items: list[dict[str, object]] = []
        total_char_count = 0
        total_storage_bytes = 0
        for upload in command.files:
            filename = upload.filename or "upload.bin"
            validate_upload_type(filename, upload.content_type)
            streamed = await stream_upload_to_spooled_file(upload, max_bytes=policy.max_file_bytes)
            try:
                total_char_count += streamed.estimated_char_count
                total_storage_bytes += streamed.size_bytes
                assert_total_storage_limit(total_storage_bytes, policy=policy)
                assert_training_char_limit(total_char_count, policy=policy)
                items.append(
                    {
                        "filename": filename,
                        "mime_type": upload.content_type,
                        "char_count": max(0, int(streamed.estimated_char_count)),
                        "storage_bytes": max(0, int(streamed.size_bytes)),
                    }
                )
            finally:
                streamed.fileobj.close()
        can_start, reason = training_quota_status(command.tenant, char_count=total_char_count)
        return {
            "file_count": len(items),
            "total_char_count": max(0, int(total_char_count)),
            "total_storage_bytes": max(0, int(total_storage_bytes)),
            "can_start": can_start,
            "reason": reason,
            "is_estimate": True,
            "items": items,
        }

    async def create_run_and_enqueue(
        self,
        command: FileIngestRunCommand,
        *,
        ingest_service: KnowledgeIngestApplicationService,
    ):
        prepared = await self.prepare_run(command)
        try:
            ensure_training_quota(command.tenant, char_count=prepared.total_char_count)
            run = ingest_service.create_file_run_and_enqueue(
                tenant_slug=command.tenant.slug or None,
                corpus_uuid=command.corpus_uuid,
                files=prepared.file_payloads,
                created_by=command.created_by,
            )
            record_training_usage(command.tenant, char_count=0, storage_bytes=prepared.total_storage_bytes)
            return run
        finally:
            prepared.close()

    async def prepare_run(self, command: FileIngestRunCommand) -> PreparedFileIngestPayload:
        policy = resolve_ingest_upload_policy(command.tenant)
        assert_file_count(command.files, policy=policy)
        prepared = PreparedFileIngestPayload()
        for index, upload in enumerate(command.files):
            filename = upload.filename or "upload.bin"
            validate_upload_type(filename, upload.content_type)
            streamed = await stream_upload_to_spooled_file(upload, max_bytes=policy.max_file_bytes)
            self._append_streamed_upload(
                prepared,
                streamed=streamed,
                provided_char_count=int(command.character_counts[index]) if index < len(command.character_counts) else 0,
                policy=policy,
            )
        return prepared

    def _append_streamed_upload(
        self,
        prepared: PreparedFileIngestPayload,
        *,
        streamed: StreamedUpload,
        provided_char_count: int,
        policy: Any,
    ) -> None:
        estimated_char_count = max(provided_char_count, streamed.estimated_char_count)
        prepared.total_char_count += estimated_char_count
        prepared.total_storage_bytes += streamed.size_bytes
        assert_total_storage_limit(prepared.total_storage_bytes, policy=policy)
        assert_training_char_limit(prepared.total_char_count, policy=policy)
        prepared.file_payloads.append(
            {
                "filename": streamed.filename,
                "fileobj": streamed.fileobj,
                "mime_type": streamed.content_type,
                "size_bytes": streamed.size_bytes,
                "checksum_sha256": streamed.checksum_sha256,
                "estimated_char_count": max(0, int(estimated_char_count)),
            }
        )


__all__ = [
    "FileIngestEstimateCommand",
    "FileIngestRunCommand",
    "FileIngestUseCase",
    "PreparedFileIngestPayload",
]
