"""Infrastruktúra összeállítás: adatbázis session factory, email, repository-k."""
from __future__ import annotations

from core.platform.bootstrap.infrastructure import InfrastructureRegistry, build_infrastructure


def assemble_infrastructure() -> InfrastructureRegistry:
    """Felépíti és visszaadja az InfrastructureRegistry-t (DB + email + repo-k)."""
    return build_infrastructure()
