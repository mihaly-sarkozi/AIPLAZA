from __future__ import annotations

from sqlalchemy import func, select

from apps.kb.kb_processing.enums.ProcessingIssueStatus import TERMINAL_ISSUE_STATUSES
from apps.kb.kb_processing.orm.ProcessingIssue import ProcessingIssue
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class ProcessingIssueRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def find_dedup(
        self,
        *,
        knowledge_base_id: str,
        training_item_id: str | None,
        module: str,
        stage: str,
        issue_code: str,
    ) -> ProcessingIssue | None:
        with self._session_factory() as session:
            issue = session.execute(
                select(ProcessingIssue).where(
                    ProcessingIssue.knowledge_base_id == knowledge_base_id,
                    ProcessingIssue.training_item_id == training_item_id,
                    ProcessingIssue.module == module,
                    ProcessingIssue.stage == stage,
                    ProcessingIssue.issue_code == issue_code,
                )
            ).scalar_one_or_none()
            if issue is not None:
                session.expunge(issue)
            return issue

    def upsert_open(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_batch_id: str | None,
        training_item_id: str | None,
        job_id: str | None,
        module: str,
        stage: str,
        step: str | None,
        severity: str,
        issue_code: str,
        issue_message: str | None,
        metadata_json: dict | None = None,
    ) -> ProcessingIssue:
        now = utc_now_naive()
        with self._session_factory() as session:
            issue = session.execute(
                select(ProcessingIssue).where(
                    ProcessingIssue.knowledge_base_id == knowledge_base_id,
                    ProcessingIssue.training_item_id == training_item_id,
                    ProcessingIssue.module == module,
                    ProcessingIssue.stage == stage,
                    ProcessingIssue.issue_code == issue_code,
                )
            ).scalar_one_or_none()
            if issue is None:
                issue = ProcessingIssue(
                    id=new_id("proc_issue"),
                    tenant_slug=tenant_slug,
                    knowledge_base_id=knowledge_base_id,
                    training_batch_id=training_batch_id,
                    training_item_id=training_item_id,
                    job_id=job_id,
                    module=module,
                    stage=stage,
                    step=step,
                    severity=severity,
                    issue_code=issue_code,
                    issue_message=(issue_message or "")[:4000] or None,
                    status="OPEN",
                    first_seen_at=now,
                    last_seen_at=now,
                    occurrence_count=1,
                    metadata_json=dict(metadata_json or {}),
                )
                session.add(issue)
            else:
                issue.occurrence_count = int(issue.occurrence_count or 0) + 1
                issue.last_seen_at = now
                issue.severity = severity
                if issue_message:
                    issue.issue_message = issue_message[:4000]
                if job_id:
                    issue.job_id = job_id
                if step:
                    issue.step = step
                if metadata_json:
                    issue.metadata_json = {**(issue.metadata_json or {}), **metadata_json}
                if issue.status in {s.value for s in TERMINAL_ISSUE_STATUSES}:
                    issue.status = "OPEN"
                    issue.resolved_at = None
            session.commit()
            session.refresh(issue)
            session.expunge(issue)
            return issue

    def update_status(self, issue_id: str, *, status: str, resolved_at=None) -> ProcessingIssue | None:
        with self._session_factory() as session:
            issue = session.get(ProcessingIssue, issue_id)
            if issue is None:
                return None
            issue.status = status
            issue.resolved_at = resolved_at
            session.commit()
            session.refresh(issue)
            session.expunge(issue)
            return issue

    def list_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        training_item_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProcessingIssue]:
        with self._session_factory() as session:
            query = select(ProcessingIssue).where(ProcessingIssue.knowledge_base_id == knowledge_base_id)
            if training_item_id:
                query = query.where(ProcessingIssue.training_item_id == training_item_id)
                query = query.where(ProcessingIssue.status == status)
            if severity:
                query = query.where(ProcessingIssue.severity == severity)
            rows = list(
                session.execute(
                    query.order_by(ProcessingIssue.last_seen_at.desc(), ProcessingIssue.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows

    def count_open_by_severity(self, knowledge_base_id: str) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ProcessingIssue.severity, func.count())
                .where(
                    ProcessingIssue.knowledge_base_id == knowledge_base_id,
                    ProcessingIssue.status == "OPEN",
                )
                .group_by(ProcessingIssue.severity)
            ).all()
            return {str(severity): int(count) for severity, count in rows}


__all__ = ["ProcessingIssueRepository"]
