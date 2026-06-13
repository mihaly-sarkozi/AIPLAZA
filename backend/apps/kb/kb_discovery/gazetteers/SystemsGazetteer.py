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
        names = list(self._default)
        if extra:
            names.extend(extra)
        return tuple(dict.fromkeys(name for name in names if name))


__all__ = ["SystemsGazetteer"]
