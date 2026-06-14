# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
from typing import Any

from pydantic import BaseModel, Field


class ChatSourceItem(BaseModel):
    kb_uuid: str
    kb_name: str = ""
    point_id: str
    source_id: str = ""
    citation_id: str = ""
    title: str = ""
    snippet: str = ""
    source_type: str = ""
    download_url: str | None = None
    download_url_template: str | None = None
    download_ref: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    section_title: str = ""
    file_ref: str | None = None
    display_type: str = ""
    created_by: int | None = None
    created_by_label: str = ""
    created_at: str | None = None


class AskResponse(BaseModel):
    answer: str
    conversation_id: str | None = None
    turn_id: str | None = None
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
    citations: list[str] = Field(default_factory=list)
    citation_records: list[dict[str, Any]] = Field(default_factory=list)
    query_profile: dict[str, Any] = Field(default_factory=dict)
    matched_chunks: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    context_blocks: list[dict[str, Any]] = Field(default_factory=list)
    readiness: dict[str, Any] = Field(default_factory=dict)
    prompt_context: dict[str, Any] = Field(default_factory=dict)
    encoded_prompt_context: str = ""
    restored_pii_spans: list[dict[str, Any]] = Field(default_factory=list)
