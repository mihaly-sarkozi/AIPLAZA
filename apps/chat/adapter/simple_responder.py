# features/chat/adapters/simple_responder.py
from apps.chat.ports.chat_model import ChatModelPort

class SimpleResponder:
    async def answer(self, question: str) -> str:
        return f"Kaptam a kérdésed: {question}"