# apps/core/di.py
# Ez egy Dependecy Injection provider ami definiálja az elérhető szolgáltatásokat
# Ha szeretnénk használni egy szolgálatást akkor Ebből a fájlból kell importálni a get metódust.
# 2026.02.14 - Sárközi Mihály

from fastapi import Request

from apps.core.container.app_container import container
from apps.core.db.tenant_context import current_tenant_schema


def set_tenant_context_from_request(request: Request) -> None:
    """
    A middleware a fő szálban állítja a tenant_slug-ot; a sync route viszont
    thread pool-ban fut, ahol a context var üres. Ez a dependency a request.state-ból
    visszaállítja a current_tenant_schema-t a route szálában.
    """
    slug = getattr(request.state, "tenant_slug", None)
    if slug:
        current_tenant_schema.set(slug)


def get_tenant_repository():
    """Tenant repository provider (subdomain → tenant)."""
    return container.tenant_repo


def get_token_service():
    """Token service provider."""
    return container.token_service

def get_login_service():
    """Login service provider."""
    return container.login_service

def get_refresh_service():
    """Refresh service provider."""
    return container.refresh_service

def get_logout_service():
    """Logout service provider."""
    return container.logout_service

def get_chat_service():
    """Chat service provider."""
    return container.chat_service

def get_kb_service():
    """Knowledge base service provider."""
    return container.knowledge


def get_kb_maintenance_service():
    """Knowledge maintenance service provider."""
    return container.maintenance_service


def get_retrieval_evaluation_service():
    """Retrieval evaluation service provider."""
    return container.retrieval_evaluation_service


def get_retrieval_feedback_service():
    """Retrieval feedback service provider."""
    return container.retrieval_feedback_service

def get_user_service():
    """User service provider."""
    return container.user_service


def get_user_repository():
    """User repository (tenant-scoped); pl. auth /me, profil frissítés."""
    return container.user_repo

def get_settings_service():
    """Settings service provider."""
    return container.settings_service

def get_audit_service():
    """Audit log service provider."""
    return container.audit_service

def get_two_factor_service():
    """Two factor service provider."""
    return container.two_factor_service


def get_session_repository():
    """Session repository (auth) – pl. user törlésnél session invalidate."""
    return container.session_repo


def get_cache():
    """Központi cache (tenant, user, permissions_changed). Redis ha redis_url, különben memory."""
    from apps.core.cache import get_cache as _get_cache
    return _get_cache()

