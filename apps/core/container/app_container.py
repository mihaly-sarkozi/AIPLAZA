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
from apps.core.security.event_channel import SecurityAuditEventChannel

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
    TwoFactorAttemptRepository,
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
from apps.knowledge.application.context_builder import KnowledgeContextBuilder
from apps.knowledge.application.query_parser import QueryParser
from apps.knowledge.application.retrieval_service import KnowledgeRetrievalService
from apps.knowledge.application.evaluation import RetrievalEvaluationService
from apps.knowledge.application.maintenance import KnowledgeMaintenanceService
from apps.knowledge.application.feedback import RetrievalFeedbackService

# --- Knowledge base ---
from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.application.indexing_pipeline import KnowledgeIndexingPipeline
from apps.knowledge.application.vector_outbox_worker import KnowledgeVectorOutboxWorker
from apps.knowledge.infrastructure.db.repositories import MySQLKnowledgeBaseRepository
from apps.knowledge.infrastructure.extraction.openai_assertion_extractor import OpenAIAssertionExtractor
from apps.knowledge.infrastructure.qdrant.knowledge_vector_index import KnowledgeVectorIndex


class AppContainer:

    def __init__(self):
        # --- DB ---
        self.db_session_factory = make_session_factory(
            settings.database_url,
            pool_pre_ping=getattr(settings, "database_pool_pre_ping", True),
        )

        # --- Security logger (valódi; async módban a channel proxyit kapják a service-ek) ---
        self._security_logger = SecurityLogger()

        # --- Auth repos (implementálják a ports *Interface osztályokat) ---
        self.tenant_repo = TenantRepository(self.db_session_factory)
        self.user_repo = UserRepository(self.db_session_factory)
        self.session_repo = SessionRepository(self.db_session_factory)
        self.settings_repo = SettingsRepository(self.db_session_factory)
        self.audit_repo = AuditRepository(self.db_session_factory)
        self.two_factor_repo = TwoFactorRepository(self.db_session_factory)
        self.two_factor_attempt_repo = TwoFactorAttemptRepository(self.db_session_factory)
        self.pending_2fa_repo = Pending2FARepository(self.db_session_factory)

        # --- Email service ---
        self.email_service = EmailService()

        # --- Token system (policy: iss + aud ha megadva + nbf mindig) ---
        _aud = (getattr(settings, "jwt_audience", "") or "").strip()
        self.token_service = TokenService(
            secret=settings.jwt_secret,
            issuer="AIPLAZA",
            audience=_aud or None,
            access_exp_min=settings.access_ttl_min,
            refresh_exp_min=settings.refresh_ttl_days * 24 * 60
        )

        # --- Settings & 2FA services ---
        self.settings_service = SettingsService(self.settings_repo)
        self._audit_service = AuditService(self.audit_repo)
        from apps.core.security.two_factor_policy import (
            get_2fa_max_attempts,
            get_2fa_attempt_window_minutes,
            get_2fa_code_expiry_minutes,
        )
        # --- Security/audit/email: async eseménycsatorna (queue + worker) vagy szinkron ---
        self.event_channel = None
        if getattr(settings, "audit_events_async", True):
            self.event_channel = SecurityAuditEventChannel(
                self._security_logger,
                self._audit_service,
                self.email_service,
            )
            self.event_channel.start_worker()
            self.security_logger = self.event_channel.security_logger
            self.audit_service = self.event_channel.audit_service
        else:
            self.security_logger = self._security_logger
            self.audit_service = self._audit_service

        # --- 2FA service (email háttérbe küldhet event_channel-nel) ---
        self.two_factor_service = TwoFactorService(
            self.two_factor_repo,
            self.email_service,
            attempt_repo=self.two_factor_attempt_repo,
            max_attempts=get_2fa_max_attempts(),
            attempt_window_minutes=get_2fa_attempt_window_minutes(),
            code_expiry_minutes=get_2fa_code_expiry_minutes(),
            event_channel=self.event_channel,
        )

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
            self.session_repo,
            self.token_service,
            self.security_logger,
            self.audit_service,
            user_repository=self.user_repo,
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
        self.kb_vector_index = KnowledgeVectorIndex(self.qdrant)
        self.assertion_extractor = OpenAIAssertionExtractor()
        self.kb_indexing_pipeline = KnowledgeIndexingPipeline(
            repo=self.kb_repo,
            vector_index=self.kb_vector_index,
            extractor=self.assertion_extractor,
        )

        self.knowledge = KnowledgeBaseService(
            repo=self.kb_repo,
            qdrant_service=self.qdrant,
            user_repo=self.user_repo,
            indexing_pipeline=self.kb_indexing_pipeline,
        )
        self.vector_outbox_worker = None
        if getattr(settings, "kb_vector_outbox_worker_enabled", True):
            self.vector_outbox_worker = KnowledgeVectorOutboxWorker(
                self.knowledge,
                poll_interval_sec=float(getattr(settings, "kb_vector_outbox_poll_sec", 5.0) or 5.0),
                batch_limit=int(getattr(settings, "kb_vector_outbox_batch_limit", 50) or 50),
            )
            self.vector_outbox_worker.start()

        # --- CHAT ---
        self.query_parser = QueryParser()
        self.context_builder = KnowledgeContextBuilder()
        self.retrieval_service = KnowledgeRetrievalService(self.knowledge)
        self.maintenance_service = KnowledgeMaintenanceService(self.knowledge, self.kb_repo)
        self.retrieval_evaluation_service = RetrievalEvaluationService(self.retrieval_service)
        self.retrieval_feedback_service = RetrievalFeedbackService(self.retrieval_service)
        self.chat_service = ChatService(
            kb_service=self.knowledge,
            retrieval_service=self.retrieval_service,
            query_parser=self.query_parser,
            context_builder=self.context_builder,
        )


# Singleton
container = AppContainer()
