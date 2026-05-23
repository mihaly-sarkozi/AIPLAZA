# backend/apps/chat/service/channel_chat_use_case.py
# Feladat: Channel chat request teljes HTTP use-case orchestration belépőpontja.
# A router csak dependencyket ad át és execute()-ot hív.

from __future__ import annotations

from typing import Any

from fastapi import Request, Response as MutableResponse

from core.kernel.audit import AuditPort


class ChannelChatUseCase:
    async def execute(
        self,
        *,
        request: Request,
        req: Any,
        tenant: Any,
        response: MutableResponse,
        audit: AuditPort | None,
        svc: Any,
    ):
        # Runtime import: a meglévő tesztek monkeypatch-elhetik a use-case függvényt.
        from apps.chat.application import http_use_cases

        return await http_use_cases.handle_channel_chat_request(
            request=request,
            req=req,
            tenant=tenant,
            response=response,
            audit=audit,
            svc=svc,
        )


__all__ = ["ChannelChatUseCase"]
