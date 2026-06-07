# backend/apps/traffic/service/__init__.py
# Feladat: A traffic service réteg publikus exportfelülete. Innen importálható a TrafficService application service.

from apps.traffic.service.TrafficService import TrafficService

__all__ = ["TrafficService"]
