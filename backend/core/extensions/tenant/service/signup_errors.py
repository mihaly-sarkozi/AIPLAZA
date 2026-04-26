"""Backward-compat: signup hibatípusok. Canonical: ``core.extensions.tenant.signup.errors``."""
from __future__ import annotations

from core.extensions.tenant.signup.errors import (  # noqa: F401
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
