# Ez a fájl a(z) contracts modul backend logikáját tartalmazza.
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class ChatGateway(Protocol):
    # Ez az aszinkron metódus a(z) chat logikáját valósítja meg.
    async def chat(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> str: ...
    # Ez az aszinkron metódus a(z) chat_with_sources logikáját valósítja meg.
    async def chat_with_sources(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        tenant: str | None = None,
        debug: bool = False,
    ) -> dict: ...

    # Ez az aszinkron metódus a(z) chat_stream logikáját valósítja meg.
    async def chat_stream(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> AsyncIterator[str]: ...
    # Ez a metódus a(z) capture_retrieval_feedback logikáját valósítja meg.
    def capture_retrieval_feedback(
        self,
        trace_id: str,
        helpful: bool | None = None,
        context_useful: bool | None = None,
        wrong_entity_resolution: bool = False,
        wrong_time_slice: bool = False,
        note: str | None = None,
    ) -> dict: ...


__all__ = ["ChatGateway"]
