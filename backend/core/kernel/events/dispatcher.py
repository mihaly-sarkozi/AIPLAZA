# backend/core/kernel/events/dispatcher.py
# Feladat: Event type alapján handler függvényekhez route-olja az eseményeket. Szándékosan független az outbox tárolástól, thread modelltől és process életciklustól; csak a regisztrált handler listát kezeli és dispatch közben hibát propagál retry célra. A security bootstrap és standalone worker használja, ezért általános core event routing elem.
# Sárközi Mihály - 2026.05.21

"""Esemény dispatcher – tiszta routolási logika, szál- és folyamatfüggetlen.

Felelősség: event_type → handler(ok) leképezés és végrehajtás.

Ez a modul szándékosan független:
  - threading modelltől (handler-ek szinkron hívódnak, a hívó thread dönti el a párhuzamosságot)
  - outbox polling mechanizmustól (OutboxWorker kezeli)
  - process life cycle-tól (AppContainer vagy standalone worker script indítja)

Regisztrálás startup-kor történik (register_security_audit_handlers vagy egyéni hook).
A dispatch thread-safe az olvasás (regisztrált handler-ek ellenőrzése) szempontjából,
ha a regisztrálás az alkalmazás indulása előtt megtörténik (ami az elvárás).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

_log = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], None]


class HandlerRegistry:
    """event_type → handler callables routolása.

    Handler-ek regisztrálása startup-kor egy szálból történik;
    a dispatch(…) hívások ezt követően bármely szálból biztonságosak (read-only).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def register(self, event_type: str, handler: EventHandler) -> None:
        """Handler regisztrálása a megadott eseménytípushoz.

        Ugyanahhoz az event_type-hoz több handler is regisztrálható;
        mind sorban, kivétel esetén a soron következők is lefutnak.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def dispatch(self, event_type: str, payload: dict[str, Any]) -> None:
        """Handler-ek futtatása a megadott eseménytípusra.

        Minden handler külön try/except alatt fut; az első kivétel propagálódik
        (outbox retry), a többit naplózza. A handler-ek legyenek idempotensek,
        ha ugyanaz az esemény újrapróbálásra kerül.
        """
        handlers = self._handlers.get(event_type)
        if not handlers:
            _log.warning("Nincs regisztrált handler az eseménytípushoz: %r", event_type)
            return
        errors: list[Exception] = []
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                _log.exception("Handler hiba (event_type=%r)", event_type)
                errors.append(exc)
        if errors:
            raise errors[0]

    def has_handler(self, event_type: str) -> bool:
        """True, ha az adott event_type-hoz legalább egy handler regisztrálva van."""
        return bool(self._handlers.get(event_type))

    def registered_types(self) -> list[str]:
        """Az összes regisztrált event_type listája."""
        return list(self._handlers.keys())


class EventDispatcher(HandlerRegistry):
    """Visszafelé kompatibilis dispatcher név a HandlerRegistry fölött."""


__all__ = ["EventDispatcher", "EventHandler", "HandlerRegistry"]
