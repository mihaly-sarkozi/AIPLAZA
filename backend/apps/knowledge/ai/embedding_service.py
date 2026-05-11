# Ez a fájl az adott terület szolgáltatás- és üzleti logikáját tartalmazza.
from __future__ import annotations

from apps.knowledge.ai.embedding_provider import OpenAIEmbeddingProvider


class EmbeddingService:
    """Egyszeru OpenAI embedding wrapper a DI kontener szamara."""

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        vector_size: int = 3072,
    ) -> None:
        self._provider = OpenAIEmbeddingProvider(
            api_key=api_key,
            model_key=model,
            vector_size=vector_size,
        )
        self._client = self._provider._client
        self._model = self._provider.model_key
        self.vector_size = self._provider.vector_size
        self.model_key = self._provider.model_key

    # Ez az aszinkron metódus a(z) embed_text logikáját valósítja meg.
    async def embed_text(self, text: str) -> list[float]:
        if not hasattr(self, "_provider"):
            response = await self._client.embeddings.create(
                model=self._model,
                input=str(text or ""),
            )
            return response.data[0].embedding
        return await self._provider.embed_text(text)

    # Ez az aszinkron metódus a(z) embed_texts logikáját valósítja meg.
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not hasattr(self, "_provider"):
            response = await self._client.embeddings.create(
                model=self._model,
                input=[str(text or "") for text in texts],
            )
            return [item.embedding for item in response.data]
        return await self._provider.embed_texts(texts)
