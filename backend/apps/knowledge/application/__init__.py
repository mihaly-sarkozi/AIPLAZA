# backend/apps/knowledge/application/__init__.py
# Feladat: A knowledge modul application service rétegének publikus belépési pontja. Itt indul a facade-ból fokozatosan leválasztott use-case orchestration, hogy a router és a domain/perzisztencia réteg között ne egy mindentudó osztály legyen az egyetlen közvetítő. Program-specifikus knowledge application boundary.
# Sárközi Mihály - 2026.05.22

from apps.knowledge.application.ingest_application_service import (
    IngestQueueUnavailableError,
    KnowledgeIngestApplicationService,
)

__all__ = [
    "IngestQueueUnavailableError",
    "KnowledgeIngestApplicationService",
]
