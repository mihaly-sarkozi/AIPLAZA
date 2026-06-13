from __future__ import annotations

from enum import Enum


class DiscoveryStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    DETECTING_LANGUAGE = "detecting_language"
    EXTRACTING_ENTITIES = "extracting_entities"
    ENRICHING_LOCAL = "enriching_local"
    EXTRACTING_TEMPORAL = "extracting_temporal"
    EXTRACTING_SPATIAL = "extracting_spatial"
    EXTRACTING_PROCESS = "extracting_process"
    BUILDING_RELATIONSHIPS = "building_relationships"
    SCORING = "scoring"
    VALIDATING = "validating"
    READY_FOR_EMBEDDING = "ready_for_embedding"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRYABLE = "retryable"


TERMINAL_STATUSES = frozenset(
    {
        DiscoveryStatus.READY_FOR_EMBEDDING,
        DiscoveryStatus.PARTIAL,
        DiscoveryStatus.FAILED,
        DiscoveryStatus.RETRYABLE,
    }
)


__all__ = ["TERMINAL_STATUSES", "DiscoveryStatus"]
