from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/UnderstandingStepRunRepository.py
# Feladat: Pipeline-lépés futási napló perzisztencia (append-only trace).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import select

from apps.kb.kb_understanding.dto.UnderstandingStepResult import UnderstandingStepResult
from apps.kb.kb_understanding.orm.UnderstandingStepRun import UnderstandingStepRun
from apps.kb.shared.ids import new_id


class UnderstandingStepRunRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def add_run(self, job_id: str, result: UnderstandingStepResult) -> str:
        run = UnderstandingStepRun(
            id=new_id("und_step"),
            job_id=job_id,
            step=result.step.value,
            status=result.status,
            input_summary=dict(result.input_summary),
            output_summary=dict(result.output_summary),
            duration_ms=result.duration_ms,
            error_code=result.error_code,
            error_message=(result.error_message or "")[:4000] or None,
        )
        with self._session_factory() as session:
            session.add(run)
            session.commit()
            return run.id

    def list_for_job(self, job_id: str) -> list[UnderstandingStepRun]:
        with self._session_factory() as session:
            runs = list(
                session.execute(
                    select(UnderstandingStepRun)
                    .where(UnderstandingStepRun.job_id == job_id)
                    .order_by(UnderstandingStepRun.created_at.asc(), UnderstandingStepRun.id.asc())
                )
                .scalars()
                .all()
            )
            for run in runs:
                session.expunge(run)
            return runs


__all__ = ["UnderstandingStepRunRepository"]
