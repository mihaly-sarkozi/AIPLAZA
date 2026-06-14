from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.kb.kb_search.bootstrap.dependencies import get_kb_search_pipeline
from apps.kb.kb_search.router.search_http_errors import map_search_exception, raise_if_blocked_search_result
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user, require_permission
from core.modules.users.domain.dto import User


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
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    pipeline=Depends(get_kb_search_pipeline),
    _perm=Depends(require_permission("kb.read")),
):
    try:
        result = pipeline.execute(
            question=body.question,
            knowledge_base_id=body.kb_uuid,
            kb_uuid=body.kb_uuid,
            tenant_slug=getattr(tenant, "slug", None),
            user_id=current_user.id,
            conversation_history=body.conversation_history,
            top_k=body.top_k,
            debug=body.debug,
        )
        raise_if_blocked_search_result(result)
        return result
    except Exception as exc:
        raise map_search_exception(exc) from exc


__all__ = ["router"]
