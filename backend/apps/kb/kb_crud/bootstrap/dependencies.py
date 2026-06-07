from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from apps.kb.kb_crud.bootstrap.service_keys import KB_CRUD_REPOSITORY
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from core.kernel.http.app_dependencies import get_module_repository


def get_knowledge_base_repository(request: Request) -> KnowledgeBaseRepository:
    return get_module_repository(KB_CRUD_REPOSITORY, request)


KnowledgeBaseRepositoryDep = Annotated[KnowledgeBaseRepository, Depends(get_knowledge_base_repository)]

__all__ = ["KnowledgeBaseRepositoryDep", "get_knowledge_base_repository"]
