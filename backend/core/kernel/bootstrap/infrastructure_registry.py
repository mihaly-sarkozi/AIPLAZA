# backend/core/kernel/bootstrap/infrastructure_registry.py
# Feladat: Az InfrastructureRegistry adatstruktúrát definiálja. Ez fogja össze a DB session factoryt, email service-t és repository registryt, hogy a runtime összeszerelés egyetlen stabil objektumon keresztül adja tovább az infrastruktúrát. Az app container, runtime lifecycle és security wiring használja, ezért általános kernel-szerződés.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass

from core.infrastructure.email.email_service import EmailService
from core.kernel.bootstrap.repository_registry import RepositoryRegistry


@dataclass(frozen=True)
class InfrastructureRegistry:
    db_session_factory: object
    email_service: EmailService
    repositories: RepositoryRegistry


__all__ = ["InfrastructureRegistry"]
