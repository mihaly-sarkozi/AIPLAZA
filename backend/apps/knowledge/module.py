from __future__ import annotations

from apps.knowledge.bootstrap.app_module import KnowledgeModule as _KnowledgeModule
from core.kernel.interface import BaseAppModule


class KnowledgeModule(_KnowledgeModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return KnowledgeModule()


__all__ = ["KnowledgeModule", "get_module"]
