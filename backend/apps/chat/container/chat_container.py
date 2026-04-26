# Ez a fájl a komponensek összerakását és a függőségek felépítését tartalmazza.
from __future__ import annotations

from dataclasses import dataclass

from apps.chat.service.chat_service import ChatService


@dataclass(frozen=True)
class ChatFeatureContainer:
    service: ChatService


# Ez a függvény felépíti a(z) chat feature logikáját.
def build_chat_feature(service: ChatService) -> ChatFeatureContainer:
    return ChatFeatureContainer(service=service)
