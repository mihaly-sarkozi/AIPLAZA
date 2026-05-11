"""App service key contract.

Canonical location for module-scoped service keys. Core must not import this
package.
"""
from __future__ import annotations


def module_service_key(domain: str, suffix: str = "service") -> str:
    domain_slug = (domain or "").strip().lower()
    if not domain_slug:
        raise ValueError("domain must not be empty")
    return f"module.{domain_slug}.{suffix}"


MODULE_KNOWLEDGE_SERVICE = module_service_key("knowledge")
MODULE_KNOWLEDGE_REPOSITORY = module_service_key("knowledge", "repository")
MODULE_KNOWLEDGE_EMBEDDING_SERVICE_FACTORY = module_service_key("knowledge", "embedding_service.factory")
MODULE_KNOWLEDGE_QDRANT_FACTORY = module_service_key("knowledge", "qdrant.factory")
MODULE_KNOWLEDGE_EVENT_CHANNEL = module_service_key("knowledge", "event_channel")

MODULE_CHAT_SERVICE = module_service_key("chat")
MODULE_CHAT_LLM_CLIENT_FACTORY = module_service_key("chat", "llm_client.factory")

MODULE_TRAFFIC_SERVICE = module_service_key("traffic")
MODULE_ORDERS_SERVICE = module_service_key("orders")
MODULE_PACKAGES_SERVICE = module_service_key("packages")
MODULE_DEMO_SERVICE = module_service_key("demo")
MODULE_PROFILE_SERVICE = module_service_key("profile")
MODULE_SETTINGS_SERVICE = module_service_key("settings")

__all__ = [
    "MODULE_CHAT_LLM_CLIENT_FACTORY",
    "MODULE_CHAT_SERVICE",
    "MODULE_DEMO_SERVICE",
    "MODULE_KNOWLEDGE_EMBEDDING_SERVICE_FACTORY",
    "MODULE_KNOWLEDGE_EVENT_CHANNEL",
    "MODULE_KNOWLEDGE_QDRANT_FACTORY",
    "MODULE_KNOWLEDGE_REPOSITORY",
    "MODULE_KNOWLEDGE_SERVICE",
    "MODULE_ORDERS_SERVICE",
    "MODULE_PACKAGES_SERVICE",
    "MODULE_PROFILE_SERVICE",
    "MODULE_SETTINGS_SERVICE",
    "MODULE_TRAFFIC_SERVICE",
    "module_service_key",
]
