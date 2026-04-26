# Ez a fájl a(z) simple_responder modul backend logikáját tartalmazza.
from apps.chat.ports.chat_model import ChatModelPort

class SimpleResponder:
    # Ez az aszinkron metódus a(z) answer logikáját valósítja meg.
    async def answer(self, question: str) -> str:
        return f"Kaptam a kérdésed: {question}"
