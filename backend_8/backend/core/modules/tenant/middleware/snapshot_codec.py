# backend/core/modules/tenant/middleware/snapshot_codec.py
# Feladat: Kompatibilitási importútvonal a tenant snapshot cache codec helperhez. Az új canonical implementáció a routing/snapshot_codec.py alatt él, ez a fájl régi importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat: lásd ``core.modules.tenant.routing.snapshot_codec``."""
from __future__ import annotations

from core.modules.tenant.routing.snapshot_codec import *  # noqa: F403
