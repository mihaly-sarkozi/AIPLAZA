# apps/knowledge/pii_gdpr/policy/legacy_mapping.py
"""
EntityType (pii_gdpr) → legacy type name (pii layer, placeholder key). Built from entity_registry.
"""
from __future__ import annotations

from apps.knowledge.pii_gdpr.entity_registry import ENTITY_REGISTRY
from apps.knowledge.pii_gdpr.enums import EntityType

ENTITY_TYPE_TO_LEGACY: dict[str, str] = {
    et.value: legacy for et, _status, legacy, _sens, _note in ENTITY_REGISTRY if legacy
}


def get_legacy_name(entity_type: EntityType | str) -> str:
    """EntityType → legacy name; unknown → lowercase with underscores."""
    key = entity_type.value if hasattr(entity_type, "value") else str(entity_type)
    return ENTITY_TYPE_TO_LEGACY.get(key, key.lower().replace(" ", "_"))
