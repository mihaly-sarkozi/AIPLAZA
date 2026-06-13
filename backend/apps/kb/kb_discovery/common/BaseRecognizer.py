from __future__ import annotations

from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext


class BaseRecognizer:
    name: str = "base"
    version: str = "1.0"

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        raise NotImplementedError


__all__ = ["BaseRecognizer"]
