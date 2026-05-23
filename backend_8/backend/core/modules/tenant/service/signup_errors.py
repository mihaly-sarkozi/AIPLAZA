# backend/core/modules/tenant/service/signup_errors.py
# Feladat: Kompatibilitási importútvonal a demo signup hibákhoz. A canonical hibák a signup/errors.py alatt élnek, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

"""Backward-compat: signup hibatípusok. Canonical: ``core.modules.tenant.signup.errors``."""
from __future__ import annotations

from core.modules.tenant.signup.errors import (  # noqa: F401
    DemoAlreadyExistsError,
    DemoEmailBlockedError,
    DemoSessionRequiredError,
    InvalidSlugError,
    NameRequiredError,
    SignupError,
)

__all__ = [
    "DemoAlreadyExistsError",
    "DemoEmailBlockedError",
    "DemoSessionRequiredError",
    "InvalidSlugError",
    "NameRequiredError",
    "SignupError",
]
