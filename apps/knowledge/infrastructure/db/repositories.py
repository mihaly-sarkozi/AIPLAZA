from sqlalchemy import select
from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.infrastructure.db.models import KBORM
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort


class MySQLKnowledgeBaseRepository(KnowledgeBaseRepositoryPort):

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _to_domain(self, orm: KBORM) -> KnowledgeBase:
        return KnowledgeBase(
            id=orm.id,
            uuid=orm.uuid,
            name=orm.name,
            description=orm.description,
            qdrant_collection_name=orm.qdrant_collection_name,
            created_at=orm.created_at,
            updated_at=orm.updated_at
        )

    def list_all(self):
        with self.session_factory() as session:
            stmt = select(KBORM)
            result = session.execute(stmt).scalars().all()
            return [self._to_domain(x) for x in result]

    def get_by_uuid(self, uuid: str):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.uuid == uuid)
            orm = session.execute(stmt).scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    def get_by_name(self, name: str):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.name == name)
            orm = session.execute(stmt).scalar_one_or_none()
            return self._to_domain(orm) if orm else None

    def create(self, kb: KnowledgeBase):
        with self.session_factory() as session:
            orm = KBORM(
                uuid=kb.uuid,
                name=kb.name,
                description=kb.description,
                qdrant_collection_name=kb.qdrant_collection_name
            )
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return self._to_domain(orm)

    def update(self, kb: KnowledgeBase):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.uuid == kb.uuid)
            orm = session.execute(stmt).scalar_one_or_none()
            if not orm:
                return None

            orm.name = kb.name
            orm.description = kb.description
            orm.updated_at = kb.updated_at

            session.commit()
            return self._to_domain(orm)

    def delete(self, uuid: str):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.uuid == uuid)
            orm = session.execute(stmt).scalar_one_or_none()
            if orm:
                session.delete(orm)
                session.commit()
