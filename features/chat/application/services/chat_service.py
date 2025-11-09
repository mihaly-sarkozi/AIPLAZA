from openai import AsyncOpenAI
import os

class ChatService:
    def __init__(self, chat_model=None):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY nem található .env fájlban.")
        self.client = chat_model or AsyncOpenAI(api_key=api_key)

    async def chat(self, question: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Te egy segítőkész asszisztens vagy az AIPLAZA rendszerben."},
                    {"role": "user", "content": question},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            print("❌ OpenAI API hiba:", e)
            return "⚠️ Nem sikerült választ kapni a modellből."
