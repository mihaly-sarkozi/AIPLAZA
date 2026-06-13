from __future__ import annotations

from enum import Enum


class DiscoveryStep(str, Enum):
    LANGUAGE_DETECTION = "language_detection"
    ENTITY_EXTRACTION = "entity_extraction"
    LOCAL_KNOWLEDGE_ENRICHMENT = "local_knowledge_enrichment"
    TEMPORAL_EXTRACTION = "temporal_extraction"
    SPATIAL_EXTRACTION = "spatial_extraction"
    PROCESS_EXTRACTION = "process_extraction"
    RELATIONSHIP_BUILD = "relationship_build"
    KNOWLEDGE_SCORING = "knowledge_scoring"
    VALIDATION = "validation"


__all__ = ["DiscoveryStep"]
