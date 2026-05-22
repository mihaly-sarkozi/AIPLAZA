# backend/apps/chat/service/llm_answer_service.py
# Feladat: LLM provider hivas, timeout es provider error mapping. A ChatService
# promptot es kontextust keszit, ez a komponens vegzi a konkret modellhivast.

from __future__ import annotations

import asyncio
import inspect
import logging
from time import perf_counter
from typing import Any

from core.kernel.interface.observability import increment_metric

try:
    from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
except Exception:  # pragma: no cover - optional dependency guard
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


__all__ = ["LLMAnswerService"]
