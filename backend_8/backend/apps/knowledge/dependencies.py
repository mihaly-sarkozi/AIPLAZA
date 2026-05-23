from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from apps.knowledge.service.ports import KnowledgeFacadePort
from core.modules.users.domain.dto import User
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user


def get_kb_service(request: Request):
    from core.kernel.http.app_dependencies import get_module_service
    from apps.knowledge.contracts import KNOWLEDGE_SERVICE

    return get_module_service(KNOWLEDGE_SERVICE, request)


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
