# Outbox Worker

## Cel

Az outbox worker a web requesttol levallasztott hattermunkakat futtatja. A web/API process gyorsan rogzit eventet, a worker pedig lease, retry, heartbeat es dead-letter szabalyokkal dolgozza fel.

## Process szerepek

- `INSTANCE_ROLE=web`: HTTP app, normal esetben nem futtat hosszu worker loopot.
- `INSTANCE_ROLE=worker`: hattermunkak futtatasa.
- `OUTBOX_WORKER_LOOP_ENABLED`: worker loop explicit kapcsoloja standalone workerben.
- `BILLING_WORKER_LOOP_ENABLED`: billing worker explicit kapcsoloja.

## Event policy

Az event policy donti el:

- timeout;
- lease hossz;
- heartbeat gyakorisag;
- max retry;
- `execution_mode`.

Rovid eventek `inline_thread` modban futhatnak. Hosszu knowledge jobok policy szinten `process` modot kapnak:

- `knowledge.ingest_pipeline`
- `knowledge.index_build`

Ha a teljes process executor meg nincs bekotve, a policy akkor is elkuloniti ezeket a rovid timeoutu eventektol, es metrikazott fallback hasznalhato.

## Megbizhatosagi szabalyok

- Egy jobot lease ved, hogy parhuzamos worker ne vigye ugyanazt.
- Lease expiry utan masik worker ujra felveheti.
- Max attempt utan dead-letter.
- Hosszu job heartbeatet kuld.
- Idempotency key kotelezo a duplikalt publikacio csokkentesere.

## Observability

Internal endpoint:

- `GET /internal/health/outbox`

Vedett endpoint, nem publikus. `require_internal_admin()` kell hozza, rate limitelt es auditolt.

Snapshot mezok:

- pending;
- running;
- failed;
- dead_letter;
- stuck_leases;
- oldest_pending_seconds;
- average_attempts;
- worker heartbeat/status.

## Production checklist

- Worker kontener kulon deployolva.
- Redis elerheto, ha a rate limit/replay/global state ezt igenyli.
- Outbox queue readiness check zold.
- `/internal/*` endpointok service tokennel vagy internal IP allowlisttel vedve.
- Dead-letter es stuck lease metrikak alertelve.
