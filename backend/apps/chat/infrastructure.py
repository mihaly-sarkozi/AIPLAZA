# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.kernel.config.config_loader import settings
from core.kernel.config.environment import is_test_env
from apps.chat.channel_access import ChannelAccessRepository, ChannelAccessService
from apps.chat.service.pii_depersonalization import PiiDepersonalizationService
from apps.chat.service.chat_service import ChatService


class _TestChatClient:
    class _Responses:
        async def create(self, **_kwargs: Any) -> Any:
            return type(
                "ChatResponse",
                (),
                {"output_text": "Teszt chat válasz."},
            )()

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = dict(kwargs)
        self.responses = self._Responses()


class _KnowledgePiiBridge:
    def __init__(self, knowledge_service: object | None) -> None:
        self._knowledge_service = knowledge_service

    def resolve_or_create_token(self, *, corpus_uuid: str, entity_type: str, original_value: str) -> str:
        if self._knowledge_service is None or not hasattr(self._knowledge_service, "resolve_or_create_pii_token"):
            return ""
        return str(
            self._knowledge_service.resolve_or_create_pii_token(
                corpus_uuid=corpus_uuid,
                entity_type=entity_type,
                original_value=original_value,
            )
            or ""
        )

    def resolve_tokens(self, *, corpus_uuid: str, tokens: list[str]) -> dict[str, str]:
        if self._knowledge_service is None or not hasattr(self._knowledge_service, "resolve_pii_tokens"):
            return {}
        value = self._knowledge_service.resolve_pii_tokens(corpus_uuid=corpus_uuid, tokens=tokens)
        return value if isinstance(value, dict) else {}

    def detect(self, text: str, sensitivity: str) -> list[tuple[int, int, str, str]]:
        if self._knowledge_service is None or not hasattr(self._knowledge_service, "detect_pii_matches"):
            return []
        value = self._knowledge_service.detect_pii_matches(text=text, sensitivity=sensitivity)
        return value if isinstance(value, list) else []


@dataclass(frozen=True)
class ChatModuleInfrastructure:
    knowledge_service: object | None = None
    kb_search_facade: object | None = None
    db_session_factory: object | None = None
    audit_service: object | None = None

    @staticmethod
    def _openai_client(**kwargs: Any):
        try:
            from openai import AsyncOpenAI
        except Exception as exc:  # pragma: no cover - dependency/environment guard
            raise RuntimeError("Az openai csomag nincs telepitve a chat klienshez.") from exc
        if is_test_env() and AsyncOpenAI is object:
            return _TestChatClient(**kwargs)
        return AsyncOpenAI(**kwargs)

    # Ez a metódus felépíti a(z) llm client logikáját.
    def build_llm_client(self):
        provider = str(getattr(settings, "chat_provider", "openai") or "openai").strip().lower()
        if provider == "ollama":
            base_url = str(getattr(settings, "ollama_url", "http://localhost:11434") or "http://localhost:11434").rstrip("/")
            api_key = str(getattr(settings, "ollama_api_key", "ollama") or "ollama")
            return self._openai_client(
                base_url=f"{base_url}/v1",
                api_key=api_key,
            )
        return self._openai_client(api_key=settings.openai_api_key)

    # Ez a metódus felépíti a(z) chat szolgáltatás logikáját.
    def build_chat_service(self) -> ChatService:
        provider = str(getattr(settings, "chat_provider", "openai") or "openai").strip().lower()
        model_name = (
            str(getattr(settings, "ollama_model", "qwen2.5:7b-instruct") or "qwen2.5:7b-instruct")
            if provider == "ollama"
            else str(getattr(settings, "chat_model", "gpt-4o-mini") or "gpt-4o-mini")
        )
        channel_access_service = None
        pii_depersonalization_service = None
        chat_session_service = None
        retrieval_service = self.knowledge_service
        use_kb_search = bool(getattr(settings, "chat_use_kb_search", True))
        if use_kb_search and self.kb_search_facade is not None:
            retrieval_service = self.kb_search_facade
        if self.db_session_factory is not None:
            channel_access_service = ChannelAccessService(ChannelAccessRepository(self.db_session_factory))
            pii_bridge = _KnowledgePiiBridge(self.knowledge_service)
            pii_depersonalization_service = PiiDepersonalizationService(
                pii_bridge,
                detector=pii_bridge.detect,
            )
            from apps.chat.repository.ChatSessionRepository import ChatSessionRepository
            from apps.chat.repository.ChatTurnContextSnapshotRepository import ChatTurnContextSnapshotRepository
            from apps.chat.repository.ChatTurnRepository import ChatTurnRepository
            from apps.chat.service.chat_session_service import ChatSessionService

            chat_session_service = ChatSessionService(
                session_repository=ChatSessionRepository(self.db_session_factory),
                turn_repository=ChatTurnRepository(self.db_session_factory),
                snapshot_repository=ChatTurnContextSnapshotRepository(self.db_session_factory),
            )
        return ChatService(
            chat_model=self.build_llm_client(),
            chat_model_name=model_name,
            kb_service=self.knowledge_service,
            retrieval_service=retrieval_service,
            channel_access_service=channel_access_service,
            pii_depersonalization_service=pii_depersonalization_service,
            audit_service=self.audit_service,
            chat_session_service=chat_session_service,
        )


# Ez a függvény felépíti a(z) chat infrastructure logikáját.
def build_chat_infrastructure(
    *,
    knowledge_service: object | None = None,
    kb_search_facade: object | None = None,
    db_session_factory: object | None = None,
    audit_service: object | None = None,
) -> ChatModuleInfrastructure:
    return ChatModuleInfrastructure(
        knowledge_service=knowledge_service,
        kb_search_facade=kb_search_facade,
        db_session_factory=db_session_factory,
        audit_service=audit_service,
    )
