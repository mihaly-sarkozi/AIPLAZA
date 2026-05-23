# backend/core/modules/tenant/signup/orchestrator_result.py
# Feladat: A demo signup orchestrator eredmény DTO-ját definiálja. Új vagy resend folyamat után szükséges user, tenant, token és email állapotadatokat hordoz. Tenant signup result contract.
# Sárközi Mihály - 2026.05.21

"""Shared result dataclass for signup use cases."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DemoSignupResult:
    slug: str
    host_hint: str
    demo_login_token: str
    created_new: bool
    resent_existing: bool = False


__all__ = ["DemoSignupResult"]
