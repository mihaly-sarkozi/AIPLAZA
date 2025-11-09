from config.settings import settings
from infrastructure.persistence.db_session import make_session_factory

from infrastructure.persistence.mysql.auth_repos import MySQLUserRepository, MySQLSessionRepository
from infrastructure.security.tokens import TokenService

from features.auth.application.services.login_service import LoginService
from features.auth.application.services.refresh_service import RefreshService
from features.auth.application.services.logout_service import LogoutService

from features.chat.application.services.chat_service import ChatService
from infrastructure.models.simple_responder import SimpleResponder


# ORM session factory (közös)
SessionLocal = make_session_factory(settings.mysql_dsn)

# Repozitóriumok
_user_repo = MySQLUserRepository(SessionLocal)
_sess_repo = MySQLSessionRepository(SessionLocal)

# Token service (DI-n át kapja a secretet/TTL-t)
_token_service = TokenService(
    secret=settings.jwt_secret, issuer="AIPLAZA",
    access_exp_min=settings.access_ttl_min, refresh_exp_min=settings.refresh_ttl_days
)

# Auth service-ek
_login_service = LoginService(_user_repo, _sess_repo, _token_service)
_refresh_service = RefreshService(_sess_repo, _token_service)
_logout_service = LogoutService(_sess_repo, _token_service)


def get_login_service(): return _login_service


def get_refresh_service(): return _refresh_service


def get_logout_service(): return _logout_service


# Chat service
_chat_service = ChatService()

def get_chat_service():
    return _chat_service