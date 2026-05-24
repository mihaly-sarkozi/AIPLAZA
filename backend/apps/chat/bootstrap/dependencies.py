# Ez a fájl a függőség-injektálási belépési pontokat és helper függvényeket tartalmazza.
from __future__ import annotations

from apps.chat.bootstrap.service_keys import CHAT_SERVICE
from core.kernel.http.app_dependencies import module_service_dependency

get_chat_service = module_service_dependency(CHAT_SERVICE)

__all__ = ["get_chat_service"]
