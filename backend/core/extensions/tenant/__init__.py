"""Tenant extension alrendszer – multitenancy, demo signup, sémakezelés.

A belső szerkezet kanonikus csomagokra bomlik (a ``service.*`` útvonalak
többsége backward-compat shim):

+------------------+----------------------------------------------------------+
| Csomag           | Felelősség                                               |
+==================+==========================================================+
| ``context``      | Request-szintű tenant schema (ContextVar), snapshot DTO  |
| ``routing``      | Host→slug feloldás, cache, snapshot kodek, request state  |
| ``middleware``   | ASGI HTTP réteg (TenantMiddleware a routingra épül)      |
| ``signup``       | Demo signup orchestráció, use case-ek, publikus facade  |
| ``provisioning`` | Tenant artefaktumok létrehozása, validátor, modellek     |
| ``schema``       | Per-tenant séma életciklus, hook registry, DDL, migráció |
| ``slug``         | Demo slug policy + idempotens foglalás                   |
| ``tokens``       | Demo login JWT / URL építés                              |
| ``repositories`` | Tenant / demo signup perzisztencia                       |
| ``policies``     | Általános tenant policy-k (régi import: demo → ``slug``) |
| ``ports``        | Extension point protokollok app-moduloknak               |
| ``dto`` /        | Domain típusok, ORM                                      |
| ``models``       |                                                          |
+------------------+----------------------------------------------------------+

**Extension pointok app-moduloknak:** ``ports.py`` (TenantRepositoryPort,
TenantSchemaManagerPort, …), schema **hook** regisztráció
(``tenant.schema.hooks``), tenant lifecycle / routing a platform
``tenant_policy`` modulban.
"""
from __future__ import annotations

__all__: list[str] = []
