class ChatService:
    def __init__(self, chat_model=None):
        self.chat_model = chat_model

    async def chat(self, question: str) -> str:
        if self.chat_model:
            # ha van injektált modell, azt használjuk
            return await self.chat_model.answer(question)
        return "Szia! Még nincs AI modell beállítva 😅"