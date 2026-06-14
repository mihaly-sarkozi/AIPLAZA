from __future__ import annotations

from apps.chat.orm.ChatSession import ChatSession
from apps.chat.orm.ChatTurn import ChatTurn
from apps.chat.orm.ChatTurnContextSnapshot import ChatTurnContextSnapshot
from core.modules.tenant.service import TenantSchemaHook, install_schema_tables, register_tenant_schema_hooks


def _install_chat_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            ChatSession.__table__,
            ChatTurn.__table__,
            ChatTurnContextSnapshot.__table__,
        ),
    )


def register_chat_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="chat",
                revision="chat.schema.v1",
                install=_install_chat_schema,
                table_names=(
                    "chat_sessions",
                    "chat_turns",
                    "chat_turn_context_snapshots",
                ),
            )
        ]
    )


__all__ = ["register_chat_tenant_hooks"]
