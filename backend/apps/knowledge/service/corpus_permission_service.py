# backend/apps/knowledge/service/corpus_permission_service.py
# Feladat: A knowledge corpus jogosultsági döntéseit és permission listázási nézeteit kezeli. Leválasztja a KnowledgeFacade-ból a user/tenant határhoz kötött use/train/manage döntéseket, hogy ezek izoláltan tesztelhetők és auditálhatók legyenek. Program-specifikus application service boundary.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from typing import Any, Callable

from apps.knowledge.domain.corpus import Corpus
from core.modules.auth.web.dependencies.auth_dependencies import has_permission
from core.modules.users.domain.dto import User


class CorpusPermissionService:
    def __init__(
        self,
        *,
        corpus_store: Any,
        user_repo_list_all: Callable[[], list[Any]],
        corpus_mapper: Callable[[Any], Corpus],
        list_all_unfiltered: Callable[[], list[Corpus]],
    ) -> None:
        self._corpus_store = corpus_store
        self._user_repo_list_all = user_repo_list_all
        self._to_corpus = corpus_mapper
        self._list_all_unfiltered = list_all_unfiltered

    def list_all(self, current_user_id: int | None = None, current_user: User | None = None) -> list[Corpus]:
        if current_user_id is None:
            return []
        if has_permission(current_user, "knowledge.write"):
            return [self._to_corpus(item) for item in self._corpus_store.list_all(include_deleted=True)]
        all_kbs = [self._to_corpus(item) for item in self._corpus_store.list_all()]
        permission = "train" if has_permission(current_user, "knowledge.permissions.manage") else "use"
        allowed_ids = set(self._corpus_store.get_kb_ids_with_permission(current_user_id, permission))
        return [kb for kb in all_kbs if kb.id is not None and kb.id in allowed_ids]

    def get_trainable_kb_ids(self, user_id: int, user: User | None) -> set[int]:
        if has_permission(user, "knowledge.write"):
            return {item.id for item in self._list_all_unfiltered() if item.id is not None}
        return set(self._corpus_store.get_kb_ids_with_permission(user_id, "train"))

    def get_permissions_with_users(self, kb_uuid: str) -> list[dict[str, Any]]:
        perm_list = self._corpus_store.list_permissions(kb_uuid)
        perm_by_user = {uid: perm for uid, perm in perm_list}
        return [
            self._permission_user_row(user, perm_by_user)
            for user in self._user_repo_list_all()
            if getattr(user, "id", None) is not None
        ]

    def get_permissions_with_users_batch(self, kb_uuids: list[str]) -> dict[str, list[dict[str, Any]]]:
        users = self._user_repo_list_all()
        perms_by_kb = self._corpus_store.list_permissions_batch(kb_uuids)
        result: dict[str, list[dict[str, Any]]] = {}
        for kb_uuid in kb_uuids:
            perm_by_user = {uid: perm for uid, perm in (perms_by_kb.get(kb_uuid) or [])}
            result[kb_uuid] = [
                self._permission_user_row(user, perm_by_user)
                for user in users
                if getattr(user, "id", None) is not None
            ]
        return result

    def set_permissions(
        self,
        kb_uuid: str,
        permissions: list[tuple[int, str]],
        current_user_id: int | None = None,
    ) -> None:
        if current_user_id is not None:
            existing = self._corpus_store.list_permissions(kb_uuid)
            existing_self = next((perm for uid, perm in existing if uid == current_user_id), "train")
            filtered = [(uid, perm) for uid, perm in permissions if uid != current_user_id and perm and perm != "none"]
            filtered.append((current_user_id, existing_self or "train"))
            self._corpus_store.set_permissions(kb_uuid, filtered, actor_user_id=current_user_id)
            return
        filtered = [(uid, perm) for uid, perm in permissions if perm and perm != "none"]
        self._corpus_store.set_permissions(kb_uuid, filtered, actor_user_id=0)

    def user_can_use(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        if has_permission(user, "knowledge.write"):
            return True
        kb = self._corpus_store.get_by_uuid(kb_uuid)
        if not kb or getattr(kb, "id", None) is None:
            return False
        return getattr(kb, "id") in self._corpus_store.get_kb_ids_with_permission(user_id, "use")

    def user_can_train(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        if has_permission(user, "knowledge.write"):
            return True
        kb = self._corpus_store.get_by_uuid(kb_uuid)
        if not kb or getattr(kb, "id", None) is None:
            return False
        return getattr(kb, "id") in self._corpus_store.get_kb_ids_with_permission(user_id, "train")

    @staticmethod
    def _permission_user_row(user: Any, perm_by_user: dict[int, str]) -> dict[str, Any]:
        user_id = getattr(user, "id", None)
        return {
            "user_id": user_id,
            "email": getattr(user, "email", "") or "",
            "name": getattr(user, "name", None),
            "permission": perm_by_user.get(user_id, "none"),
            "role": getattr(user, "role", "user"),
        }


__all__ = ["CorpusPermissionService"]
