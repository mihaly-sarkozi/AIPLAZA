# core/kernel/logging

Az `logging` könyvtár a kernel logolási és observability kompatibilitási rétege. Itt van a strukturált logging konfiguráció, a JSON formatter, a request timing helper API és a security event logger; az általános observability context, metrics és event implementáció már a `core/kernel/observability` csomagban él.

## Fő felelősség

Ez a csomag biztosítja, hogy az app factory, standalone worker, HTTP middleware-ek, DB instrumentation, events worker és auth use case-ek egységesen tudjanak strukturált logot, metrikát és security eseményt írni. A logok célja, hogy Grafana/Loki, SIEM vagy hasonló loggyűjtő felé konzisztens payload menjen.

## Fájlok

- `logging_config.py`: globális Python logging konfiguráció strukturált JSON formatterrel.
- `structured_formatter.py`: LogRecordból sanitizált JSON log sort készít.
- `telemetry.py`: Sentry és OpenTelemetry runtime bootstrap best-effort módon.
- `observability.py`: kompatibilis exportfelület a `core.kernel.observability` context, events és metrics API-khoz.
- `request_timing.py`: request scope timing spanek, DB query statisztikák és request metrikák helper API-ja.
- `security_logger.py`: publikus `SecurityLogger` osztály login/logout/refresh mixinekkel.
- `security_events.py`: közös security log event emitter és severity konstansok.
- `security_payload.py`: security log payload sanitizálás.
- `security_auth_events.py`: kompatibilis gyűjtő export az auth security mixinekhez.
- `security_login_events.py`: login security események mixinje.
- `security_logout_events.py`: logout security események mixinje.
- `security_refresh_events.py`: refresh token security események mixinje.

## Kapcsolódás a nagy egészhez

Az `app/app_factory.py` konfigurálja a strukturált loggingot és runtime telemetryt. A `http` middleware-ek request/correlation ID-t, request timingot és hibametrikákat írnak. A `db` instrumentation DB query timingot rögzít, az `events` worker observability scope-pal dolgozik, az auth use case-ek pedig a `SecurityLogger` API-n keresztül írnak biztonsági eseményeket.


## Tervezési megjegyzés

Új általános observability implementációt lehetőleg a `core/kernel/observability` csomagba tegyünk. A `logging/observability.py` csak kompatibilis importfelület; hosszabb távon a modulok közvetlenül a public interface vagy az új observability réteg felé mozdíthatók.

# Sárközi Mihály - 2026.05.21