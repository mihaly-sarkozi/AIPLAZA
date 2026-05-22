# backend/core/modules/tenant/middleware/request_state.py
# Feladat: Kompatibilitási importútvonal a tenant request state helperhez. Az új canonical implementáció a routing/request_state.py alatt él, ez a fájl régi importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat: lásd ``core.modules.tenant.routing.request_state``."""
from __future__ import annotations

from core.modules.tenant.routing.request_state import *  # noqa: F403
