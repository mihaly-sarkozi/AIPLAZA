# apps/core/di.py

# Ez egy Dependecy Injection provider ami definiálja az elérhető szolgáltatásokat
# Ha szeretnénk használni egy szolgálatást akkor Ebből a fájlból kell importálni a get metódust.

from apps.core.container.app_container import container

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

def get_user_service():
    """User service provider."""
    return container.user_service

