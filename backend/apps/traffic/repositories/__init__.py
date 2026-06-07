# backend/apps/traffic/repositories/__init__.py
# Feladat: A traffic repository réteg publikus exportfelülete. Innen importálható a forgalmi read repository.

from apps.traffic.repositories.TrafficRepository import TrafficRepository
from apps.traffic.repositories.TrafficQuestionUsageRepository import TrafficQuestionUsageRepository

__all__ = ["TrafficQuestionUsageRepository", "TrafficRepository"]
