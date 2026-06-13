from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+", re.UNICODE)
_SIGNATURE = re.compile(
    r"(?i)\b("
    r"üdv|tisztelettel|köszönettel|"
    r"best regards|kind regards|sincerely|regards|signature|signed by"
    r")\b",
    re.UNICODE,
)


class PersonContextSignals:
    def email_nearby(self, text: str, start: int, end: int, *, window: int = 120) -> bool:
        snippet = text[max(0, start - window) : min(len(text), end + window)]
        return _EMAIL.search(snippet) is not None

    def signature_nearby(self, text: str, start: int, end: int, *, window: int = 200) -> bool:
        snippet = text[max(0, start - window) : min(len(text), end + window)]
        return _SIGNATURE.search(snippet) is not None


__all__ = ["PersonContextSignals"]
