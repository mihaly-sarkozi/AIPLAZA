from __future__ import annotations

import logging

from core.kernel.config.config_loader import settings

logger = logging.getLogger(__name__)


class OpenAIEmbeddingAdapter:
    def __init__(self) -> None:
        api_key = str(settings.openai_api_key or "").strip()
        if not api_key:
            raise ValueError("OpenAI embedding adapter: hiányzó openai_api_key")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def embed_texts(self, texts: list[str], model: str) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(input=texts, model=model)
        return [list(item.embedding) for item in response.data]


__all__ = ["OpenAIEmbeddingAdapter"]
