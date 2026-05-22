from __future__ import annotations

import pytest

from apps.chat.service.retrieval_context_builder import RetrievalContextBuilder

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _KbServiceStub:
    def user_can_use(self, kb_uuid: str, user_id: int, permission_subject) -> bool:
        return kb_uuid != "forbidden-kb"

    def search_assertions(self, **_kwargs):
        return [{"id": "assertion-1", "text": "A szerződés aktív."}]


def _builder(kb_service=None) -> RetrievalContextBuilder:
    return RetrievalContextBuilder(
        kb_service=kb_service,
        retrieval_service=None,
        query_parser=None,
        context_builder=None,
        enrich_parsed_query=lambda _q, parsed: dict(parsed),
        is_followup=lambda _uid, _parsed: False,
        llm_context_text_from_packet=lambda packet: str(packet.get("context_text") or ""),
        stamp_packet_kb=lambda _packet, _kb_uuid, _kb_name: None,
        merge_context_packets=lambda packets, **kwargs: {"packets": packets, **kwargs},
    )


@pytest.mark.anyio
async def test_builder_returns_empty_packet_when_kb_service_missing() -> None:
    packet = await _builder(kb_service=None).build(question="Mi a státusz?", user_id=1)
    assert packet["top_assertions"] == []
    assert isinstance(packet["scoring_summary"], dict)


@pytest.mark.anyio
async def test_builder_checks_kb_permission() -> None:
    with pytest.raises(PermissionError):
        await _builder(kb_service=_KbServiceStub()).build(
            question="Mi a státusz?",
            user_id=1,
            kb_uuid="forbidden-kb",
        )
