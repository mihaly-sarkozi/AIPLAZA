from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from apps.knowledge.service.ports import KnowledgeFacadePort
from core.capabilities.users.dto import User
from core.di import RequiredTenantContextDep
from core.platform.auth.auth_dependencies import get_current_user


def get_kb_service():
    from apps.di import get_service
    from apps.knowledge.contracts import KNOWLEDGE_SERVICE

    return get_service(KNOWLEDGE_SERVICE)


get_knowledge_facade = get_kb_service

KnowledgeFacadeDep = Annotated[KnowledgeFacadePort, Depends(get_knowledge_facade)]
KnowledgeTenantDep = RequiredTenantContextDep
CurrentKnowledgeUserDep = Annotated[User, Depends(get_current_user)]

__all__ = [
    "CurrentKnowledgeUserDep",
    "KnowledgeFacadeDep",
    "KnowledgeTenantDep",
    "get_kb_service",
    "get_knowledge_facade",
]
