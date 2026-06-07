from __future__ import annotations


class SubmitFeedbackService:
    async def execute(self, *, knowledge_base_id: str, payload: dict[str, object]) -> str:
        raise NotImplementedError("feedback — későbbi lépés")
