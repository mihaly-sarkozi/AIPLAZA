from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_embedding.errors.LocalEmbeddingError import LocalEmbeddingError

logger = logging.getLogger(__name__)


class LocalEmbeddingAdapter:
    """Lokális sentence-transformers embedding — dummy fallback nélkül."""

    def __init__(
        self,
        *,
        default_model: str,
        expected_dimension: int,
        device: str = "cpu",
        batch_size: int = 16,
        normalize_embeddings: bool = True,
        cache_folder: str | None = None,
    ) -> None:
        self._default_model = (default_model or "BAAI/bge-m3").strip()
        self._expected_dimension = max(1, int(expected_dimension))
        self._device = (device or "cpu").strip().lower()
        self._batch_size = max(1, int(batch_size))
        self._normalize_embeddings = bool(normalize_embeddings)
        self._cache_folder = (cache_folder or "").strip() or None
        self._model: Any = None
        self._loaded_model_name: str | None = None

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "provider": "local",
            "model": self._loaded_model_name or self._default_model,
            "device": self._device,
            "normalized": self._normalize_embeddings,
            "batch_size": self._batch_size,
        }

    def ensure_model_loaded(self, model: str | None = None) -> None:
        self._load_model(self._resolve_model(model))

    def embed_texts(self, texts: list[str], model: str) -> list[list[float]]:
        if not texts:
            return []
        resolved_model = self._resolve_model(model)
        self._load_model(resolved_model)
        safe_texts = [text if text else " " for text in texts]
        try:
            raw = self._model.encode(
                safe_texts,
                batch_size=min(self._batch_size, len(safe_texts)),
                normalize_embeddings=self._normalize_embeddings,
                show_progress_bar=False,
            )
        except Exception as exc:
            logger.exception("Local embedding generation failed (model=%s)", resolved_model)
            raise LocalEmbeddingError(
                "LOCAL_EMBEDDING_GENERATION_FAILED",
                message=str(exc),
                model=resolved_model,
            ) from exc

        vectors: list[list[float]] = []
        for embedding in raw:
            vector = [float(value) for value in embedding]
            if not vector:
                raise LocalEmbeddingError(
                    "LOCAL_EMBEDDING_GENERATION_FAILED",
                    message="empty_vector",
                    model=resolved_model,
                )
            if len(vector) != self._expected_dimension:
                raise LocalEmbeddingError(
                    "LOCAL_EMBEDDING_DIMENSION_MISMATCH",
                    message="dimension_mismatch",
                    expected=self._expected_dimension,
                    actual=len(vector),
                    model=resolved_model,
                )
            vectors.append(vector)
        return vectors

    def _resolve_model(self, model: str | None) -> str:
        candidate = (model or "").strip()
        return candidate or self._default_model

    def _load_model(self, model: str) -> None:
        if self._model is not None and self._loaded_model_name == model:
            return
        logger.info("Local embedding model loading started: %s (device=%s)", model, self._device)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise LocalEmbeddingError(
                "LOCAL_EMBEDDING_MODEL_LOAD_FAILED",
                message="sentence-transformers package is not installed",
                model=model,
            ) from exc

        kwargs: dict[str, Any] = {"device": self._device}
        if self._cache_folder:
            kwargs["cache_folder"] = self._cache_folder

        try:
            self._model = SentenceTransformer(model, **kwargs)
            self._loaded_model_name = model
        except Exception as exc:
            logger.exception("Local embedding model load failed: %s", model)
            self._model = None
            self._loaded_model_name = None
            raise LocalEmbeddingError(
                "LOCAL_EMBEDDING_MODEL_LOAD_FAILED",
                message=str(exc),
                model=model,
            ) from exc
        logger.info("Local embedding model loaded: %s", model)


__all__ = ["LocalEmbeddingAdapter"]
