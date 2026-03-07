# apps/audit/application/audit_service.py
# Teljes audit log: belépés (siker/sikertelen), 2FA, kilépés, refresh, user CRUD.
# A service maga sanitizál: érzékeny adat soha nem kerül a tárolóba.
#
# FONTOS – szinkron írás: ez az osztály közvetlenül _repo.append()-et hív (blokkoló DB írás).
# A request path-on NEM ezt kell használni. A container audit_events_async=True esetén a
# SecurityAuditEventChannel AuditServiceProxy-ját injektálja (queue.put); a worker hívja
# meg ezt a valódi AuditService.log()-ot. Így az auth/request latency-ből nem eszik az audit.
# Ha ezt a class-t közvetlenül kapná a route/service, az audit írás benne maradna a kérésben.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
import json
from typing import Optional, Any

from apps.audit.ports import AuditRepositoryInterface
from apps.audit.sanitization import sanitize_details


class AuditService:
    """
    Szinkron audit írás: egy táblába írja az eseményeket (tenant sémában). Minden log() DB írás.
    Használat: általában a channel worker hívja; a request path-on a proxy (event_channel.audit_service)
    kerül injektálásra, ami csak queue-ba tesz, így a kérés nem vár az audit írásra.
    """

    def __init__(self, repo: AuditRepositoryInterface):
        self._repo = repo

    def log(
        self,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Egy esemény rögzítése (szinkron DB írás). details sanitizálás után JSON stringként tároljuk."""
        safe_details = sanitize_details(details)
        details_str = json.dumps(safe_details, ensure_ascii=False) if safe_details else None
        # Szinkron írás – request path-on ne ezt a service-t hívd, hanem a channel proxy-t (queue).
        self._repo.append(
            action=action,
            user_id=user_id,
            details=details_str,
            ip=ip,
            user_agent=user_agent,
        )
