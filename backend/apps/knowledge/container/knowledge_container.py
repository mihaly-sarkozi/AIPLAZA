# Ez a fájl a komponensek összerakását és a függőségek felépítését tartalmazza.
from __future__ import annotations

from dataclasses import dataclass

from apps.knowledge.service.knowledge_service import KnowledgeBaseService
from apps.knowledge.repositories.knowledge_base_repository import MySQLKnowledgeBaseRepository
from core.modules.users.repository.persistence.user_repository import UserRepository


@dataclass(frozen=True)
class KnowledgeFeatureContainer:
    service: KnowledgeBaseService


# Ez a függvény felépíti a(z) knowledge feature logikáját.
def build_knowledge_feature(repo: MySQLKnowledgeBaseRepository, user_repo: UserRepository | None = None) -> KnowledgeFeatureContainer:
    return KnowledgeFeatureContainer(service=KnowledgeBaseService(repo=repo, user_repo=user_repo))
