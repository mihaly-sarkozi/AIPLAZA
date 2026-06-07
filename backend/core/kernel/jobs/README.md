# Platform job queue (`core.kernel.jobs`)

Általános, app-független háttérfeladat-technológia a meglévő platform outbox infrastruktúrára építve.

## Szerep

| Réteg | Felelősség |
|-------|------------|
| `core.kernel.jobs` | Publikus API: job írása (`enqueue_job`), handler regisztráció (`register_job_handler`) |
| `core.kernel.events` | Outbox tárolás, worker loop, dispatcher, retry policy |
| App modulok (kb, knowledge, chat, …) | Domain-specifikus payload + handler; **csak** jobot insertálnak |

## Használat (producer)

```python
from core.kernel.jobs import enqueue_job

enqueue_job(
    "kb.understanding_requested",
    {"tenant_slug": slug, "training_item_id": item_id, ...},
    idempotency_key=f"kb.understanding_requested:{slug}:{item_id}",
)
```

## Használat (consumer / worker)

```python
from core.kernel.jobs import register_job_handler

def register_my_app_handlers(dispatcher):
    register_job_handler(dispatcher, "my.event", my_handler)
```

A standalone worker (`core.kernel.events.worker_entrypoint`) app-szintű `register_*_event_handlers` függvényeket hív.

## DI

A `platform.job_queue` kulcs (`PLATFORM_JOB_QUEUE`) a `SecurityAuditEventChannel.publish` felületet adja — ugyanaz az outbox, amit audit/email események is használnak.

## Jövő

Külön app + saját DB + memóriatároló + ütemezés később is erre a mintára építhető; a producer/consumer API változatlan maradhat.
