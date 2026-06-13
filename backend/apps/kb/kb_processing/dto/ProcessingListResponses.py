from __future__ import annotations

from pydantic import BaseModel, Field

from apps.kb.kb_processing.dto.ProcessingEventSummary import ProcessingEventSummary
from apps.kb.kb_processing.dto.ProcessingIssueSummary import ProcessingIssueSummary


class ProcessingEventsPage(BaseModel):
    items: list[ProcessingEventSummary] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0


class ProcessingIssuesPage(BaseModel):
    items: list[ProcessingIssueSummary] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0


__all__ = ["ProcessingEventsPage", "ProcessingIssuesPage"]
