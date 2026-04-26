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
