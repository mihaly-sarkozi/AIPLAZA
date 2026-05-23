# backend/core/modules/tenant/middleware/resolution_service.py
# Feladat: Kompatibilitási importútvonal a tenant host resolution szolgáltatáshoz. Az új canonical implementáció a routing/resolution.py alatt él, ez a fájl régi middleware importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat: lásd ``core.modules.tenant.routing.resolution``."""
from __future__ import annotations

from core.modules.tenant.routing.resolution import *  # noqa: F403
