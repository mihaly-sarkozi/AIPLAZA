# backend/apps/knowledge/service/source_access_service.py
# Owns source display metadata and source/query download payloads.

from __future__ import annotations

from typing import Any

from apps.knowledge.domain.source import Source


class SourceAccessService:
    def __init__(self, facade: Any) -> None:
        self._facade = facade

    def __getattr__(self, name: str) -> Any:
        return getattr(self._facade, name)

    def get_source_content(self, source_id: str) -> dict[str, Any] | None:
        source = self._source_store.get(source_id)
        if source is None:
            return None
        document = self._document_store.get_for_source(source_id)
        return {
            "id": source.id,
            "corpus_uuid": source.corpus_uuid,
            "title": source.title,
            "source_type": source.source_type,
            "file_ref": source.file_ref,
            "original_content": source.raw_content,
            "extracted_text": document.text_content if document is not None else str(source.raw_content or ""),
            "metadata": source.metadata,
        }

    @staticmethod
    def source_display_type(source: Source) -> str:
        if source.source_type == "text":
            return "Gépelés"
        filename = str(source.file_ref or source.title or "").lower()
        if filename.endswith(".pdf"):
            return "PDF"
        if filename.endswith(".docx"):
            return "DOCX"
        if filename.endswith(".doc"):
            return "DOC"
        if source.source_type == "url":
            return "URL"
        return "Fájl" if source.source_type == "file" else str(source.source_type or "")

    def source_created_by_label(self, source: Source) -> str:
        return self.user_label(source.created_by)

    def user_label(self, user_id: int | None) -> str:
        if user_id is None:
            return "Ismeretlen"
        user = None
        if self._user_repo is not None and hasattr(self._user_repo, "get_by_id"):
            try:
                user = self._user_repo.get_by_id(user_id)
            except Exception:
                user = None
        for attr in ("full_name", "name", "email", "username"):
            value = getattr(user, attr, None) if user is not None else None
            if str(value or "").strip():
                return str(value).strip()
        return f"Felhasználó #{user_id}"

    @staticmethod
    def download_filename(source: Source) -> str:
        filename = str(source.file_ref or source.title or source.id).strip() or source.id
        if source.source_type == "text" and "." not in filename.rsplit("/", 1)[-1]:
            filename = f"{filename}.txt"
        return filename

    def get_source_download(self, source_id: str) -> dict[str, Any] | None:
        source = self._source_store.get(source_id)
        if source is None:
            return None
        filename = self.download_filename(source)
        if source.source_type == "file":
            bucket_name = str(source.metadata.get("bucket_name") or "")
            object_key = str(source.metadata.get("object_key") or "")
            if not bucket_name or not object_key:
                return None
            stored = self._object_storage.get_bytes(key=object_key, bucket=bucket_name)
            return {
                "filename": filename,
                "content_type": stored.ref.content_type or source.metadata.get("mime_type") or "application/octet-stream",
                "body": stored.body,
            }
        document = self._document_store.get_for_source(source_id) if hasattr(self._document_store, "get_for_source") else None
        text = str(source.raw_content or (document.text_content if document is not None else "") or "")
        return {
            "filename": filename,
            "content_type": "text/plain; charset=utf-8",
            "body": text.encode("utf-8"),
        }

    def get_query_source_download(self, query_run_id: str, source_id: str) -> dict[str, Any] | None:
        run = self._query_run_store.get(query_run_id)
        if run is None:
            return None
        direct_download = self.get_source_download(source_id)
        if direct_download is not None:
            return direct_download

        citation = next(
            (
                item
                for item in run.citations
                if item.source_id == source_id or item.chunk_id == source_id
            ),
            None,
        )
        snippet = citation.snippet if citation is not None else ""
        if not snippet:
            snippet = run.context_text or ""
        answer_text = str(run.metadata.get("answer_text") or "")
        parts = [
            "AIPLAZA chat source context",
            f"Query run: {run.id}",
            f"Source id: {source_id}",
            f"Question: {run.query}",
            f"Answer: {answer_text}",
            "",
            "Context:",
            snippet,
        ]
        return {
            "filename": f"aiplaza-context-{source_id[:8] or run.id[:8]}.txt",
            "content_type": "text/plain; charset=utf-8",
            "body": "\n".join(parts).encode("utf-8"),
            "corpus_uuid": run.corpus_uuid,
        }

    def get_query_context_download(self, query_run_id: str) -> dict[str, Any] | None:
        run = self._query_run_store.get(query_run_id)
        if run is None:
            return None
        answer_text = str(run.metadata.get("answer_text") or "")
        parts = [
            "AIPLAZA LLM context audit",
            f"Query run: {run.id}",
            f"Corpus UUID: {run.corpus_uuid}",
            f"Question: {run.query}",
            f"Answer: {answer_text}",
            "",
            "LLM instructions:",
            (
                "A kovetkezo tudastar-context alapjan valaszolj tomoren, es csak akkor allits tenyt, "
                "ha a context alatamasztja. A valasz nyelve mindig egyezzen meg a felhasznalo kerdesenek nyelvevel."
            ),
            "",
            "Context sent to LLM:",
            run.context_text or "",
        ]
        return {
            "filename": f"aiplaza-llm-context-{run.id[:8]}.txt",
            "content_type": "text/plain; charset=utf-8",
            "body": "\n".join(parts).encode("utf-8"),
            "corpus_uuid": run.corpus_uuid,
        }

    def read_ingest_file_bytes(self, item_id: str) -> tuple[bytes, str | None, str | None]:
        ingest_input = self._ingest_input_store.get_for_item(item_id)
        if ingest_input is None:
            raise ValueError("Ingest input not found")
        if ingest_input.input_type != "file":
            raise ValueError("Ingest input is not a file")
        if not ingest_input.bucket_name or not ingest_input.object_key:
            raise ValueError("Object storage reference is missing")
        stored = self._object_storage.get_bytes(key=ingest_input.object_key, bucket=ingest_input.bucket_name)
        return stored.body, ingest_input.mime_type or stored.ref.content_type, ingest_input.original_filename


__all__ = ["SourceAccessService"]
