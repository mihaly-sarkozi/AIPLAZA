from __future__ import annotations

from typing import List
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort
from apps.knowledge.domain.kb import KnowledgeBase
import uuid

class KnowledgeBaseService:

    def __init__(self, repo: KnowledgeBaseRepositoryPort, qdrant_service: "QdrantClientWrapper") -> None:
        self.repo = repo
        self.qdrant = qdrant_service

    def list_all(self) -> List[KnowledgeBase]:
        """Összes knowledge base listázása."""
        return self.repo.list_all()

    def create(self, name: str, description: str | None = None) -> KnowledgeBase:
        """Új knowledge base létrehozása."""
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

        return self.repo.create(kb)

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
