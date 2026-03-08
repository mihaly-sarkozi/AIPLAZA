from __future__ import annotations

from typing import List, Optional, Any
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort, KbPermissionItem
from apps.knowledge.domain.kb import KnowledgeBase
import uuid


def _user_repo_list_all(user_repo: Any) -> List[Any]:
    if user_repo is None:
        return []
    return user_repo.list_all()


class KnowledgeBaseService:

    def __init__(
        self,
        repo: KnowledgeBaseRepositoryPort,
        qdrant_service: "QdrantClientWrapper",
        user_repo: Any = None,
    ) -> None:
        self.repo = repo
        self.qdrant = qdrant_service
        self.user_repo = user_repo

    def list_all(
        self,
        current_user_id: Optional[int] = None,
        current_user_role: Optional[str] = None,
    ) -> List[KnowledgeBase]:
        """Owner mindent lát; admin csak a kezelhető (train) KB-kat; user csak use/train jogosat."""
        if current_user_id is None:
            return []
        all_kbs = self.repo.list_all()
        if current_user_role == "owner":
            return all_kbs
        if current_user_role == "admin":
            allowed_ids = set(self.repo.get_kb_ids_with_permission(current_user_id, "train"))
        else:
            allowed_ids = set(self.repo.get_kb_ids_with_permission(current_user_id, "use"))
        return [kb for kb in all_kbs if kb.id is not None and kb.id in allowed_ids]

    def list_all_unfiltered(self) -> List[KnowledgeBase]:
        """Összes knowledge base (admin listához)."""
        return self.repo.list_all()

    def create(
        self,
        name: str,
        description: str | None = None,
        permissions: Optional[List[KbPermissionItem]] = None,
        current_user_id: Optional[int] = None,
    ) -> KnowledgeBase:
        """Új knowledge base létrehozása; opcionálisan jogosultságokkal. A létrehozó mindig train jogot kap."""
        if self.repo.get_by_name(name):
            raise ValueError("KB name already exists")

        kb_uuid = str(uuid.uuid4())
        collection_name = f"kb_{kb_uuid}"

        self.qdrant.create_collection(collection_name)

        kb = KnowledgeBase(
            id=None,
            uuid=kb_uuid,
            name=name,
            description=description,
            qdrant_collection_name=collection_name,
            created_at=None,
            updated_at=None
        )

        created = self.repo.create(kb)
        perms = [(uid, p) for uid, p in (permissions or []) if p and p != "none"]
        if current_user_id is not None and not any(uid == current_user_id for uid, _ in perms):
            perms.append((current_user_id, "train"))
        self.repo.set_permissions(created.uuid, perms)
        return created

    def update(self, uuid: str, name: str, description: str) -> KnowledgeBase:
        """Knowledge base frissítése."""
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        kb.name = name
        kb.description = description
        return self.repo.update(kb)

    def delete(self, uuid: str, confirm_name: str | None = None) -> None:
        """Knowledge base törlése."""
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        # Ha confirm_name van megadva, ellenőrizzük
        if confirm_name and confirm_name != kb.name:
            raise ValueError("Confirmation name does not match")

        self.qdrant.delete_collection(kb.qdrant_collection_name)
        self.repo.delete(uuid)

    def get_permissions_with_users(self, kb_uuid: str) -> List[dict]:
        """Jogosultságok listája user adatokkal: { user_id, email, name, permission }."""
        perm_list = self.repo.list_permissions(kb_uuid)
        perm_by_user = {uid: p for uid, p in perm_list}
        users = _user_repo_list_all(self.user_repo)
        result = []
        for u in users:
            if getattr(u, "id", None) is None:
                continue
            result.append({
                "user_id": u.id,
                "email": getattr(u, "email", "") or "",
                "name": getattr(u, "name", None),
                "permission": perm_by_user.get(u.id, "none"),
                "role": getattr(u, "role", "user"),
            })
        return result

    def set_permissions(
        self, kb_uuid: str, permissions: List[KbPermissionItem], current_user_id: Optional[int] = None
    ) -> None:
        """Jogosultságok beállítása. A current_user saját jogát egyáltalán nem módosítjuk."""
        if current_user_id is not None:
            existing = self.repo.list_permissions(kb_uuid)
            existing_self = next((p for uid, p in existing if uid == current_user_id), "train")
            perms = []
            for uid, perm in permissions:
                if uid == current_user_id:
                    continue
                if perm and perm != "none":
                    perms.append((uid, perm))
            perms.append((current_user_id, existing_self if existing_self else "train"))
            self.repo.set_permissions(kb_uuid, perms)
        else:
            self.repo.set_permissions(
                kb_uuid, [(uid, p) for uid, p in permissions if p and p != "none"]
            )

    def user_can_use(self, kb_uuid: str, user_id: int, user_role: Optional[str]) -> bool:
        """Owner mindent használhat; különben csak ha van use/train joga."""
        if user_role == "owner":
            return True
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            return False
        allowed = self.repo.get_kb_ids_with_permission(user_id, "use")
        return kb.id in allowed

    def user_can_train(self, kb_uuid: str, user_id: int, user_role: Optional[str]) -> bool:
        """Owner mindent taníthat és kezelhet; különben csak ha van train joga."""
        if user_role == "owner":
            return True
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            return False
        allowed = self.repo.get_kb_ids_with_permission(user_id, "train")
        return kb.id in allowed

    # ------------------------------------------------------------
    #  ADD BLOCK – SZÖVEGES TANÍTÁS
    # ------------------------------------------------------------
    async def add_block(self, uuid: str, title: str, content: str) -> dict[str, str]:
        """Szöveges blokk hozzáadása a knowledge base-hez."""
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        # embed
        vector = await self.qdrant.embed_text(content)

        # upsert
        await self.qdrant.insert(
            kb.qdrant_collection_name,
            title=title,
            content=content,
            vector=vector
        )

        return {"status": "ok"}
    # ------------------------------------------------------------
    #  FILE TRAINING
    # ------------------------------------------------------------
    async def train_from_file(self, uuid: str, file) -> dict[str, str]:
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        ext = file.filename.lower()
        content = ""

        if ext.endswith(".pdf"):
            import pdfplumber
            with pdfplumber.open(file.file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n"

        elif ext.endswith(".docx"):
            import docx
            doc = docx.Document(file.file)
            for p in doc.paragraphs:
                content += p.text + "\n"

        elif ext.endswith(".txt"):
            content = file.file.read().decode("utf-8")

        else:
            raise ValueError("Unsupported file type")

        return await self.add_block(uuid, file.filename, content)
