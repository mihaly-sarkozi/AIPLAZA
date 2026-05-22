# backend/core/kernel/security/__init__.py
# Feladat: A kernel biztonsági infrastruktúra csomag belépési pontja. Runtime HTTP védelmeket, cookie/CSRF/rate limit helperöket, permission service-t és indítási konfigurációs guardokat fog össze, de nem tartalmaz auth domain flow-kat. Core security csomag, amelyből a konkrét elemek explicit almodulból importálandók.
# Sárközi Mihály - 2026.05.21

"""Kernel biztonsági csomag — edge / infrastruktúra szintű védelem.

A `core.kernel.security` modul technikai és induláskori védelmeket tartalmaz:
JWT titok erőssége, cookie Secure/SameSite, CSRF middleware, security headerek,
rate limit tároló, refresh/access TTL, valamint auth startup policy guardok.

Az auth modulban az autentikációs flow-k, token/session kezelés és auth domain
döntések maradnak. A startup konfigurációs security ellenőrzések itt élnek.
"""

from __future__ import annotations

__all__: list[str] = []
