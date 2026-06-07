# backend/apps/traffic/router/__init__.py
# Feladat: A traffic router réteg publikus exportfelülete. Innen importálható a FastAPI router.

from apps.traffic.router.TrafficRouter import get_traffic_service, router

__all__ = ["get_traffic_service", "router"]
