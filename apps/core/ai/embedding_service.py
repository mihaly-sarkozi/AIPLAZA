from openai import AsyncOpenAI

class EmbeddingService:

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def embed_text(self, text: str) -> list[float]:
        resp = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return resp.data[0].embedding
