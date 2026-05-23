# core/kernel/events

Az `events` könyvtár a kernel általános, perzisztens eseménykezelő infrastruktúrája. Nem üzleti domain eseményeket definiál, hanem azt a framework réteget, amely request pathból outboxba ír, háttér workerrel feldolgoz, és handler-ekhez dispatchol.

## Fő felelősség

Ez a csomag az outbox pattern központi megvalósítása. A web process csak eseményt publikál (`event_channel.py`, `event_proxies.py`), a tárolást az outbox repository végzi (`outbox.py`), a feldolgozást pedig az `OutboxWorker` és a hozzá tartozó worker loop intézi (`worker.py`, `worker_loop.py`).

## Fájlok

- `__init__.py`: lazy publikus exportfelület a gyakori event komponensekhez.
- `__main__.py`: megtartandó package entrypoint a `python -m core.kernel.events` worker indításhoz.
- `dispatcher.py`: event type alapján regisztrált handler-ekhez route-olja az eseményeket.
- `event_channel.py`: request pathból outboxba írja a security, audit és email eseményeket.
- `event_payload.py`: observability, tenant, user és instance role metadatával gazdagítja a payloadot.
- `event_proxies.py`: service proxyk, amelyek a hívásokat outbox eseményekké alakítják.
- `handlers.py`: beépített security, audit és email handler factory-k és regisztráció.
- `outbox.py`: outbox repository publikus műveletei.
- `outbox_models.py`: outbox ORM modell és worker snapshot dataclass.
- `outbox_queries.py`: claim és work item query helper logika.
- `outbox_sql.py`: outbox tábla telepítő és upgrade SQL.
- `worker.py`: `OutboxWorker` életciklus, thread és blocking futtatás.
- `worker_loop.py`: polling, batch feldolgozás, timeoutos dispatch és retry állapotkezelés.
- `worker_policy.py`: event típusonkénti timeout, lease és heartbeat policy.
- `worker_entrypoint.py`: standalone worker process assembly.

## Kapcsolódás a nagy egészhez

A `bootstrap/security.py` építi fel a security audit event channel-t és regisztrálja a beépített handler-eket. A runtime wiring és lifecycle modulok gondoskodnak arról, hogy combined módban worker szál indulhasson, dedikált worker processben pedig a `python -m core.kernel.events` belépőpont futtassa a loopot.

## Production Operáció

Az outbox worker nem egyetlen globális timeouttal dolgozik: audit/email események rövid, knowledge ingest/index jobok hosszabb policyt kapnak. A claim során lease mezők töltődnek (`leased_by`, `lease_until`, `last_heartbeat_at`, `started_at`), hosszú handler alatt heartbeat hosszabbítja a lease-t. Ha a worker meghal, a lejárt lease alapján másik worker újra felveheti a sort.

Sikertelen handler esetén retry/backoff történik. A max próbálkozás után a sor `dead_letter` státuszba kerül, `last_error` és `finished_at` mezőkkel. A `PlatformEventOutboxRepository.queue_snapshot()` alap observability adatokat ad: status szerinti darabszám, pending/running/failed/dead-letter jobs, oldest pending age, stuck leases és átlagos attempt count.

# Sárközi Mihály - 2026.05.22