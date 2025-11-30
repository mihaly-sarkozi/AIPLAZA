# apps/core/container/app_container.py

# Ez az osztály felelős az alkalmazás fő komponenseinek és szolgáltatásainak összefogásáért (dependency injection mintával).
# Ide tartoznak az adatbázis kapcsolatok, repository-k, security szolgáltatások, authentikációs szolgáltatások, 
# valamint a chat és knowledge base app service-ek. Minden függőség központilag innen példányosítható, 
# így egyszerű, átlátható és könnyen bővíthető az alkalmazás fő részeinek kezelése.


from config.settings import settings

# --- DB ---
from apps.core.db.session import make_session_factory

# --- Security ---
from apps.core.security.token_service import TokenService
from apps.core.security.security_logger import SecurityLogger

# --- Qdrant + Embedding ---
from apps.core.qdrant.qdrant_wrapper import QdrantClientWrapper
from apps.core.ai.embedding_service import EmbeddingService

# --- Auth services + repos ---
from apps.auth.application.services.login_service import LoginService
from apps.auth.application.services.refresh_service import RefreshService
from apps.auth.application.services.logout_service import LogoutService
from apps.auth.application.services.user_service import UserService
from apps.auth.infrastructure.db.repositories import MySQLUserRepository, MySQLSessionRepository

# --- Chat ---
from apps.chat.application.services.chat_service import ChatService

# --- Knowledge base ---
from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.infrastructure.db.repositories import MySQLKnowledgeBaseRepository


class AppContainer:

    def __init__(self):
        # --- DB ---
        self.db_session_factory = make_session_factory(settings.mysql_dsn)

        # --- Security logger ---
        self.security_logger = SecurityLogger()

        # --- Auth repos ---
        self.user_repo = MySQLUserRepository(self.db_session_factory)
        self.session_repo = MySQLSessionRepository(self.db_session_factory)

        # --- Token system ---
        self.token_service = TokenService(
            secret=settings.jwt_secret,
            issuer="AIPLAZA",
            access_exp_min=settings.access_ttl_min,
            refresh_exp_min=settings.refresh_ttl_days
        )

        # --- Auth app services ---
        self.login_service = LoginService(self.user_repo, self.session_repo, self.token_service, self.security_logger)
        self.refresh_service = RefreshService(self.session_repo, self.token_service, self.security_logger)
        self.logout_service = LogoutService(self.session_repo, self.token_service, self.security_logger)
        self.user_service = UserService(self.user_repo)

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
