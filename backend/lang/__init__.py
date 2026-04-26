# lang - lokalizalt uzenetek es email sablonok
from lang.email_templates import get_email_template, DEFAULT_LANG
from lang.messages import get_message, ErrorCode

__all__ = [
    "get_email_template",
    "get_message",
    "ErrorCode",
    "DEFAULT_LANG",
]
