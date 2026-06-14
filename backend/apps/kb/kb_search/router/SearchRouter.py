from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.kb.kb_search.bootstrap.dependencies import get_kb_search_pipeline
from core.modules.auth.web.dependencies.auth_dependencies import require_permission


router = APIRouter(prefix="/kb/search", tags=["kb-search"])


class SearchRequestBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=2400)
    kb_uuid: str = Field(..., min_length=1)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    debug: bool = False
    top_k: int | None = Field(default=None, ge=1, le=50)


@router.post("")
async def search_knowledge_base(
    body: SearchRequestBody,
    tenant_slug: str | None = None,
    pipeline=Depends(get_kb_search_pipeline),
    _user=Depends(require_permission("kb.read")),
):
    try:
        return pipeline.execute(
            question=body.question,
            knowledge_base_id=body.kb_uuid,
            kb_uuid=body.kb_uuid,
            tenant_slug=tenant_slug,
            conversation_history=body.conversation_history,
            top_k=body.top_k,
            debug=body.debug,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


__all__ = ["router"]
