from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/legacy_facade_resolver.py
# Feladat: A legacy knowledge facade lusta feloldása az adapterekhez.
# A modul-regisztrációs sorrendtől függetlenül, hívás időben kéri le a service-t.
# Sárközi Mihály - 2026.06.11

import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_legacy_knowledge_facade() -> Any | None:
    try:
        from apps.state_keys import KNOWLEDGE_SERVICE
        from core.kernel.http.app_dependencies import get_module_service

        return get_module_service(KNOWLEDGE_SERVICE)
    except Exception:
        logger.debug("kb_crud.legacy_facade_unavailable", exc_info=True)
        return None


__all__ = ["resolve_legacy_knowledge_facade"]
