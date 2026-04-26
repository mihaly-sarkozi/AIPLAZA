"""Meghívó token typed hibatípusok.

InviteService typed exception-öket dob, a route handler ezeket kapja el
és mapeli HTTP státuszkódra – string-alapú ValueError ellenőrzések helyett.
"""
from __future__ import annotations


class InviteTokenError(Exception):
    """Alap meghívó token hiba."""


class InviteTokenExpiredError(InviteTokenError):
    """A meghívó token lejárt."""


class InviteTokenInvalidError(InviteTokenError):
    """A meghívó token érvénytelen vagy már felhasznált."""
