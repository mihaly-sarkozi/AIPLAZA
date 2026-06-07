# backend/apps/traffic/schemas/__init__.py
# Feladat: A traffic schema osztályok publikus exportfelülete. A response DTO-k külön osztályfájlokban élnek.

from apps.traffic.schemas.TrafficCatalogEntryResponse import TrafficCatalogEntryResponse
from apps.traffic.schemas.TrafficOverviewResponse import TrafficOverviewResponse
from apps.traffic.schemas.TrafficQuestionReservationResult import TrafficQuestionReservationResult
from apps.traffic.schemas.TrafficQuestionUserUsageResponse import TrafficQuestionUserUsageResponse

__all__ = [
    "TrafficCatalogEntryResponse",
    "TrafficOverviewResponse",
    "TrafficQuestionReservationResult",
    "TrafficQuestionUserUsageResponse",
]
