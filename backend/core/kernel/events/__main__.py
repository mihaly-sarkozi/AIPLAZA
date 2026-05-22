# backend/core/kernel/events/__main__.py
# Feladat: Package entrypoint a standalone outbox worker futtatásához. Megtartása indokolt, mert a `python -m core.kernel.events` és Docker CMD alapú worker indítás ezt a fájlt keresi; a tényleges assembly viszont a worker_entrypoint.py-ban van. Core futtatási adapter, nem üzleti eseménylogika.
# Sárközi Mihály - 2026.05.21

"""Standalone outbox worker belépő pont.

Használat:
    INSTANCE_ROLE=worker python -m core.kernel.events

    Vagy Docker-containerben:
        CMD ["python", "-m", "core.kernel.events"]

A worker:
  1. Betölti a konfigurációt (.env / env var)
  2. Csatlakozik az adatbázishoz
  3. Felépíti az EventDispatcher-t (biztonsági audit handler-ekkel)
  4. Elindítja az OutboxWorker-t blokkoló módban
  5. SIGTERM / SIGINT hatására tisztán leáll

Szükséges env var-ok (amelyek a web-processhez is kellenek):
  DATABASE_URL, JWT_SECRET, SMTP_* (vagy .env fájl)

Worker-specifikus:
  INSTANCE_ROLE=worker
"""
from __future__ import annotations

from core.kernel.events.worker_entrypoint import build_and_run_worker_process


def _build_and_run() -> None:
    build_and_run_worker_process()


if __name__ == "__main__":
    _build_and_run()
