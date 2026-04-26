# Ez a fájl több modul által közösen használt backend segédlogikát tartalmaz.
from lang.messages import ErrorCode, get_message, lang_from_request


class LocalizedPresenterBase:
    # Ez a metódus a(z) lang logikáját valósítja meg.
    @staticmethod
    def lang(request) -> str:
        return lang_from_request(request)

    # Ez a metódus a(z) detail_for_lang logikáját valósítja meg.
    @staticmethod
    def detail_for_lang(code: ErrorCode, lang: str) -> dict[str, str]:
        return {"code": code.value, "message": get_message(code, lang)}

    # Ez a metódus a(z) detail logikáját valósítja meg.
    def detail(self, request, code: ErrorCode) -> dict[str, str]:
        return self.detail_for_lang(code, self.lang(request))
