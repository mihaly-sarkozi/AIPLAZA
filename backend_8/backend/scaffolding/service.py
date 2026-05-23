# backend/scaffolding/service.py
# Feladat: Az új app modulok minimális backend service sablonját adja. A TemplateService egy healthcheck metódussal mutatja meg, hogyan legyen saját service komponens regisztrálva és routerből használva. Scaffolding template fájl egyszerű app service indulóponthoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations


class TemplateService:
    def healthcheck(self) -> str:
        return "ok"
