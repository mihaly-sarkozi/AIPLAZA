# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI

from core.kernel.config import app_settings
from apps.chat.service.chat_service import ChatService


@dataclass(frozen=True)
class ChatModuleInfrastructure:
    knowledge_service: object | None = None

    # Ez a metódus felépíti a(z) llm client logikáját.
    def build_llm_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=app_settings.openai_api_key)

    # Ez a metódus felépíti a(z) chat szolgáltatás logikáját.
    def build_chat_service(self) -> ChatService:
        return ChatService(
            chat_model=self.build_llm_client(),
            kb_service=self.knowledge_service,
            retrieval_service=self.knowledge_service,
        )


# Ez a függvény felépíti a(z) chat infrastructure logikáját.
def build_chat_infrastructure(*, knowledge_service: object | None = None) -> ChatModuleInfrastructure:
    return ChatModuleInfrastructure(knowledge_service=knowledge_service)
