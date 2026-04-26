"""Runtime assembly egységek – AppContainer belső felépítése.

Az AppContainer nem tartalmazza közvetlenül az összeállítási lépéseket;
delegál ezekhez a modulokhoz:

  - infrastructure_assembly  – DB, email, core repository-k
  - security_assembly          – audit, outbox repo, token, event channel, dispatcher
  - manifest_assembly        – platform + app manifest merge
  - permissions_assembly       – PermissionService a manifest permissions alapján
  - outbox_wiring            – OutboxWorker összekötése (async audit pipeline)
  - module_registration      – kétfázisú modul regisztráció
  - kernel_di                – core.di kernel függőségek
  - runtime_lifecycle        – storage init, worker start/stop, státusz

A publikus API továbbra is ``core.platform.runtime.AppContainer``.
"""
from __future__ import annotations

__all__: list[str] = []
