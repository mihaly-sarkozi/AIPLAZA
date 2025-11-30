# core/ports/chat_model.py
from typing import Protocol

class ChatModelPort(Protocol):
    def answer(self, user_text: str) -> str:  ...