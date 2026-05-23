"""Compatibility alias for apps.chat.application.chat_payload_policy."""
from apps.chat.application import chat_payload_policy as _impl
import sys as _sys
_sys.modules[__name__] = _impl
