from __future__ import annotations


class RunKnowledgeTestService:
    async def execute(self, *, test_id: str) -> dict[str, object]:
        raise NotImplementedError("testing — későbbi lépés")
