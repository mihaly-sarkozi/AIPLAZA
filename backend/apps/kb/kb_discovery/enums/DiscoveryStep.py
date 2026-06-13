from __future__ import annotations

from enum import Enum


class DiscoveryStep(str, Enum):
    LANGUAGE_DETECTION = "language_detection"
    ENTITY_EXTRACTION = "entity_extraction"
    LOCAL_KNOWLEDGE_ENRICHMENT = "local_knowledge_enrichment"
    RELATIONSHIP_BUILD = "relationship_build"
    KNOWLEDGE_SCORING = "knowledge_scoring"
    VALIDATION = "validation"


__all__ = ["DiscoveryStep"]
