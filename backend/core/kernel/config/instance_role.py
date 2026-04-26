"""Instance szerepkör konfiguráció.

Meghatározza az aktuális process szerepkörét a telepítésben:

  web      – csak HTTP kéréseket szolgál ki (nincs háttérfeldolgozó)
  worker   – csak háttér-feladatokat dolgoz fel (nincs HTTP)
  combined – mindkettő (fejlesztési alapértelmezés)

Beállítása: INSTANCE_ROLE környezeti változó.

Horizontális skálázásnál:
  - A web-folyamatokon INSTANCE_ROLE=web legyen beállítva.
  - A háttérfeldolgozó-konténereken INSTANCE_ROLE=worker.
  - Fejlesztésben INSTANCE_ROLE=combined (vagy üresen hagyva).

Ez a modul szándékosan semmilyen alkalmazás-szintű függőséget nem importál –
bármely rétegből biztonságosan importálható.
"""
from __future__ import annotations

import os
from enum import Enum


class InstanceRole(str, Enum):
    """Az aktuális process szerepköre a telepítésben."""
    WEB = "web"
    WORKER = "worker"
    COMBINED = "combined"


_VALID_ROLES = {r.value for r in InstanceRole}


def get_instance_role() -> InstanceRole:
    """Visszaadja a INSTANCE_ROLE env var alapján az aktuális szerepkört.

    Ha az env var nincs beállítva, COMBINED (fejlesztési alapértelmezés).
    Érvénytelen érték esetén ValueError-t dob.
    """
    raw = (os.environ.get("INSTANCE_ROLE") or "combined").strip().lower()
    if raw not in _VALID_ROLES:
        valid = sorted(_VALID_ROLES)
        raise ValueError(
            f"INSTANCE_ROLE érvénytelen érték: {raw!r}. "
            f"Megengedett értékek: {valid}"
        )
    return InstanceRole(raw)


def is_web_process() -> bool:
    """True, ha ez a process HTTP kéréseket szolgál ki (web vagy combined mód)."""
    return get_instance_role() in {InstanceRole.WEB, InstanceRole.COMBINED}


def is_worker_process() -> bool:
    """True, ha ez a process háttérfeladatokat dolgoz fel (worker vagy combined mód)."""
    return get_instance_role() in {InstanceRole.WORKER, InstanceRole.COMBINED}


def should_run_background_workers() -> bool:
    """True, ha ebben a processben beágyazott outbox poll szál indulhat.

    Csak ``combined`` (dev): egy processben HTTP + háttér szál.

    ``web`` – nincs szál; ``worker`` – külön belépőpont (``run_blocking``),
    nem az AppContainer indít threadet (nincs dupla feldolgozás).
    """
    return get_instance_role() == InstanceRole.COMBINED


__all__ = [
    "InstanceRole",
    "get_instance_role",
    "is_web_process",
    "is_worker_process",
    "should_run_background_workers",
]
