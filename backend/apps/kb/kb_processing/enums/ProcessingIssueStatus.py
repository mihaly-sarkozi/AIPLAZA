from __future__ import annotations

from enum import Enum


class ProcessingIssueStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


TERMINAL_ISSUE_STATUSES = frozenset(
    {
        ProcessingIssueStatus.RESOLVED,
        ProcessingIssueStatus.IGNORED,
    }
)


__all__ = ["TERMINAL_ISSUE_STATUSES", "ProcessingIssueStatus"]
