# AIPLAZA P0 Observability Alert Set

Ez a minimum P0 riasztási csomag a `/api/metrics` exportban lévő metrikákhoz.

## 1. 5xx arány kiugrás

- Trigger: `platform.request.count` címkék: `status_family="5xx"` aránya 5 perces ablakban > 3%.
- Cél: gyors hibaeszkaláció backend regresszió esetén.

## 2. Lassú kérés spike

- Trigger: `platform.request.latency.ms` (`path_group` bontásban) utolsó érték / aggregátum tartósan > 1500 ms.
- Cél: teljesítményromlás korai észlelése endpoint-csoport szinten.

## 3. Worker/recovery hiba arány

- Trigger: `build_failed_count`, `ingest_item_failed_count`, `platform.request.unhandled_error.count` növekedési üteme.
- Cél: ingest/index és háttérfolyamat stabilitás monitorozása.

## Metrika dimenziók (P0)

- `status_family` (`2xx`/`4xx`/`5xx`)
- `method` (`GET`/`POST`/...)
- `path_group` (pl. `auth`, `knowledge`, `billing`, `platform-admin`)

Ezek a címkék közvetlenül exportálva vannak a Prometheus kimenetben.
