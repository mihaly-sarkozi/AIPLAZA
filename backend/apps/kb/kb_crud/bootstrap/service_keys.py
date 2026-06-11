from __future__ import annotations

# backend/apps/kb/kb_crud/bootstrap/service_keys.py
# Feladat: A kb_crud modul DI kulcsai.
# Sárközi Mihály - 2026.06.07

from core.kernel.interface.app_keys import module_service_key

KB_CRUD_REPOSITORY = module_service_key("kb", "crud.repository")
KB_CRUD_PERMISSION_REPOSITORY = module_service_key("kb", "crud.permission_repository")
KB_CRUD_USER_DIRECTORY = module_service_key("kb", "crud.user_directory")
KB_CRUD_CONTENT_CLEANUP = module_service_key("kb", "crud.content_cleanup")
KB_CRUD_STORAGE_METRICS = module_service_key("kb", "crud.storage_metrics")
KB_CRUD_TRAINING_SUMMARY = module_service_key("kb", "crud.training_summary")
KB_CRUD_USAGE_LIMIT = module_service_key("kb", "crud.usage_limit")
KB_CRUD_AUDIT_LOGGER = module_service_key("kb", "crud.audit_logger")

__all__ = [
    "KB_CRUD_AUDIT_LOGGER",
    "KB_CRUD_CONTENT_CLEANUP",
    "KB_CRUD_PERMISSION_REPOSITORY",
    "KB_CRUD_REPOSITORY",
    "KB_CRUD_STORAGE_METRICS",
    "KB_CRUD_TRAINING_SUMMARY",
    "KB_CRUD_USAGE_LIMIT",
    "KB_CRUD_USER_DIRECTORY",
]
