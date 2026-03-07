# apps/core/container/app_container.py

# Ez az osztály felelős az alkalmazás fő komponenseinek és szolgáltatásainak összefogásáért (dependency injection mintával).
# Ide tartoznak az adatbázis kapcsolatok, repository-k, security szolgáltatások, authentikációs szolgáltatások, 
# valamint a chat és knowledge base app service-ek. Minden függőség központilag innen példányosítható, 
# így egyszerű, átlátható és könnyen bővíthető az alkalmazás fő részeinek kezelése.
# 2026.02.14 - Sárközi Mihály


from config.settings import settings

# --- DB ---
from apps.core.db.session import make_session_factory

# --- Security ---
from apps.core.security.token_service import TokenService
from apps.core.security.security_logger import SecurityLogger

# --- Qdrant + Embedding ---
from apps.core.qdrant.qdrant_wrapper import QdrantClientWrapper
from apps.ai.embedding_service import EmbeddingService

# --- Auth (authentikáció) + Users + Settings modulok ---
from apps.auth.application.services.login_service import LoginService
from apps.auth.application.services.refresh_service import RefreshService
from apps.auth.application.services.logout_service import LogoutService
from apps.auth.application.services.two_factor_service import TwoFactorService
from apps.auth.infrastructure.db.repositories import (
    TenantRepository,
    SessionRepository,
    TwoFactorRepository,
    Pending2FARepository,
)
from apps.users.application.services.user_service import UserService
from apps.users.infrastructure.db.repositories import UserRepository, InviteTokenRepository
from apps.settings.application.services.settings_service import SettingsService
from apps.settings.infrastructure.db.repositories import SettingsRepository
from apps.audit.application.audit_service import AuditService
from apps.audit.infrastructure.db.repositories import AuditRepository
from apps.core.email.email_service import EmailService

# --- Chat ---
from apps.chat.application.services.chat_service import ChatService

# --- Knowledge base ---
from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.infrastructure.db.repositories import MySQLKnowledgeBaseRepository


class AppContainer:

    def __init__(self):
        # --- DB ---
        self.db_session_factory = make_session_factory(
            settings.database_url,
            pool_pre_ping=getattr(settings, "database_pool_pre_ping", True),
        )

        # --- Security logger ---
        self.security_logger = SecurityLogger()

        # --- Auth repos (implementálják a ports *Interface osztályokat) ---
        self.tenant_repo = TenantRepository(self.db_session_factory)
        self.user_repo = UserRepository(self.db_session_factory)
        self.session_repo = SessionRepository(self.db_session_factory)
        self.settings_repo = SettingsRepository(self.db_session_factory)
        self.audit_repo = AuditRepository(self.db_session_factory)
        self.two_factor_repo = TwoFactorRepository(self.db_session_factory)
        self.pending_2fa_repo = Pending2FARepository(self.db_session_factory)

        # --- Email service ---
        self.email_service = EmailService()

        # --- Token system ---
        self.token_service = TokenService(
            secret=settings.jwt_secret,
            issuer="AIPLAZA",
            access_exp_min=settings.access_ttl_min,
            refresh_exp_min=settings.refresh_ttl_days * 24 * 60
        )

        # --- Settings & 2FA services ---
        self.settings_service = SettingsService(self.settings_repo)
        self.audit_service = AuditService(self.audit_repo)
        self.two_factor_service = TwoFactorService(self.two_factor_repo, self.email_service)

        # --- Auth app services ---
        self.login_service = LoginService(
            self.user_repo,
            self.session_repo,
            self.pending_2fa_repo,
            self.token_service,
            self.security_logger,
            self.two_factor_service,
            self.audit_service,
            settings_service=self.settings_service,
        )
        self.refresh_service = RefreshService(
            self.session_repo, self.token_service, self.security_logger, self.audit_service
        )
        self.logout_service = LogoutService(
            self.session_repo, self.token_service, self.security_logger, self.audit_service
        )
        self.invite_token_repo = InviteTokenRepository(self.db_session_factory)
        self.user_service = UserService(
            self.user_repo,
            self.audit_service,
            invite_token_repository=self.invite_token_repo,
            email_service=self.email_service,
        )

        # --- VECTOR + EMBEDDING ---
        self.qdrant = QdrantClientWrapper(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            openai_key=settings.OPENAI_API_KEY
        )

        self.embedder = EmbeddingService(api_key=settings.OPENAI_API_KEY)

        # --- KNOWLEDGE BASE SERVICE ---
        self.kb_repo = MySQLKnowledgeBaseRepository(self.db_session_factory)

        self.knowledge = KnowledgeBaseService(
            repo=self.kb_repo,
            qdrant_service=self.qdrant
        )

        # --- CHAT ---
        self.chat_service = ChatService()


# Singleton
container = AppContainer()
