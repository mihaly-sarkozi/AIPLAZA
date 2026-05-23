# core/kernel/observability

Az `observability` könyvtár a kernel általános megfigyelhetőségi implementációs magja. Itt él a request/worker kontextus, a strukturált event logolás, a payload sanitizálás, az in-memory metrika registry és a Prometheus renderelés.

## Fő felelősség

Ez a csomag adja azokat az alacsony szintű építőelemeket, amelyekre a `logging` csomag, a HTTP middleware-ek, a DB instrumentation, az events worker és az app modulok observability wrapperjei építenek. Nem FastAPI-specifikus, és nem tartalmaz üzleti logikát.

## Fájlok

- `__init__.py`: csomagjelölő az observability implementációkhoz.
- `context.py`: ContextVar alapú correlation, request, tenant, user és worker kontextus.
- `events.py`: strukturált event és exception log emitter.
- `payload.py`: default log context, JSON-biztosítás és payload sanitizálás.
- `metric_registry.py`: thread-safe in-memory metric registry és metric series modell.
- `metrics.py`: globális metrika helper API increment, observe, snapshot, reset és render műveletekkel.
- `prometheus_renderer.py`: registry tartalom Prometheus text format exportja.
- `sinks.py`: opcionális külső observability sink interfészek.

## Kapcsolódás a nagy egészhez

A `logging/observability.py` kompatibilitási façade innen re-exportálja a context, events és metrics API-kat a régi importútvonalhoz. A `logging/structured_formatter.py` a `payload.py` helperjeit használja, a lifecycle/monitoring endpoint pedig a Prometheus renderelésen keresztül tud metrikát szolgáltatni.


## Tervezési megjegyzés

Ide kerüljenek az általános observability implementációk. A `logging` könyvtár maradjon a Python logging konfiguráció, formatter és security logger helye; a modulok felé tartós public felületet vagy a `core.kernel.interface.observability`, vagy a kompatibilis `core.kernel.logging.observability` adjon.

# Sárközi Mihály - 2026.05.21