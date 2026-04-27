# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
from typing import Any

from pydantic import BaseModel, Field


class ChatSourceItem(BaseModel):
    kb_uuid: str
    point_id: str
    source_id: str = ""
    title: str = ""
    snippet: str = ""
    source_type: str = ""
    file_ref: str | None = None
    display_type: str = ""
    created_by: int | None = None
    created_by_label: str = ""


class AskResponse(BaseModel):
    answer: str
    query_run_id: str | None = None
    sources: list[ChatSourceItem] = Field(default_factory=list)
    debug: dict[str, Any] | None = Field(default=None)
    answer_mode: str = "no_answer"
    answer_source: str = "none"
    confidence: float = 0.0
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    cited_claim_ids: list[str] = Field(default_factory=list)
    cited_sentence_ids: list[str] = Field(default_factory=list)
    cited_source_ids: list[str] = Field(default_factory=list)
    query_profile: dict[str, Any] = Field(default_factory=dict)
    matched_chunks: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
