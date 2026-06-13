from __future__ import annotations

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_json


class SystemsGazetteer:
    def __init__(self) -> None:
        payload = load_json(data_file("systems", "default_systems.json"), {})
        default = payload.get("default") if isinstance(payload, dict) else payload
        self._default = tuple(
            str(item).strip() for item in (default or []) if str(item).strip()
        )

    def systems_for(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        extra: tuple[str, ...] | None = None,
    ) -> tuple[str, ...]:
        names: list[str] = list(self._default)
        if tenant_slug:
            tenant_payload = load_json(
                data_file("systems", "tenants", f"{tenant_slug}.json"),
                [],
            )
            names.extend(self._names_from_payload(tenant_payload))
        kb_payload = load_json(
            data_file("systems", "knowledge_bases", f"{knowledge_base_id}.json"),
            [],
        )
        names.extend(self._names_from_payload(kb_payload))
        if extra:
            names.extend(extra)
        return tuple(dict.fromkeys(name for name in names if name))

    @staticmethod
    def _names_from_payload(payload: object) -> list[str]:
        if isinstance(payload, list):
            return [str(item).strip() for item in payload if str(item).strip()]
        if isinstance(payload, dict):
            systems = payload.get("systems") or payload.get("default") or []
            return [str(item).strip() for item in systems if str(item).strip()]
        return []


__all__ = ["SystemsGazetteer"]
