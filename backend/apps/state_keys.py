"""App-szintű ModuleContext.state kulcsok.

Az app modulok saját belső wiring kulcsai itt élnek, nem a core interface-ben.
"""
from __future__ import annotations

CTX_STATE_CHAT_INFRASTRUCTURE = "module.chat.infrastructure"
CTX_STATE_KNOWLEDGE_INFRASTRUCTURE = "module.knowledge.infrastructure"
KNOWLEDGE_SERVICE = "module.knowledge.service"

__all__ = [
    "CTX_STATE_CHAT_INFRASTRUCTURE",
    "CTX_STATE_KNOWLEDGE_INFRASTRUCTURE",
    "KNOWLEDGE_SERVICE",
]

