# AIPLAZA Go-Live Checklist (P0)

Ez a lista a "valódi billing bekötésen kívüli" go-live minimumot foglalja össze.
Cél: 60-90 perc alatt végigfuttatható, reprodukálható release gate.

## 0) Előfeltétel (2 perc)

- A parancsokat a projekt gyökeréből futtasd: `/Users/sarkozimihaly/PycharmProjects/AIPLAZA`
- A compose stack fusson:

```bash
docker compose ps
```

Elvárt: `backend`, `frontend`, `postgres`, `qdrant`, `minio` service `Up`.

## 1) Backend release acceptance (15-25 perc)

```bash
docker compose exec backend sh -lc 'cd /app/backend && python -m pytest -m release_acceptance -v --tb=short'
```

Ha itt hiba van, go-live stop, előbb javítás.

## 2) Backend célzott regresszió (15-20 perc)

```bash
docker compose exec backend sh -lc 'cd /app/backend && python -m pytest tests/unit/knowledge/test_claim_typing.py tests/unit/test_app_knowledge_facade.py -v --tb=short'
docker compose exec backend sh -lc 'cd /app/backend && python -m pytest tests/unit -v --tb=short'
```

Megjegyzés: ha idő szűk, a második parancs mehet release utáni első körbe, de a knowledge/billing fókuszú tesztek menjenek go-live előtt.

## 3) Frontend minőségkapu (8-12 perc)

```bash
cd frontend
npm run lint
npm run build
cd ..
```

Elvárt: lint/build zöld.

## 4) Operációs smoke (10-15 perc)

Minimum manuális ellenőrzés:

- bejelentkezés + session frissítés működik
- tudásbázis létrehozás / ingest start
- chat válasz forrással
- csomagoldal és kvóta üzenetek konzisztens megjelenése
- platform admin security monitoring oldal betölt

## 5) Observability és riasztáscsatorna (8-10 perc)

- `/api/metrics` elérhető és exportálja a P0 dimenziókat (`status_family`, `method`, `path_group`)
- riasztási szabályok aktívak:
  - 5xx arány kiugrás
  - lassú kérés spike
  - worker/recovery hiba arány
- van kijelölt értesítési csatorna és felelős személy

Részletek: `OBSERVABILITY_ALERTS_P0.md`.

## 6) Backup/restore bizonyítás (15-20 perc)

Minimum igazolás:

- Postgres backup készült és visszaállítás tesztelve
- Qdrant snapshot/visszaállítás tesztelve
- object storage backup/visszaállítás tesztelve
- rollback döntési pontok röviden dokumentálva

Go-live előtt legalább egy sikeres próba legyen friss időbélyeggel.

## 7) Go/No-Go döntés (2 perc)

Go csak akkor:

- release_acceptance zöld
- frontend lint+build zöld
- operációs smoke zöld
- observability riasztáscsatorna él
- backup/restore próba sikeres

Ha bármelyik piros, `NO-GO`.

## 8) Upload body limit (kötelező)

Knowledge file ingest előtt a reverse proxy oldalon is legyen kemény body limit, különben a backendig átfolyhat túl nagy payload.

- `nginx`: `client_max_body_size 25m;`
- `Traefik`: `--entryPoints.web.transport.respondingTimeouts.readTimeout=60s` + middleware request-body limit
- `Cloudflare`: a terven felüli uploadot blokkoló WAF szabály (`Content-Length` guard) és endpoint rate limit

Megjegyzés: backend oldalon a `/api/knowledge/corpora/{corpus_uuid}/sources/file`, `/api/knowledge/corpora/{corpus_uuid}/ingest/files/estimate`, `/api/knowledge/corpora/{corpus_uuid}/ingest/files` útvonalak csomagfüggő fájl/darabszám/összméret/karakter limittel védettek.

## Gyors futtatási sorrend (ajánlott)

1. `docker compose ps`
2. backend release_acceptance
3. frontend lint/build
4. operációs smoke
5. alert/metrics ellenőrzés
6. backup/restore check
7. go/no-go döntés
