# features/chat/adapters/simple_responder.py
from features.chat.ports.chat_model import ChatModelPort

class SimpleResponder(ChatModelPort):
    def answer(self, user_text: str) -> str:
        return f"Erre kérdeztél: '{user_text}'. Válasz: hello world 😊"