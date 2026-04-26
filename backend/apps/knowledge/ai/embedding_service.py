# Ez a fájl az adott terület szolgáltatás- és üzleti logikáját tartalmazza.
from __future__ import annotations

from openai import AsyncOpenAI


class EmbeddingService:
    """Egyszeru OpenAI embedding wrapper a DI kontener szamara."""

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    # Ez az aszinkron metódus a(z) embed_text logikáját valósítja meg.
    async def embed_text(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=str(text or ""),
        )
        return response.data[0].embedding

    # Ez az aszinkron metódus a(z) embed_texts logikáját valósítja meg.
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=[str(text or "") for text in texts],
        )
        return [item.embedding for item in response.data]
