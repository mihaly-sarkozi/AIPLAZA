from __future__ import annotations

# backend/apps/kb/kb_understanding/adapters/LlmCompletionAdapter.py
# Feladat: Szinkron OpenAI-kompatibilis chat-completions hívás JSON kimenettel
# (provider: openai | ollama, a chat app kliens-mintájával). A kliens lazy-init:
# első hívásnál épül fel, így a wiring nem függ az API kulcs meglététől.
# Sárközi Mihály - 2026.06.11

import json
import re
import threading
from typing import Any

from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LlmCompletionAdapter:
    def __init__(self, client: Any = None, model: str | None = None) -> None:
        self._client = client
        self._model = model
        self._lock = threading.Lock()

    def complete_json(self, *, system: str, user: str, max_tokens: int = 1500) -> Any:
        """LLM hívás; a választ JSON-ként parzolja (code fence eltávolításával)."""
        client, model = self._ensure_client()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
        except Exception as exc:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.LLM_UNAVAILABLE, retryable=True
            ) from exc
        return self._parse_json(content)

    def _ensure_client(self) -> tuple[Any, str]:
        if self._client is not None and self._model:
            return self._client, self._model
        with self._lock:
            if self._client is None or not self._model:
                self._client, self._model = self._build_from_settings()
        return self._client, self._model

    @staticmethod
    def _build_from_settings() -> tuple[Any, str]:
        from core.kernel.config.config_loader import settings

        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - dependency guard
            raise UnderstandingProcessingError(UnderstandingErrorCode.LLM_UNAVAILABLE) from exc

        provider = str(getattr(settings, "chat_provider", "openai") or "openai").strip().lower()
        if provider == "ollama":
            base_url = str(getattr(settings, "ollama_url", "http://localhost:11434") or "").rstrip("/")
            api_key = str(getattr(settings, "ollama_api_key", "ollama") or "ollama")
            client = OpenAI(base_url=f"{base_url}/v1", api_key=api_key)
            model = str(getattr(settings, "ollama_model", "") or "")
        else:
            api_key = str(getattr(settings, "openai_api_key", "") or "")
            if not api_key:
                raise UnderstandingProcessingError(UnderstandingErrorCode.LLM_UNAVAILABLE)
            client = OpenAI(api_key=api_key)
            model = str(getattr(settings, "chat_model", "") or "")
        if not model:
            raise UnderstandingProcessingError(UnderstandingErrorCode.LLM_UNAVAILABLE)
        return client, model

    @staticmethod
    def _parse_json(content: str) -> Any:
        text = _JSON_FENCE.sub("", content.strip()).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Beágyazott JSON objektum / tömb kivágása, ha az LLM körítést adott.
            for opening, closing in (("{", "}"), ("[", "]")):
                start = text.find(opening)
                end = text.rfind(closing)
                if 0 <= start < end:
                    try:
                        return json.loads(text[start : end + 1])
                    except json.JSONDecodeError:
                        continue
            raise UnderstandingProcessingError(UnderstandingErrorCode.LLM_UNAVAILABLE, retryable=True)


__all__ = ["LlmCompletionAdapter"]
