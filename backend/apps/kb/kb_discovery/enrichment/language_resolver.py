from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage


def resolve_chunk_language(chunk: DiscoveryChunkDto) -> tuple[str, bool]:
    code = (chunk.language_code or "").strip().lower()
    if not code:
        return SupportedLanguage.UNKNOWN.value, True
    if code in {SupportedLanguage.MIXED.value, SupportedLanguage.UNKNOWN.value}:
        return code, True
    if code in SupportedLanguage._value2member_map_:
        return code, False
    return SupportedLanguage.UNKNOWN.value, True


def supported_language(code: str) -> SupportedLanguage:
    normalized = (code or "").strip().lower()
    if normalized in SupportedLanguage._value2member_map_:
        return SupportedLanguage(normalized)
    return SupportedLanguage.UNKNOWN


__all__ = ["resolve_chunk_language", "supported_language"]
