"""Tenant signup typed hibatípusok.

A TenantSignupOrchestrator (és use case-ek) typed exception-öket dobnak,
a route handler ezeket kapja el és mapeli HTTP státuszkódra –
string-alapú ValueError ellenőrzések helyett.
"""
from __future__ import annotations


class SignupError(Exception):
    """Alap signup hiba."""


class DemoSessionRequiredError(SignupError):
    """Demo signup esetén session azonosító szükséges."""


class InvalidSlugError(SignupError):
    """Érvényes slug nem generálható."""


class NameRequiredError(SignupError):
    """Név megadása kötelező."""


class DemoAlreadyExistsError(SignupError):
    """Ezzel az email-lel már létezik demo tenant."""


class DemoEmailBlockedError(SignupError):
    """Ez az email cím le van tiltva (korábbi leiratkozás miatt)."""
