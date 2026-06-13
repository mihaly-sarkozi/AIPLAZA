# apps/billing

A `billing` app az AIPLAZA program-specifikus előfizetés-, usage limit-, addon-, számlázási és payment integrációs modulja. Nem core/framework réteg: tenantokra, csomagokra, invoice-okra, programon belüli knowledge/chat használatra és admin billing felületekre épül.

## Fő felelősség

A modul public schema táblákban tartja a billing catalogot, tenant előfizetéseket, kérdés- és tréninghasználatot, invoice adatokat, idempotens payment eventeket és debug dátumszimulációs állapotot. A `BillingService` számolja a limiteket, kezeli a trial/active/restricted lifecycle-t, upgrade/downgrade/proration logikát, addon vásárlást, invoice PDF renderelést, verified webhookból érkező payment eventeket és háttérben futó due cycle feldolgozást.

## Fájlok

- `module.py`: `BillingAppModule`, service/repository/worker assembly, router bekötés, catalog/storage startup és settings section regisztráció.
- `router.py`: billing route kompozíció és debug route környezeti védelem.
- `api_routes.py`: owner-only billing HTTP endpointok és aláírt provider webhook endpoint rate limittel.
- `debug_routes.py`: local/staging debug dátumszimuláció és kézi billing futtatás owner jogosultsággal, külön feature flaggel, audit loggal és szigorú rate limittel.
- `schemas.py`: Pydantic request/response contractok validált plan, period, addon quantity és debug outcome mezőkkel.
- `models.py`: public schema billing ORM modellek.
- `repositories.py`: catalog, subscription, usage, invoice és debug state adat-hozzáférés.
- `catalog.py`: alap billing catalog seed sorok, plan/addon map és catalog response transzformációk.
- `calculations.py`: állapotmentes billing dátum-, időszak-, kedvezmény-, storage- és pénz helper függvények.
- `domain.py`: catalogból képzett `BillingPlan` és `BillingAddon` adatstruktúrák.
- `debug_clock.py`: dátumszimulációs clock wrapper debug billing futtatásokhoz.
- `subscription_proration.py`: csomagváltás, downgrade/scheduled change és upgrade proration kalkulációk.
- `service.py`: fő billing üzleti orchestration; a catalog, proration, tiszta kalkulációk és DTO-k már külön fájlban vannak, de továbbra is nagy blast radiusú fájl.
- `workflows.py`: subscription lifecycle, renewal, restriction, invoicing és cycle processor use case-ek.
- `payment.py`: manual, simulated és stripe_test payment gateway adapter, valamint minimális HMAC webhook signature verifier.
- `invoice_pdf.py`: ReportLab alapú invoice PDF renderer.
- `worker.py`: periodikus háttér billing cycle worker.
- `tenant_hooks.py`: tenant signup előfizetés inicializáló hook.
- `schema_hooks.py`: billing tenant schema lifecycle hook, jelenleg no-op.
- `runtime.py`, `__init__.py`: stabil exportfelületek.
- `web/module.tsx`: billing frontend route és menü regisztráció.

## Biztonság És Rate Limit

A production billing endpointok tenant contextet és auth dependencyt használnak. A módosító és fizetési jellegű műveletek `owner` szerepet kérnek, az access-status bejelentkezett usernek elérhető. Minden HTTP endpoint kapott rate limitet: olvasásnál magasabb, subscription/addon/settle és debug műveleteknél szigorúbb kerettel.

A fizetési completion webhook-first: a user által hívott `upgrade-complete` valós providernél csak állapotot kérdez le, nem futtat payment gatewayt és nem módosít subscriptiont. Subscription állapot fizetési oldalon csak verified provider webhookból, idempotensen rögzített payment event után változhat; a webhook endpoint a raw payload HMAC signature-jét ellenőrzi `BILLING_{PROVIDER}_WEBHOOK_SECRET` alapján. Kivétel a `simulated` provider (production-ben tiltott): ott nincs valós webhook, ezért az `upgrade-complete` a fizetést helyben szimulálja, azonnal aktiválja a csomagváltást és `simulated_paid` számlát ír.

A debug route-ok csak `local` és `staging` környezetben, `BILLING_DEBUG_ROUTES_ENABLED` kapcsolóval érhetők el, és minden használat strukturált audit eseményt ír. A payment provider defaultja `manual`, a Stripe teszt mód környezeti secretet igényel, a PDF renderer user/tenant szövegeket HTML escape-pel kezeli.

## Tesztfedés

Meglévő teszt fedi a simulated/manual/stripe_test payment provider ágakat és sikertelen subscription settlement viselkedést. Új célzott teszt fedi a billing request validációkat, a route rate limit dekorátorok jelenlétét és a debug route környezeti védelmét.

## Kockázatos Pontok

A `service.py` még mindig nagy, sok felelősséget hordoz, ezért csak célzott változtatással érdemes módosítani. A bontási körökben a tiszta kalkulációk, domain DTO-k, debug clock, catalog seed/transzformációk és proration logika kikerültek belőle; későbbi refaktorban az invoice creation, usage limit és warning email logikát külön use case-ekbe lehet tovább bontani. A `repositories.py` public schema raw SQL részei szintén érzékenyek, mert platform admin metrikák és tenant usage függ tőlük.

## Sárközi Mihály - 2026.05.21
