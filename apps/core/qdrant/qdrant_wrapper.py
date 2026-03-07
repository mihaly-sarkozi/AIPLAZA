from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from qdrant_client.http.exceptions import UnexpectedResponse
from openai import AsyncOpenAI
from typing import Any
import asyncio
import uuid as uuid_lib


class QdrantUnavailableError(Exception):
    """Qdrant nem elérhető vagy a konfiguráció hibás (pl. 404)."""


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
        """Új kollekció létrehozása Qdrant-ban (create, nem recreate – így nem 404 ha még nincs)."""
        try:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=3072,  # text-embedding-3-large mérete
                    distance=Distance.COSINE
                )
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                raise QdrantUnavailableError(
                    "Qdrant 404: a szolgáltatás nem elérhető vagy a QDRANT_URL hibás. "
                    "Lokálisan pl. http://localhost:6333, Cloud-nál a cluster URL (trailing slash nélkül). "
                    "Ellenőrizd a .env-ben a QDRANT_URL-t és hogy a Qdrant fut-e."
                ) from e
            raise

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
