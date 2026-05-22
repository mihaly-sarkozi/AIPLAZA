# backend/core/modules/tenant/service/signup/orchestrator_result.py
# Feladat: Kompatibilitási importútvonal a canonical tenant signup csomag felé. Az új implementáció a signup/ és provisioning/ csomagok alatt él, ez a fájl régi service/signup importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat shim → core.modules.tenant.signup.orchestrator_result"""
from __future__ import annotations
from core.modules.tenant.signup.orchestrator_result import *  # noqa: F403
