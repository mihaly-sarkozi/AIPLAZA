import os
from dotenv import load_dotenv

from qdrant_wrapper import QdrantClient
from qdrant_wrapper.models import (
    VectorParams,
    Distance,
    PointStruct
)

from openai import AsyncOpenAI

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not QDRANT_URL:
    raise Exception("QDRANT_URL is not set in the environment")
if not QDRANT_API_KEY:
    raise Exception("QDRANT_API_KEY is not set in the environment")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY is not set in the environment")


# ---------------------------------------------------------
#  Qdrant + OpenAI kliensek
# ---------------------------------------------------------
qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------
#  Qdrant Service
# ---------------------------------------------------------
class QdrantService:

    def __init__(self, client: QdrantClient):
        self.client = client

    # --- Embedding generálás ---
    async def embed_text(self, text: str) -> list[float]:
        """
        OpenAI embedding generálás.
        """
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    # --- Beszúrás Qdrant kollekcióba ---
    def insert(self, collection: str, title: str, content: str, vector: list[float]):
        """
        A tudástár blokk beszúrása Qdrant-ba.
        """
        point = PointStruct(
            id=None,
            vector=vector,
            payload={
                "title": title,
                "content": content,
            }
        )

        self.client.upsert(
            collection_name=collection,
            points=[point],
        )

    # --- Kollekció létrehozás ---
    def create_collection(self, name: str):
        self.client.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=1536,
                distance=Distance.COSINE
            )
        )

    # --- Kollekció törlés ---
    def delete_collection(self, name: str):
        self.client.delete_collection(collection_name=name)


# Globális service
qdrant_service = QdrantService(qdrant_client)
