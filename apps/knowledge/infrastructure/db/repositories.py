from typing import Optional
from sqlalchemy import select, delete
from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.infrastructure.db.models import KBORM, KbUserPermissionORM, KbTrainingLogORM, KbPersonalDataORM
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort, KbPermissionItem


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
            personal_data_mode=getattr(orm, "personal_data_mode", None) or "no_personal_data",
            personal_data_sensitivity=getattr(orm, "personal_data_sensitivity", None) or "medium",
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

    def get_by_id(self, kb_id: int):
        with self.session_factory() as session:
            stmt = select(KBORM).where(KBORM.id == kb_id)
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
                qdrant_collection_name=kb.qdrant_collection_name,
                personal_data_mode=getattr(kb, "personal_data_mode", None) or "no_personal_data",
                personal_data_sensitivity=getattr(kb, "personal_data_sensitivity", None) or "medium",
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
            if hasattr(orm, "personal_data_mode"):
                orm.personal_data_mode = getattr(kb, "personal_data_mode", None) or "no_personal_data"
            if hasattr(orm, "personal_data_sensitivity"):
                orm.personal_data_sensitivity = getattr(kb, "personal_data_sensitivity", None) or "medium"
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

    def list_permissions(self, kb_uuid: str) -> list[KbPermissionItem]:
        with self.session_factory() as session:
            kb = session.execute(select(KBORM).where(KBORM.uuid == kb_uuid)).scalar_one_or_none()
            if not kb:
                return []
            stmt = select(KbUserPermissionORM.user_id, KbUserPermissionORM.permission).where(
                KbUserPermissionORM.kb_id == kb.id
            )
            rows = session.execute(stmt).all()
            return [(r[0], r[1]) for r in rows]

    def add_training_log(
        self,
        kb_id: int,
        point_id: str,
        user_id: Optional[int],
        user_display: Optional[str],
        title: str,
        content: Optional[str],
    ) -> None:
        with self.session_factory() as session:
            session.add(
                KbTrainingLogORM(
                    kb_id=kb_id,
                    point_id=point_id,
                    user_id=user_id,
                    user_display=user_display or None,
                    title=title,
                    content=content,
                )
            )
            session.commit()

    def list_training_log(self, kb_uuid: str) -> list[dict]:
        with self.session_factory() as session:
            kb = session.execute(select(KBORM).where(KBORM.uuid == kb_uuid)).scalar_one_or_none()
            if not kb:
                return []
            stmt = (
                select(KbTrainingLogORM)
                .where(KbTrainingLogORM.kb_id == kb.id)
                .order_by(KbTrainingLogORM.created_at.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "point_id": r.point_id,
                    "user_id": r.user_id,
                    "user_display": r.user_display or "",
                    "title": r.title,
                    "content": r.content,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    def delete_training_log_by_point_id(self, kb_id: int, point_id: str) -> bool:
        with self.session_factory() as session:
            stmt = delete(KbTrainingLogORM).where(
                KbTrainingLogORM.kb_id == kb_id,
                KbTrainingLogORM.point_id == point_id,
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount > 0

    def set_permissions(self, kb_uuid: str, permissions: list[KbPermissionItem]) -> None:
        with self.session_factory() as session:
            kb = session.execute(select(KBORM).where(KBORM.uuid == kb_uuid)).scalar_one_or_none()
            if not kb:
                raise ValueError("KB not found")
            session.execute(delete(KbUserPermissionORM).where(KbUserPermissionORM.kb_id == kb.id))
            for user_id, perm in permissions:
                if perm and perm != "none":
                    session.add(
                        KbUserPermissionORM(kb_id=kb.id, user_id=user_id, permission=perm)
                    )
            session.commit()

    def get_kb_ids_with_permission(self, user_id: int, permission: str) -> list[int]:
        """KB id-k ahol a user rendelkezik ezzel a jogosultsággal (train = use + train)."""
        with self.session_factory() as session:
            if permission == "use":
                stmt = select(KbUserPermissionORM.kb_id).where(
                    KbUserPermissionORM.user_id == user_id,
                    KbUserPermissionORM.permission.in_(["use", "train"]),
                )
            else:
                stmt = select(KbUserPermissionORM.kb_id).where(
                    KbUserPermissionORM.user_id == user_id,
                    KbUserPermissionORM.permission == permission,
                )
            rows = session.execute(stmt).scalars().all()
            return list(rows)

    def add_personal_data(self, kb_id: int, data_type: str, extracted_value: str) -> str:
        import uuid as uuid_mod
        ref_id = str(uuid_mod.uuid4())
        with self.session_factory() as session:
            session.add(
                KbPersonalDataORM(
                    kb_id=kb_id,
                    data_type=data_type,
                    extracted_value=extracted_value,
                    reference_id=ref_id,
                )
            )
            session.commit()
        return ref_id
