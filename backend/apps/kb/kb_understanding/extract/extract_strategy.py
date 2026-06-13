from __future__ import annotations

from apps.kb.kb_understanding.config.ExtractConfig import ExtractConfig
from apps.kb.kb_understanding.enums.ExtractStrategy import ExtractStrategy


def resolve_extract_strategy(file_size_bytes: int, config: ExtractConfig) -> ExtractStrategy:
    if file_size_bytes > config.max_extract_file_size_bytes:
        return ExtractStrategy.REJECTED_TOO_LARGE
    if file_size_bytes <= config.small_file_max_bytes:
        return ExtractStrategy.IN_MEMORY
    if file_size_bytes <= config.large_file_max_bytes:
        return ExtractStrategy.TEMP_FILE
    return ExtractStrategy.STREAMING


def file_size_mb(file_size_bytes: int) -> float:
    return round(file_size_bytes / (1024 * 1024), 2)


__all__ = ["file_size_mb", "resolve_extract_strategy"]
