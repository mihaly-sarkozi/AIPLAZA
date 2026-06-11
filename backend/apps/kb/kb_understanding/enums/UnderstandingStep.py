from __future__ import annotations

# backend/apps/kb/kb_understanding/enums/UnderstandingStep.py
# Feladat: A megértési pipeline 10 lépésének kanonikus felsorolása (futási sorrendben).
# Sárközi Mihály - 2026.06.11

from enum import Enum


class UnderstandingStep(str, Enum):
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    STRUCTURE_DETECTION = "structure_detection"
    CHUNKING = "chunking"
    ENTITY_EXTRACTION = "entity_extraction"
    KNOWLEDGE_ENRICHMENT = "knowledge_enrichment"
    EMBEDDING = "embedding"
    RELATIONSHIP_BUILD = "relationship_build"
    KNOWLEDGE_SCORING = "knowledge_scoring"
    VALIDATION = "validation"


__all__ = ["UnderstandingStep"]
