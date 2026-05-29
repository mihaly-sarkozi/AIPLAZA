from __future__ import annotations

from apps.chat.bootstrap.app_module import ChatModule as _ChatModule
from core.kernel.interface import BaseAppModule


class ChatModule(_ChatModule, BaseAppModule):
    pass


def get_module() -> BaseAppModule:
    return ChatModule()


__all__ = ["ChatModule", "get_module"]
