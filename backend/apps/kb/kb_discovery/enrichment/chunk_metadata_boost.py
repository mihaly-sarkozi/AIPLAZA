from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto


def chunk_metadata_boost(chunk: DiscoveryChunkDto) -> float:
    boost = 0.0
    metadata = chunk.metadata or {}
    if chunk.section_title:
        boost += 0.15
    if metadata.get("heading_path"):
        boost += 0.1
    if metadata.get("table_refs") or chunk.chunk_type == "table":
        boost += 0.1
    if metadata.get("is_from_ocr"):
        boost -= 0.2
    if len(chunk.text.strip()) < 40:
        boost -= 0.15
    return boost


def heading_terms(chunk: DiscoveryChunkDto) -> list[str]:
    terms: list[str] = []
    if chunk.section_title:
        terms.append(chunk.section_title.strip())
    heading_path = chunk.metadata.get("heading_path") if chunk.metadata else None
    if isinstance(heading_path, list):
        terms.extend(str(item).strip() for item in heading_path if str(item).strip())
    return terms


__all__ = ["chunk_metadata_boost", "heading_terms"]
