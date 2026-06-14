# backend/apps/chat/service/llm_answer_service.py
# Feladat: LLM provider hivas, timeout es provider error mapping. A ChatService
# promptot es kontextust keszit, ez a komponens vegzi a konkret modellhivast.

from __future__ import annotations

import asyncio
import inspect
import logging
from time import perf_counter
from typing import Any

from core.kernel.config.config_loader import settings
from core.kernel.interface.observability import increment_metric
from apps.chat.errors import ChatConfigurationError
from apps.chat.service.chat_text_utils import coerce_response_text, extract_response_text

try:
    from openai import AsyncOpenAI
    from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
except Exception:  # pragma: no cover - optional dependency guard
    AsyncOpenAI = Any  # type: ignore
    APIError = Exception  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    RateLimitError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class LLMAnswerService:
    def __init__(
        self,
        *,
        client: Any,
        chat_model_name: str,
        chat_max_tokens: int,
        chat_temperature: float,
        completion_timeout_sec: int,
        response_text_extractor,
    ) -> None:
        self._client = client
        self._chat_model_name = chat_model_name
        self._chat_max_tokens = chat_max_tokens
        self._chat_temperature = chat_temperature
        self._completion_timeout_sec = completion_timeout_sec
        self._extract_response_text = response_text_extractor

    @property
    def client(self) -> Any:
        return self._client

    @property
    def chat_model_name(self) -> str:
        return self._chat_model_name

    @property
    def chat_max_tokens(self) -> int:
        return self._chat_max_tokens

    @property
    def chat_temperature(self) -> float:
        return self._chat_temperature

    @property
    def completion_timeout_sec(self) -> int:
        return self._completion_timeout_sec

    @staticmethod
    def openai_client(**kwargs: Any) -> Any:
        try:
            from openai import AsyncOpenAI as _AsyncOpenAI
        except Exception as exc:  # pragma: no cover - dependency/environment guard
            raise ChatConfigurationError("Az openai csomag nincs telepitve a chat klienshez.") from exc
        return _AsyncOpenAI(**kwargs)

    @staticmethod
    def coerce_response_text(value: Any) -> str:
        return coerce_response_text(value)

    @staticmethod
    def extract_response_text(response: Any) -> str:
        return extract_response_text(response)

    @classmethod
    def from_settings(
        cls,
        *,
        client: Any | None = None,
        chat_model_name: str | None = None,
        client_factory: Any | None = None,
    ) -> LLMAnswerService:
        provider = str(getattr(settings, "chat_provider", "openai") or "openai").strip().lower()
        factory = client_factory or cls.openai_client
        resolved_client = client
        if resolved_client is None:
            if provider == "ollama":
                base_url = str(
                    getattr(settings, "ollama_url", "http://localhost:11434") or "http://localhost:11434"
                ).rstrip("/")
                api_key = str(getattr(settings, "ollama_api_key", "ollama") or "ollama")
                resolved_client = factory(base_url=f"{base_url}/v1", api_key=api_key)
            else:
                if not settings.openai_api_key:
                    raise ChatConfigurationError("OPENAI_API_KEY nincs beállítva (config / .env).")
                resolved_client = factory(api_key=settings.openai_api_key)
        default_model = (
            str(getattr(settings, "ollama_model", "qwen2.5:7b-instruct") or "qwen2.5:7b-instruct")
            if provider == "ollama"
            else str(getattr(settings, "chat_model", "gpt-4o-mini") or "gpt-4o-mini")
        )
        return cls(
            client=resolved_client,
            chat_model_name=str(chat_model_name or default_model),
            chat_max_tokens=max(64, int(getattr(settings, "chat_max_tokens", 220) or 220)),
            chat_temperature=float(getattr(settings, "chat_temperature", 0.2) or 0.2),
            completion_timeout_sec=max(5, int(getattr(settings, "chat_completion_timeout_sec", 45) or 45)),
            response_text_extractor=cls.extract_response_text,
        )

    def chat_completion_kwargs(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._chat_model_name,
            "messages": messages,
        }
        create_callable = getattr(getattr(getattr(self._client, "chat", None), "completions", None), "create", None)
        accepts_kwargs = False
        accepted_names: set[str] = set()
        if callable(create_callable):
            try:
                signature = inspect.signature(create_callable)
                accepted_names = set(signature.parameters.keys())
                accepts_kwargs = any(
                    parameter.kind == inspect.Parameter.VAR_KEYWORD
                    for parameter in signature.parameters.values()
                )
            except (TypeError, ValueError):
                accepts_kwargs = True
        else:
            accepts_kwargs = True
        if accepts_kwargs or "max_tokens" in accepted_names:
            payload["max_tokens"] = self._chat_max_tokens
        if self._chat_temperature >= 0 and (accepts_kwargs or "temperature" in accepted_names):
            payload["temperature"] = self._chat_temperature
        return payload

    async def complete_text(self, messages: list[dict[str, str]]) -> str:
        response = await asyncio.wait_for(
            self._client.chat.completions.create(**self.chat_completion_kwargs(messages)),
            timeout=self._completion_timeout_sec,
        )
        return self._extract_response_text(response)

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return await self.complete_text_or_message(messages)

    async def complete_text_or_message(
        self,
        messages: list[dict[str, str]],
        *,
        empty_message: str = "⚠️ Nem sikerült választ kapni a modellből.",
    ) -> str:
        try:
            answer = await self.complete_text(messages)
            if not answer:
                logger.warning("Üres válasz érkezett az LLM API-tól")
                return empty_message
            return str(answer or "")
        except RateLimitError as exc:
            logger.error("LLM rate limit hiba: %s", exc, exc_info=True)
            error_text = str(exc).lower()
            if "insufficient_quota" in error_text:
                return (
                    "⚠️ Az OpenAI API kvóta lemerült. "
                    "Ellenőrizd a számlázást, vagy állítsd a CHAT_PROVIDER=ollama értéket lokális modellhez."
                )
            return "⚠️ Túl sok kérés. Kérlek, próbáld újra később."
        except APITimeoutError as exc:
            increment_metric("llm_timeout_total", 1.0, tags={"provider": "chat_completion"})
            logger.error("LLM timeout hiba: %s", exc, exc_info=True)
            return "⚠️ A válasz túl sokáig tartott. Kérlek, próbáld újra."
        except APIConnectionError as exc:
            logger.error("LLM kapcsolati hiba: %s", exc, exc_info=True)
            return "⚠️ A lokális/remote LLM most nem elérhető. Ellenőrizd a provider URL-t és próbáld újra."
        except APIError as exc:
            logger.error("LLM API hiba: %s", exc, exc_info=True)
            return empty_message
        except asyncio.TimeoutError:
            increment_metric("llm_timeout_total", 1.0, tags={"provider": "chat_completion"})
            logger.error("LLM timeout: a modellhívás túllépte az időkorlátot.", exc_info=True)
            return "⚠️ A modell válasza túl sokáig tartott. Próbáld újra rövidebb kérdéssel."
        except Exception as exc:
            logger.error("Váratlan LLM hiba: %s", exc, exc_info=True)
            return empty_message

    async def complete_text_with_timing(
        self,
        messages: list[dict[str, str]],
        *,
        empty_message: str = "⚠️ Nem sikerült választ kapni a modellből.",
    ) -> tuple[str, float]:
        started = perf_counter()
        answer = await self.complete_text_or_message(messages, empty_message=empty_message)
        return answer, round((perf_counter() - started) * 1000.0, 2)

    async def generate_with_timing(
        self,
        messages: list[dict[str, str]],
        *,
        empty_message: str = "⚠️ Nem sikerült választ kapni a modellből.",
    ) -> tuple[str, float]:
        return await self.complete_text_with_timing(messages, empty_message=empty_message)


__all__ = ["LLMAnswerService"]
