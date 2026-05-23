from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.chat.errors import ChatConfigurationError, ChatPermissionDenied, ChatRequestInvalid
from apps.chat.service.answer_download_service import AnswerDownloadService
from apps.chat.service.llm_answer_service import LLMAnswerService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _KbService:
    def get_query_source_download(self, query_run_id: str, source_id: str) -> dict:
        return {"corpus_uuid": "kb-1", "query_run_id": query_run_id, "source_id": source_id}

    def user_can_use(self, corpus_uuid: str, user_id: int, subject: object) -> bool:
        return False


def test_answer_download_service_raises_chat_app_error_for_permission_denial() -> None:
    service = AnswerDownloadService(_KbService())

    with pytest.raises(ChatPermissionDenied):
        service.download_answer_source(
            query_run_id="query-1",
            source_id="source-1",
            user_id=7,
            user_role="user",
        )


def test_llm_answer_service_raises_chat_app_error_for_missing_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.chat.service.llm_answer_service.settings", SimpleNamespace(chat_provider="openai", openai_api_key=""))

    with pytest.raises(ChatConfigurationError):
        LLMAnswerService.from_settings(client=None, client_factory=lambda **_kwargs: object())


def test_chat_request_invalid_is_module_app_error() -> None:
    with pytest.raises(ChatRequestInvalid):
        raise ChatRequestInvalid("Invalid chat payload.")
