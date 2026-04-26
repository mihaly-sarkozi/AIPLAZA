"""ModuleContext.state kulcsok – bootstrap / platform belső átadás, nem DI service kulcs.

Ezek a kulcsok a kétfázisú regisztráció során kerülnek be (pl. outbox worker
referencia a lifecycle modulnak). App-modulok **ne** használjanak új, véletlenszerű
state kulcsokat publikus API-ként; ha modulok között adat kell, ``register_service``
+ ``service_keys``.
"""
from __future__ import annotations

#: OutboxWorker | None – AppContainer tölti be register_manifest_modules előtt
CTX_STATE_OUTBOX_WORKER = "outbox_worker"

#: Platform auth összerakás eredménye (belső feature bundle)
CTX_STATE_AUTH_FEATURE = "auth.feature"

#: Platform users modul feature bundle
CTX_STATE_USERS_FEATURE = "users.feature"

__all__ = [
    "CTX_STATE_AUTH_FEATURE",
    "CTX_STATE_OUTBOX_WORKER",
    "CTX_STATE_USERS_FEATURE",
]
