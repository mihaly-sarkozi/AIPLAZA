from __future__ import annotations

from typing import Any, Mapping

from apps.knowledge.service.facade_runtime import KnowledgeFacadeRuntime
from apps.knowledge.service.facade_wiring import build_knowledge_facade_runtime


def build_knowledge_facade_from_init(
    owner: Any,
    init_args: Mapping[str, Any],
) -> KnowledgeFacadeRuntime:
    dependencies = {key: value for key, value in init_args.items() if key != "self"}
    return build_knowledge_facade_runtime(owner, **dependencies)


__all__ = ["build_knowledge_facade_from_init"]
