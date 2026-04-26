"""Core platform csomag.

Stabil, publikus API (app-moduloknak)
======================================
  core.platform.contract  – Az EGYETLEN ajánlott importálási pont app-modulok számára.
                             Tartalmaz: AppModule, ModuleContext, RouteRegistration,
                             lifecycle hook típusokat.

  core.platform.service_keys – Service kulcs konstansok (platform-only).

  core.platform.composition  – AppModule és ModuleContext implementációja.

  core.platform.manifest     – AppManifest és PlatformManifest.

Belső implementáció (ne importálj közvetlenül app-modulokból)
==============================================================
  core.platform.bootstrap.*   – indítási infrastruktúra (AppContainer, SecurityRegistry, stb.)
  core.platform.runtime.*     – runtime wiring (belső bootstrap)
  core.platform.auth.*        – token service, allowlist, password policy (platform auth belső)
  core.platform.events.*      – outbox, event_channel, worker (event pipeline belső)
  core.platform.brand.*       – brand belső implementáció
  core.platform.domain.*      – domain belső implementáció
  core.platform.lifecycle.*   – lifecycle belső implementáció
  core.platform.settings.*    – settings belső implementáció
  core.platform.permissions.* – permission service belső implementáció
  core.platform.registry      – platform manifest factory (belső bootstrap)
  core.platform.composition   – közvetlenül is importálható, de a contract ajánlott

App-modul fejlesztési útmutató
================================
  1. Importálj a minimális `core.platform.contract` API-ból vagy a
     `core.platform.contract.keys` / `core.platform.service_keys` modulokból.
  2. Deklaráld service_dependencies() a kötelező platform service-eidet.
  3. Használd ctx.clock, ctx.session_factory, ctx.user_repository typed property-ket
     a raw string lookup-ok helyett.
  4. Regisztrálj "module.{domain}.*" kulccsal (ne "platform.*" – az a core-é).
  5. Permissions konvenció: "domain.action" (pl. "knowledge.read").

  Példa:
      from core.platform.contract import AppModule, ModuleContext
      class MyModule(AppModule):
          key = "app.my_domain"
          def service_dependencies(self): return (...)
          def register(self, ctx: ModuleContext): ...
"""
