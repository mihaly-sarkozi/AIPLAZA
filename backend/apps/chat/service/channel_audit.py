from __future__ import annotations

from typing import Any


def build_web_channel_audit(*, channel_id: str | None = None) -> tuple[str, dict[str, Any]]:
    resolved = str(channel_id or "web").strip() or "web"
    return resolved, {
        "channel_type": resolved,
        "channel_credential_id": "",
        "source": "web_chat",
    }


def build_channel_api_audit(
    *,
    channel_type: str | None,
    credential_id: str | None,
    external_session_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    resolved_type = str(channel_type or "channel").strip().lower() or "channel"
    credential = str(credential_id or "").strip()
    channel_id = f"{resolved_type}:{credential}" if credential else resolved_type
    metadata = {
        "channel_type": resolved_type,
        "channel_credential_id": credential,
        "source": "channel_api",
    }
    if external_session_id:
        metadata["external_session_id"] = str(external_session_id)
    return channel_id, metadata


def merge_search_run_metadata(
    *,
    channel_metadata: dict[str, Any] | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    metadata = dict(channel_metadata or {})
    if conversation_id:
        metadata["conversation_id"] = str(conversation_id)
    return metadata


__all__ = ["build_channel_api_audit", "build_web_channel_audit", "merge_search_run_metadata"]
