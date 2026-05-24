from __future__ import annotations

from core.kernel.interface.app_keys import module_service_key

CHAT_SERVICE = module_service_key("chat")
CHAT_LLM_CLIENT_FACTORY = module_service_key("chat", "llm_client.factory")

__all__ = ["CHAT_LLM_CLIENT_FACTORY", "CHAT_SERVICE"]
