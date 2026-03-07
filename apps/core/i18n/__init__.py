# apps/core/i18n – Többnyelvű szövegek: email sablonok, hibakódok, felhasználói üzenetek.
from apps.core.i18n.email_templates import get_email_template, DEFAULT_LANG
from apps.core.i18n.messages import get_message, ErrorCode

__all__ = [
    "get_email_template",
    "get_message",
    "ErrorCode",
    "DEFAULT_LANG",
]
