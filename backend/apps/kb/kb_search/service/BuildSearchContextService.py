from __future__ import annotations

from apps.kb.kb_search.schemas.SearchRequest import SearchRequest


class BuildSearchContextService:
    async def execute(self, request: SearchRequest) -> dict[str, object]:
        raise NotImplementedError("search — 5. lépés")
