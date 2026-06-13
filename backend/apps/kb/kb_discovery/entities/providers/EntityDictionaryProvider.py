from __future__ import annotations

from typing import Any, Protocol

from apps.kb.kb_discovery.gazetteers.EntityDictionaryGazetteer import EntityDictionaryGazetteer


class EntityDictionaryProvider(Protocol):
    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]: ...


class DefaultEntityDictionaryProvider:
    def __init__(self, gazetteer: EntityDictionaryGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or EntityDictionaryGazetteer()

    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]:
        return self._gazetteer.default_entries()


class TenantEntityDictionaryProvider:
    def __init__(self, gazetteer: EntityDictionaryGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or EntityDictionaryGazetteer()

    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]:
        if not tenant_slug:
            return []
        return self._gazetteer.tenant_entries(tenant_slug)


class KnowledgeBaseEntityDictionaryProvider:
    def __init__(self, gazetteer: EntityDictionaryGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or EntityDictionaryGazetteer()

    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]:
        return self._gazetteer.knowledge_base_entries(knowledge_base_id)


class CompositeEntityDictionaryProvider:
    def __init__(self, *providers: EntityDictionaryProvider) -> None:
        self._providers = providers

    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for provider in self._providers:
            for entry in provider.load(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
            ):
                name = str(entry.get("name") or "").strip().casefold()
                entity_type = str(entry.get("type") or "other").strip().casefold()
                if not name:
                    continue
                key = (entity_type, name)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(dict(entry))
        return merged


def build_default_entity_dictionary_provider() -> CompositeEntityDictionaryProvider:
    gazetteer = EntityDictionaryGazetteer()
    return CompositeEntityDictionaryProvider(
        DefaultEntityDictionaryProvider(gazetteer),
        TenantEntityDictionaryProvider(gazetteer),
        KnowledgeBaseEntityDictionaryProvider(gazetteer),
    )


__all__ = [
    "CompositeEntityDictionaryProvider",
    "DefaultEntityDictionaryProvider",
    "EntityDictionaryProvider",
    "KnowledgeBaseEntityDictionaryProvider",
    "TenantEntityDictionaryProvider",
    "build_default_entity_dictionary_provider",
]
