# apps/knowledge/service

A `service` könyvtár a knowledge modul program-specifikus application és domain orchestration rétege. A `KnowledgeFacade` még kompatibilitási belépési pont, de az új fejlesztéseknek fokozatosan kisebb use-case service-ekbe kell kerülniük.

## Service Boundaryk

- `corpus_permission_service.py`: corpus listázás, use/train jogosultsági döntések és permission nézetek. Ez a tenant/user határt védi, ezért izoláltan tesztelendő.
- `url_fetch_service.py`: URL ingest célvalidáció, HEAD elérhetőség és biztonságos letöltés/HTML strip. Ez az SSRF/DNS/redirect/content-type boundaryt tartja távol a facade orchestrationtől.
- `knowledge_trace_service.py`: ingest trace és diagnosztikai nézet építés.
- `knowledge_facade.py`: legacy kompatibilitási facade; új felelősséget csak delegálással kapjon.

## Következő Bontási Célok

Az ingest run/item, source storage, document parser, chunking, embedding, index build, retrieval, feedback és lineage felelősségeket külön service-ekbe kell továbbvinni. A cél, hogy a facade vékony adapterré váljon, amely stabil API-t tart fenn a routerek felé, de nem hordoz üzleti állapotgépeket.

## Sárközi Mihály - 2026.05.22
