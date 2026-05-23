from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

class EmbeddingProvider(Protocol):
    model_key: str
    vector_size: int

    async def embed_text(self, text: str) -> list[float]: ...
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(slots=True)
class OpenAIEmbeddingProvider:
    api_key: str
    model_key: str = "text-embedding-3-large"
    vector_size: int = 3072

    def __post_init__(self) -> None:
        try:
            from openai import AsyncOpenAI
        except Exception as exc:  # pragma: no cover - dependency/environment guard
            raise RuntimeError("OpenAI embedding providerhez telepitsd az openai csomagot.") from exc
        self._client = AsyncOpenAI(api_key=self.api_key)

    async def embed_text(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self.model_key,
            input=str(text or ""),
        )
        return list(response.data[0].embedding)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        normalized = [str(text or "") for text in texts]
        if not normalized:
            return []
        response = await self._client.embeddings.create(
            model=self.model_key,
            input=normalized,
        )
        return [list(item.embedding) for item in response.data]


class LocalBgeM3EmbeddingProvider:
    _MODEL_CACHE: dict[str, Any] = {}
    _MODEL_LOCK = Lock()

    def __init__(
        self,
        *,
        model_key: str = "BAAI/bge-m3",
        vector_size: int = 1024,
        batch_size: int = 16,
    ) -> None:
        self.model_key = model_key
        self.vector_size = int(vector_size)
        self.batch_size = max(1, int(batch_size))

    @classmethod
    def _load_model(cls, model_key: str):
        with cls._MODEL_LOCK:
            model = cls._MODEL_CACHE.get(model_key)
            if model is not None:
                return model
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except Exception as exc:  # pragma: no cover - dependency/environment guard
                raise RuntimeError(
                    "A local embedding providerhez telepitsd a sentence-transformers csomagot."
                ) from exc
            model = SentenceTransformer(model_key)
            cls._MODEL_CACHE[model_key] = model
            return model

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = " ".join(str(text or "").split())
        if len(normalized) > 12000:
            normalized = normalized[:12000]
        return normalized

    async def embed_text(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0] if vectors else [0.0] * self.vector_size

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        normalized = [self._normalize(text) for text in texts]
        if not normalized:
            return []
        model = self._load_model(self.model_key)
        vectors: list[list[float]] = []
        for start in range(0, len(normalized), self.batch_size):
            batch = normalized[start : start + self.batch_size]
            encoded = model.encode(
                batch,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            if hasattr(encoded, "tolist"):
                encoded = encoded.tolist()
            vectors.extend([list(item) for item in encoded])
        return vectors


def build_embedding_provider_from_settings(settings: Any) -> EmbeddingProvider:
    provider = str(getattr(settings, "embedding_provider", "local") or "local").strip().lower()
    model_key = str(getattr(settings, "embedding_model", "BAAI/bge-m3") or "BAAI/bge-m3").strip()
    vector_size = int(getattr(settings, "embedding_vector_size", 1024) or 1024)
    batch_size = int(getattr(settings, "embedding_batch_size", 16) or 16)
    if provider == "local":
        return LocalBgeM3EmbeddingProvider(
            model_key=model_key or "BAAI/bge-m3",
            vector_size=vector_size,
            batch_size=batch_size,
        )
    if provider == "openai":
        api_key = str(getattr(settings, "openai_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("openai_api_key kotelezo, ha EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model_key=model_key or "text-embedding-3-large",
            vector_size=vector_size,
        )
    raise ValueError(f"Ismeretlen embedding provider: {provider}")


__all__ = [
    "EmbeddingProvider",
    "LocalBgeM3EmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "build_embedding_provider_from_settings",
]
