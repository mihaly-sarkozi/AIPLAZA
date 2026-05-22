# backend/lang/__init__.py
# Feladat: A lokalizációs csomag exportfelülete. Az email sablonokhoz és API/user-facing üzenetekhez szükséges helper függvényeket, ErrorCode enumot és default nyelvkódot adja tovább egységes importpontból. Nyelvi contract réteg a backend modulok számára.
# Sárközi Mihály - 2026.05.21
from lang.email_templates import get_email_template, DEFAULT_LANG
from lang.messages import get_message, ErrorCode

__all__ = [
    "get_email_template",
    "get_message",
    "ErrorCode",
    "DEFAULT_LANG",
]
