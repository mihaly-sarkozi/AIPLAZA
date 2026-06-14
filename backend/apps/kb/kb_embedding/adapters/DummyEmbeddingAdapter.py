from __future__ import annotations

import hashlib
import struct


class DummyEmbeddingAdapter:
    """Determinisztikus fejlesztői embedding — productionben ne legyen alapértelmezett."""

    def __init__(self, dimension: int = 1024) -> None:
        self._dimension = max(1, int(dimension))

    def embed_texts(self, texts: list[str], model: str) -> list[list[float]]:
        return [self._deterministic_vector(text) for text in texts]

    def _deterministic_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        seed = digest
        while len(values) < self._dimension:
            for idx in range(0, len(seed) - 3, 4):
                raw = struct.unpack(">I", seed[idx:idx + 4])[0]
                values.append((raw % 10000) / 10000.0 - 0.5)
                if len(values) >= self._dimension:
                    break
            seed = hashlib.sha256(seed).digest()
        return values


__all__ = ["DummyEmbeddingAdapter"]
