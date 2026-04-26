"""Core tesztelhetőségi felület – mely részek futnak fake-kkel, mi kér DB-t / HTTP-t.

**Pure unit (stub / in-memory, minimális függőség)**

- ``core.kernel.security.startup_guards`` – env + settings objektum
- ``core.platform.auth.security_policy`` – policy validátorok
- ``core.platform.events.{dispatcher,outbox}`` – stub repository (lásd ``test_platform_event_channel``)
- ``core.platform.auth.token_service`` – JWT, mock idő opcionális
- ``core.platform.composition.ModuleContext`` – DI határok (``test_module_context_di_boundary``)
- az alkalmazásréteg PII / sanitization pipeline-jai – szöveg feldolgozás
- ``shared.*`` – chunking, hash, nyelvfelismerés (ha nincs nehéz import)

**Unit, de opcionálisan FastAPI / SQLAlchemy típusok**

- ``core.kernel.http_dependencies`` / tenant context – ``Request`` mock (``test_tenant_context_dependency``)
- ``core.extensions.tenant.service`` séma sync – fake engine (``test_tenant_schema_sync``)

**Integration (FastAPI app + TestClient vagy valós DB)**

- ``tests/integration`` – API, auth flow, repository DB, manifest smoke (``test_platform_app_factory.py``)

**Gyűjtés**

- Csak unit: ``pytest tests/unit`` (nem tölti az integration conftest app fixture-ét).
- Integration: ``pytest tests/integration``.
- Összes: ``pytest tests``.

Release / CI: unit ág ne igényeljen PostgreSQL-t; integration szolgáltatással fut.
"""

__all__: list[str] = []
