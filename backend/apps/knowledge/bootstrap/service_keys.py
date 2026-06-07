from __future__ import annotations

from apps.state_keys import KNOWLEDGE_SERVICE
from core.kernel.interface.app_keys import module_service_key

KNOWLEDGE_REPOSITORY = module_service_key("knowledge", "repository")
KNOWLEDGE_EMBEDDING_SERVICE_FACTORY = module_service_key("knowledge", "embedding_service.factory")
KNOWLEDGE_QDRANT_FACTORY = module_service_key("knowledge", "qdrant.factory")
__all__ = [
    "KNOWLEDGE_EMBEDDING_SERVICE_FACTORY",
    "KNOWLEDGE_QDRANT_FACTORY",
    "KNOWLEDGE_REPOSITORY",
    "KNOWLEDGE_SERVICE",
]
