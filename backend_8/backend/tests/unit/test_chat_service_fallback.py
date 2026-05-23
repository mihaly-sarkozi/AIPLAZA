from __future__ import annotations

import asyncio
import pytest

from apps.chat.service.chat_service import ChatService

pytestmark = pytest.mark.unit


class _FakeCompletions:
    async def create(self, model, messages, stream=False):
        assert model == "gpt-4o-mini"
        assert isinstance(messages, list) and len(messages) >= 2
        class _Msg:
            content = "fallback ok"
        class _Choice:
            message = _Msg()
        class _Resp:
            choices = [_Choice()]
        return _Resp()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


def _fake_openai_factory(**_kwargs):
    return _FakeClient()


class _KbExploding:
    def user_can_use(self, kb_uuid, user_id, user):
        return True

    async def build_context_for_chat(self, **kwargs):
        raise RuntimeError("qdrant temporary failure")


class _Parser:
    def parse(self, question: str):
        return {"intent": "summary"}


def test_chat_returns_empty_when_context_build_fails():
    """Context build hiba esetén üres válasz (nem szimulál LLM-mel)."""
    ChatService._openai_client = staticmethod(_fake_openai_factory)
    svc = ChatService(
        chat_model=_FakeClient(),
        kb_service=_KbExploding(),
        query_parser=_Parser(),
        context_builder=None,
    )
    answer = asyncio.run(svc.chat("Teszt kérdés", user_id=1, user_role="owner"))
    assert answer == ""
