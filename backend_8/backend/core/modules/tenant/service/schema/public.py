# backend/core/modules/tenant/service/schema/public.py
# Feladat: Kompatibilitási importútvonal a canonical tenant schema csomag felé. Az új implementáció a schema/ csomag alatt él, ez a fájl régi service/schema importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat shim → core.modules.tenant.schema.public"""
from __future__ import annotations
from core.modules.tenant.schema.public import *  # noqa: F403
