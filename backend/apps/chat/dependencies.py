# Ez a fájl a függőség-injektálási belépési pontokat és helper függvényeket tartalmazza.
from __future__ import annotations

from apps.di import module_service_dependency
from apps.contracts.service_keys import MODULE_CHAT_SERVICE

get_chat_service = module_service_dependency(MODULE_CHAT_SERVICE)

__all__ = ["get_chat_service"]
