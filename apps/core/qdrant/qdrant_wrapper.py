from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from openai import AsyncOpenAI
from typing import Any
import asyncio
import uuid as uuid_lib

class QdrantClientWrapper:
    def __init__(self, url: str, api_key: str, openai_key: str):
        self.client = QdrantClient(url=url, api_key=api_key, check_compatibility=False)
        self.openai = AsyncOpenAI(api_key=openai_key)

    async def embed_text(self, text: str) -> list[float]:
        """Szöveg embedding generálása OpenAI API-val."""
        response = await self.openai.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        return response.data[0].embedding

    async def upsert_vector(self, uuid: str, collection: str, vector: list[float], metadata: dict) -> Any:
        """Vektor beszúrása Qdrant kollekcióba (async wrapper sync hívásra)."""
        def _upsert():
            return self.client.upsert(
                collection_name=collection,
                points=[{
                    "id": uuid,
                    "vector": vector,
                    "payload": metadata
                }]
            )
        return await asyncio.to_thread(_upsert)

    async def search(self, query: str, collection: str, limit: int = 5) -> list[Any]:
        """Vektoros keresés Qdrant-ban."""
        vector = await self.embed_text(query)
        
        def _search():
            return self.client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit
            )
        return await asyncio.to_thread(_search)

    def create_collection(self, name: str) -> None:
        """Kollekció létrehozása Qdrant-ban."""
        self.client.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=3072,  # text-embedding-3-large mérete
                distance=Distance.COSINE
            )
        )

    def delete_collection(self, name: str) -> None:
        """Kollekció törlése Qdrant-ból."""
        self.client.delete_collection(collection_name=name)

    async def insert(self, collection: str, title: str, content: str, vector: list[float]) -> Any:
        """Beszúrás Qdrant kollekcióba (async wrapper sync hívásra)."""
        point_id = str(uuid_lib.uuid4())
        
        def _upsert():
            return self.client.upsert(
                collection_name=collection,
                points=[{
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "title": title,
                        "content": content,
                    }
                }]
            )
        return await asyncio.to_thread(_upsert)
