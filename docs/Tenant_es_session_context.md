# Tenant ismeretlen a hostból – mi történik?

## Cél

Ne legyen sémák közötti adatszivárgás: **soha** ne használjunk másik (pl. default) sémát, ha a tenant nem ismert. Ha a hostból nem derül ki a tenant, a kérés 400/404-gyel zárul, vagy a session nyitás explicit hibát dob.

---

## Mikor nem ismert a tenant?

| Eset | Middleware viselkedés |
|------|------------------------|
| **Nincs Host header** | `/api` kérésnél → **400** „Tenant hiányzik”. Nem /api → továbbadás (pl. docs). |
| **Host nincs leképezve** (pl. `127.0.0.1` nincs domain2tenant-ben) | `/api` kérésnél → **400** „Tenant hiányzik. Használd a céges aldomaint (pl. http://demo.local:8001).” |
| **Slug ismert, de a tenant nincs a DB-ben** | **404** „Ismeretlen vagy nem létező tenant.” |
| **Tenant inaktív** | **403** „A tenant jelenleg nem aktív.” |

Tehát **tenant-scoped route-ot** (users, auth, settings, kb, chat) csak akkor érsz el, ha a middleware beállította a `tenant_slug`-ot és a `current_tenant_schema`-t.

---

## Session factory (tenant ismert vs nem)

- **Ha `current_tenant_schema` be van állítva** (pl. `"demo"`): `SET search_path TO "demo"` → tenant-scoped táblák (users, sessions, stb.).
- **Ha üres** (pl. middleware executor szál, ahol még nincs tenant context): `SET search_path TO public`. A **public** sémában csak a tenant lista (tenants, tenant_domains, tenant_configs) van – **nincs** user/audit adat, így nincs sémák közötti adatszivárgás. A middleware így tudja lekérni a tenantot host alapján.
- **Nincs „default tenant” fallback:** soha nem állítunk másik tenant sémát (pl. demo) ha a tenant nem ismert; csak public (globális táblák) vagy konkrét tenant séma.

---

## Sync route és context var

A middleware a **main** szálban állítja a `current_tenant_schema`-t. A **sync** route viszont **thread pool**-ban fut, ahol a context var alapból üres. Ezért:

- Minden **tenant-scoped router** (auth, users, settings, knowledge, chat) használja a **`Depends(set_tenant_context_from_request)`** dependency-t, ami a route szálában `request.state.tenant_slug` → `current_tenant_schema.set(slug)`.
- Így a session factory ugyanabban a szálban látja a sémát; **nem** kell és **nem** szabad default/fallback sémát használni.

Ha üres a schema (pl. middleware executor szál, vagy dependency nélküli public-only hívás), a session `search_path` public-ra áll – csak a tenant lista (tenants, tenant_domains) érhető, nem tenant-scoped user adat.

---

## Összefoglaló

| Kérdés | Válasz |
|--------|--------|
| Mi van, ha nem ismert a hostból a tenant? | /api-nál 400 vagy 404; nem jutunk el tenant-scoped DB hívásig. |
| Default/fallback séma? | **Nincs.** Cél: zero adatszivárgás séma között. |
| Session schema nélkül? | `search_path = public` (tenant lista); tenant-scoped adat csak schema beállítva esetén. |
