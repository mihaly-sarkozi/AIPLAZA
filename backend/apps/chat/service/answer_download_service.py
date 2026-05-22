# backend/apps/chat/service/answer_download_service.py
# Feladat: Chat valaszhoz kapcsolodo forras es kontextus letoltesi use-case-ek.
# Jogosultsagot ellenoriz a knowledge service public feluleten keresztul.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PermissionSubject:
    id: int | None
    role: str | None
    is_active: bool = True


class AnswerDownloadService:
    def __init__(self, kb_service: Any = None):
        self._kb_service = kb_service

    def download_answer_source(
        self,
        *,
        query_run_id: str,
        source_id: str,
        user_id: int | None = None,
        user_role: str | None = None,
    ) -> dict | None:
        kb_service = self._kb_service
        if kb_service is None or not hasattr(kb_service, "get_query_source_download"):
            return None
        download = kb_service.get_query_source_download(query_run_id, source_id)
        if download is None:
            return None
        self._ensure_can_use_download(download, user_id=user_id, user_role=user_role)
        return download

    def download_answer_context(
        self,
        *,
        query_run_id: str,
        user_id: int | None = None,
        user_role: str | None = None,
    ) -> dict | None:
        kb_service = self._kb_service
        if kb_service is None or not hasattr(kb_service, "get_query_context_download"):
            return None
        download = kb_service.get_query_context_download(query_run_id)
        if download is None:
            return None
        self._ensure_can_use_download(download, user_id=user_id, user_role=user_role)
        return download

    def _ensure_can_use_download(
        self,
        download: dict,
        *,
        user_id: int | None,
        user_role: str | None,
    ) -> None:
        corpus_uuid = str(download.get("corpus_uuid") or "").strip()
        kb_service = self._kb_service
        if not corpus_uuid or user_id is None or kb_service is None or not hasattr(kb_service, "user_can_use"):
            return
        subject = PermissionSubject(id=user_id, role=user_role, is_active=True)
        if not kb_service.user_can_use(corpus_uuid, user_id, subject):
            raise PermissionError("Nincs jogosultság a megadott tudástár használatához.")


__all__ = ["AnswerDownloadService", "PermissionSubject"]
