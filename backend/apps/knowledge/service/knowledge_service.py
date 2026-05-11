# Ez a fájl az adott terület szolgáltatás- és üzleti logikáját tartalmazza.
from __future__ import annotations

import uuid as uuid_lib
from typing import Any, Optional

from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.repositories.knowledge_base_repository import MySQLKnowledgeBaseRepository
from apps.knowledge.ports.repositories import KbPermissionItem
from core.capabilities.users.dto import User
from core.platform.auth.auth_dependencies import has_permission


class KnowledgeBaseService:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, repo: MySQLKnowledgeBaseRepository, user_repo: Any = None) -> None:
        self.repo = repo
        self.user_repo = user_repo

    # Ez a metódus a(z) user_repo_list_all logikáját valósítja meg.
    def _user_repo_list_all(self) -> list[Any]:
        if self.user_repo is None:
            return []
        return self.user_repo.list_all()

    # Ez a metódus listázza a(z) all logikáját.
    def list_all(
        self,
        current_user_id: Optional[int] = None,
        current_user: User | None = None,
    ) -> list[KnowledgeBase]:
        if current_user_id is None:
            return []
        all_kbs = self.repo.list_all()
        if has_permission(current_user, "knowledge.write"):
            return all_kbs
        permission = "train" if has_permission(current_user, "knowledge.permissions.manage") else "use"
        allowed_ids = set(self.repo.get_kb_ids_with_permission(current_user_id, permission))
        return [kb for kb in all_kbs if kb.id is not None and kb.id in allowed_ids]

    # Ez a metódus listázza a(z) all unfiltered logikáját.
    def list_all_unfiltered(self) -> list[KnowledgeBase]:
        return self.repo.list_all(include_deleted=True)

    def storage_metrics_for_corpus(self, kb: KnowledgeBase) -> dict[str, int]:
        return {
            "file_bytes": 0,
            "database_bytes": 0,
            "qdrant_bytes": 0,
            "total_bytes": 0,
            "qdrant_points": 0,
            "qdrant_vectors": 0,
        }

    # Qdrant kollekció neve tanításhoz (uuid alapján).
    def qdrant_collection_for_uuid(self, kb_uuid: str) -> str | None:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb:
            return None
        return kb.qdrant_collection_name

    # Ez a metódus visszaadja a(z) trainable KB ids logikáját.
    def get_trainable_kb_ids(self, user_id: int, user: User | None) -> set[int]:
        if has_permission(user, "knowledge.write"):
            return {kb.id for kb in self.repo.list_all() if kb.id is not None}
        return set(self.repo.get_kb_ids_with_permission(user_id, "train"))

    # Ez a metódus létrehozza a(z) create logikáját.
    def create(
        self,
        name: str,
        description: str | None = None,
        permissions: Optional[list[KbPermissionItem]] = None,
        current_user_id: Optional[int] = None,
    ) -> KnowledgeBase:
        if self.repo.get_by_name(name):
            raise ValueError("KB name already exists")
        if current_user_id is None:
            raise ValueError("Current user is required")
        kb_uuid = str(uuid_lib.uuid4())
        kb = KnowledgeBase(
            id=None,
            uuid=kb_uuid,
            name=name,
            description=description,
            qdrant_collection_name=f"kb_{kb_uuid}",
            created_at=None,
            updated_at=None,
        )
        created = self.repo.create(kb, actor_user_id=current_user_id)
        perms = [(uid, perm) for uid, perm in (permissions or []) if perm and perm != "none"]
        if not any(uid == current_user_id for uid, _ in perms):
            perms.append((current_user_id, "train"))
        self.repo.set_permissions(created.uuid, perms, actor_user_id=current_user_id)
        return created

    # Ez a metódus frissíti a(z) update logikáját.
    def update(
        self,
        uuid: str,
        name: str,
        description: str | None,
        personal_data_mode: Optional[str] = None,
        pii_depersonalization_enabled: Optional[bool] = None,
        current_user_id: Optional[int] = None,
    ) -> KnowledgeBase:
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")
        if current_user_id is None:
            raise ValueError("Current user is required")
        kb.name = name
        kb.description = description
        if personal_data_mode is not None:
            kb.personal_data_mode = personal_data_mode
        if pii_depersonalization_enabled is not None:
            kb.pii_depersonalization_enabled = bool(pii_depersonalization_enabled)
        return self.repo.update(kb, actor_user_id=current_user_id)

    # Ez a metódus törli a(z) delete logikáját.
    def delete(self, uuid: str, confirm_name: str | None = None, demo_mode: bool = False) -> None:
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")
        if confirm_name and confirm_name != kb.name:
            raise ValueError("Confirmation name does not match")
        self.repo.delete(uuid)

    # Ez a metódus visszaadja a(z) permissions with felhasználók logikáját.
    def get_permissions_with_users(self, kb_uuid: str) -> list[dict]:
        perm_list = self.repo.list_permissions(kb_uuid)
        perm_by_user = {uid: perm for uid, perm in perm_list}
        return [
            {
                "user_id": user.id,
                "email": getattr(user, "email", "") or "",
                "name": getattr(user, "name", None),
                "permission": perm_by_user.get(user.id, "none"),
                "role": getattr(user, "role", "user"),
            }
            for user in self._user_repo_list_all()
            if getattr(user, "id", None) is not None
        ]

    # Ez a metódus visszaadja a(z) permissions with felhasználók batch logikáját.
    def get_permissions_with_users_batch(self, kb_uuids: list[str]) -> dict[str, list[dict]]:
        if not kb_uuids:
            return {}
        users = self._user_repo_list_all()
        perms_by_kb = self.repo.list_permissions_batch(kb_uuids)
        result: dict[str, list[dict]] = {}
        for kb_uuid in kb_uuids:
            perm_by_user = {uid: perm for uid, perm in (perms_by_kb.get(kb_uuid) or [])}
            result[kb_uuid] = [
                {
                    "user_id": user.id,
                    "email": getattr(user, "email", "") or "",
                    "name": getattr(user, "name", None),
                    "permission": perm_by_user.get(user.id, "none"),
                    "role": getattr(user, "role", "user"),
                }
                for user in users
                if getattr(user, "id", None) is not None
            ]
        return result

    # Ez a metódus beállítja a(z) permissions logikáját.
    def set_permissions(
        self,
        kb_uuid: str,
        permissions: list[KbPermissionItem],
        current_user_id: Optional[int] = None,
    ) -> None:
        if current_user_id is not None:
            existing = self.repo.list_permissions(kb_uuid)
            existing_self = next((perm for uid, perm in existing if uid == current_user_id), "train")
            filtered = [(uid, perm) for uid, perm in permissions if uid != current_user_id and perm and perm != "none"]
            filtered.append((current_user_id, existing_self or "train"))
            self.repo.set_permissions(kb_uuid, filtered, actor_user_id=current_user_id)
            return
        filtered = [(uid, perm) for uid, perm in permissions if perm and perm != "none"]
        self.repo.set_permissions(kb_uuid, filtered, actor_user_id=0)

    # Ez a metódus a(z) user_can_use logikáját valósítja meg.
    def user_can_use(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        if has_permission(user, "knowledge.write"):
            return True
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            return False
        return kb.id in self.repo.get_kb_ids_with_permission(user_id, "use")

    # Ez a metódus a(z) user_can_train logikáját valósítja meg.
    def user_can_train(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        if has_permission(user, "knowledge.write"):
            return True
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            return False
        return kb.id in self.repo.get_kb_ids_with_permission(user_id, "train")
