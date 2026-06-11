from __future__ import annotations

# backend/apps/kb/kb_crud/bootstrap/dependencies.py
# Feladat: CRUD use-case service példányok összeállítása (FastAPI Depends).
# Sárközi Mihály - 2026.06.07

from fastapi import Request

from apps.kb.kb_crud.bootstrap.service_keys import (
    KB_CRUD_AUDIT_LOGGER,
    KB_CRUD_CONTENT_CLEANUP,
    KB_CRUD_PERMISSION_REPOSITORY,
    KB_CRUD_REPOSITORY,
    KB_CRUD_STORAGE_METRICS,
    KB_CRUD_TRAINING_SUMMARY,
    KB_CRUD_USAGE_LIMIT,
    KB_CRUD_USER_DIRECTORY,
)
from apps.kb.kb_crud.service.CreateKnowledgeBaseService import CreateKnowledgeBaseService
from apps.kb.kb_crud.service.DeleteKnowledgeBaseService import DeleteKnowledgeBaseService
from apps.kb.kb_crud.service.GetKnowledgeBasePermissionsService import GetKnowledgeBasePermissionsService
from apps.kb.kb_crud.service.GetKnowledgeBaseService import GetKnowledgeBaseService
from apps.kb.kb_crud.service.GetPermissionsBatchService import GetPermissionsBatchService
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.ListKnowledgeBasesService import ListKnowledgeBasesService
from apps.kb.kb_crud.service.SetKnowledgeBasePermissionsService import SetKnowledgeBasePermissionsService
from apps.kb.kb_crud.service.UpdateKnowledgeBaseService import UpdateKnowledgeBaseService
from core.kernel.http.app_dependencies import get_module_repository


def get_kb_access_policy(request: Request) -> KbAccessPolicy:
    return KbAccessPolicy(
        get_module_repository(KB_CRUD_REPOSITORY, request),
        get_module_repository(KB_CRUD_PERMISSION_REPOSITORY, request),
    )


def get_create_knowledge_base_service(request: Request) -> CreateKnowledgeBaseService:
    return CreateKnowledgeBaseService(
        repository=get_module_repository(KB_CRUD_REPOSITORY, request),
        permission_repository=get_module_repository(KB_CRUD_PERMISSION_REPOSITORY, request),
        usage_limit=get_module_repository(KB_CRUD_USAGE_LIMIT, request),
        audit=get_module_repository(KB_CRUD_AUDIT_LOGGER, request),
    )


def get_list_knowledge_bases_service(request: Request) -> ListKnowledgeBasesService:
    return ListKnowledgeBasesService(
        repository=get_module_repository(KB_CRUD_REPOSITORY, request),
        access_policy=get_kb_access_policy(request),
        training_summary=get_module_repository(KB_CRUD_TRAINING_SUMMARY, request),
        storage_metrics=get_module_repository(KB_CRUD_STORAGE_METRICS, request),
    )


def get_get_knowledge_base_service(request: Request) -> GetKnowledgeBaseService:
    return GetKnowledgeBaseService(
        repository=get_module_repository(KB_CRUD_REPOSITORY, request),
        access_policy=get_kb_access_policy(request),
        training_summary=get_module_repository(KB_CRUD_TRAINING_SUMMARY, request),
        storage_metrics=get_module_repository(KB_CRUD_STORAGE_METRICS, request),
    )


def get_update_knowledge_base_service(request: Request) -> UpdateKnowledgeBaseService:
    return UpdateKnowledgeBaseService(
        repository=get_module_repository(KB_CRUD_REPOSITORY, request),
        access_policy=get_kb_access_policy(request),
        audit=get_module_repository(KB_CRUD_AUDIT_LOGGER, request),
    )


def get_delete_knowledge_base_service(request: Request) -> DeleteKnowledgeBaseService:
    return DeleteKnowledgeBaseService(
        repository=get_module_repository(KB_CRUD_REPOSITORY, request),
        access_policy=get_kb_access_policy(request),
        content_cleanup=get_module_repository(KB_CRUD_CONTENT_CLEANUP, request),
        training_summary=get_module_repository(KB_CRUD_TRAINING_SUMMARY, request),
        audit=get_module_repository(KB_CRUD_AUDIT_LOGGER, request),
    )


def get_kb_permissions_service(request: Request) -> GetKnowledgeBasePermissionsService:
    return GetKnowledgeBasePermissionsService(
        permission_repository=get_module_repository(KB_CRUD_PERMISSION_REPOSITORY, request),
        user_directory=get_module_repository(KB_CRUD_USER_DIRECTORY, request),
        access_policy=get_kb_access_policy(request),
    )


def get_kb_permissions_batch_service(request: Request) -> GetPermissionsBatchService:
    return GetPermissionsBatchService(
        permission_repository=get_module_repository(KB_CRUD_PERMISSION_REPOSITORY, request),
        user_directory=get_module_repository(KB_CRUD_USER_DIRECTORY, request),
        access_policy=get_kb_access_policy(request),
    )


def get_set_kb_permissions_service(request: Request) -> SetKnowledgeBasePermissionsService:
    return SetKnowledgeBasePermissionsService(
        repository=get_module_repository(KB_CRUD_REPOSITORY, request),
        permission_repository=get_module_repository(KB_CRUD_PERMISSION_REPOSITORY, request),
        user_directory=get_module_repository(KB_CRUD_USER_DIRECTORY, request),
        access_policy=get_kb_access_policy(request),
        audit=get_module_repository(KB_CRUD_AUDIT_LOGGER, request),
    )


__all__ = [
    "get_create_knowledge_base_service",
    "get_delete_knowledge_base_service",
    "get_get_knowledge_base_service",
    "get_kb_access_policy",
    "get_kb_permissions_batch_service",
    "get_kb_permissions_service",
    "get_list_knowledge_bases_service",
    "get_set_kb_permissions_service",
    "get_update_knowledge_base_service",
]
