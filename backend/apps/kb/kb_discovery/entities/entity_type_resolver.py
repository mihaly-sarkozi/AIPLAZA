from __future__ import annotations

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.enums.EntityType import EntityType


def resolve_entity_type(raw: object, *, entry_name: str, context: DiscoveryContext) -> EntityType:
    value = str(raw or EntityType.OTHER.value).strip().lower()
    try:
        return EntityType(value)
    except ValueError:
        context.dictionary_warnings.append(
            {
                "entry_name": entry_name,
                "invalid_type": value,
                "fallback": EntityType.OTHER.value,
            }
        )
        return EntityType.OTHER


__all__ = ["resolve_entity_type"]
