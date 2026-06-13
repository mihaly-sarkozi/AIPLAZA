from __future__ import annotations

from typing import Any

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_json


class EntityDictionaryGazetteer:
    def default_entries(self) -> list[dict[str, Any]]:
        payload = load_json(data_file("dictionaries", "default_entities.json"), [])
        return [self._normalize_entry(item) for item in payload if isinstance(item, dict)]

    def tenant_entries(self, tenant_slug: str) -> list[dict[str, Any]]:
        path = data_file("dictionaries", "tenants", f"{tenant_slug}.json")
        payload = load_json(path, [])
        return [self._normalize_entry(item) for item in payload if isinstance(item, dict)]

    def knowledge_base_entries(self, knowledge_base_id: str) -> list[dict[str, Any]]:
        path = data_file("dictionaries", "knowledge_bases", f"{knowledge_base_id}.json")
        payload = load_json(path, [])
        return [self._normalize_entry(item) for item in payload if isinstance(item, dict)]

    @staticmethod
    def _normalize_entry(item: dict[str, Any]) -> dict[str, Any]:
        aliases = [str(alias).strip() for alias in (item.get("aliases") or []) if str(alias).strip()]
        return {
            "name": str(item.get("name") or "").strip(),
            "type": str(item.get("type") or "other").strip().lower(),
            "confidence": float(item.get("confidence") or 0.8),
            "aliases": aliases,
        }


__all__ = ["EntityDictionaryGazetteer"]
