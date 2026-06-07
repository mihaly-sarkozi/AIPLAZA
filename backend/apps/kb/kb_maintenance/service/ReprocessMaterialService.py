from __future__ import annotations


class ReprocessMaterialService:
    async def execute(self, *, material_id: str) -> str:
        raise NotImplementedError("maintenance — későbbi lépés")
