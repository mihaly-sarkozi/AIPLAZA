# Knowledge Ingest

## Cel

A knowledge ingest a tenant tudastarba erkezo text, file es URL inputokat ingest runokra bontja, majd workerben feldolgozza. Az API feladata a jogosultsag, quota es input validacio utan a run/item/input rekordok letrehozasa es az outbox job publikacio.

## Fobb lepesek

1. API request erkezik.
2. Tenant es user jogosultsag ellenorzes.
3. Upload/URL/text guardok lefutnak.
4. `IngestRun` letrejon.
5. `IngestItem` rekordok letrejonnek.
6. Outbox event publikacio: `knowledge.ingest_pipeline`.
7. Worker feldolgozza az itemeket.
8. Parser dokumentum, paragraph, sentence rekordok keszulnek.
9. Interpretation pipeline claim/mention/entity/semantic block/retrieval chunk adatot epit.
10. Index build kulon worker jobkent indulhat.

## Text ingest

Text inputnal az API rogzitett szoveget ad at. Meret es tenant quota ellenorzott. A parser normalizalt dokumentumszoveget keszit.

## File ingest

File inputnal az API:

- fajlszam limitet ellenoriz;
- extension/content-type/magic bytes ellenorzest vegez;
- meretlimitet nez;
- malware scan hook/failure kezelest tamogat;
- object storage-ba ment `SourceStorageService`-en keresztul;
- content hash deduplikaciot hasznal.

Object storage kulcs tenant prefixet kap:

- `tenants/{tenant}/knowledge/...`

Ez tenant izolacio szempontbol kritikus.

## URL ingest

URL inputnal az API csak a run/item/input rekordot es outbox jobot hozza letre. A letoltes worker oldalon tortenik. Security reszletek: `docs/security/url-ingest.md`.

## Status management

Az ingest run es item statuszokat az `IngestRunService` kezeli:

- run letrehozas;
- item processing;
- item failed/retry;
- progress ujraszamolas;
- completion/partial_success;
- run failed.

## Production guardok

- URL ingest csak izolalt worker mellett legyen bekapcsolva.
- Object storage productionben kotelezo, ha file ingest aktiv.
- Redis productionben kotelezo a tobb peldanyos replay/rate limit/global state miatt.
- Training MFA bekapcsolhato: `TRAINING_MFA_REQUIRED`.
- Tenant quota ellenorzi a training char/storage hasznalatot.

## Teszteles

Celzott tesztek:

- URL ingest security: `backend/tests/unit/knowledge/test_url_ingest_security.py`
- upload hardening: `backend/tests/unit/test_knowledge_api_upload_limits.py`
- source storage: `backend/tests/unit/knowledge/test_source_storage_service.py`
- ingest run status: `backend/tests/unit/knowledge/test_ingest_run_service.py`
- tenant izolacio: `backend/tests/unit/knowledge/test_tenant_isolation_api_contracts.py`
