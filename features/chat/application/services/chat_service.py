# features/chat/application/chat_service.py
from features.chat.ports.chat_model import ChatModelPort

class ChatService:
    def __init__(self, chat_model: ChatModelPort):
        self.chat_model = chat_model

    def chat(self, question: str) -> str:
        q = (question or "").strip()
        if not q:
            return "Adj meg kérdést."
        return self.chat_model.answer(q)