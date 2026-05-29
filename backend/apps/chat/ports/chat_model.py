# Ez a fájl az adott terület adatmodelljeit és kapcsolódó struktúráit tartalmazza.
from typing import Protocol

class ChatModelPort(Protocol):
    # Ez a metódus a(z) answer logikáját valósítja meg.
    def answer(self, user_text: str) -> str:  ...




