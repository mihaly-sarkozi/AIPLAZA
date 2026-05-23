"""Compatibility alias for apps.chat.application.http_use_cases."""
from apps.chat.application import http_use_cases as _impl
import sys as _sys
_sys.modules[__name__] = _impl
