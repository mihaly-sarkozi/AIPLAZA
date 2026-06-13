from __future__ import annotations

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer


class EntityNormalizer:
    def __init__(self) -> None:
        self._normalizer = TextNormalizer()

    def normalize_name(self, name: str) -> str:
        return self._normalizer.normalize(name)


__all__ = ["EntityNormalizer"]
