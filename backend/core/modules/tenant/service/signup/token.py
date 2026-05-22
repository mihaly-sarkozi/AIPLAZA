# backend/core/modules/tenant/service/signup/token.py
# Feladat: Kompatibilitási importútvonal a canonical tenant signup csomag felé. Az új implementáció a signup/ és provisioning/ csomagok alatt él, ez a fájl régi service/signup importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat shim → ``core.modules.tenant.tokens.demo_jwt``."""
from __future__ import annotations

from core.modules.tenant.tokens.demo_jwt import *  # noqa: F403
