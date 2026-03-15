from __future__ import annotations

from typing import Any

from apps.knowledge.application.scoring import determine_assertion_status


class KnowledgeMaintenanceService:
    """Karbantartó és diagnosztikai szolgáltatások a retrieval réteghez."""

    def __init__(self, kb_service: Any, repo: Any) -> None:
        self.kb_service = kb_service
        self.repo = repo

    async def recompute_local_relations_for_source_point(self, kb_uuid: str, source_point_id: str) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        # Reindex lokális scope-ból újraépíti a relationöket is.
        result = await self.kb_service.reindex_training_point(kb_uuid=kb_uuid, point_id=source_point_id)
        return {"status": "ok", "source_point_id": source_point_id, "result": result}

    def recompute_assertion_statuses_for_kb(self, kb_uuid: str, batch_limit: int = 5000) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        rows = self.repo.list_assertions_for_kb(kb.id, limit=batch_limit, offset=0)
        updated = 0
        for row in rows:
            aid = int(row["id"])
            relations = self.repo.list_assertion_relations([aid], limit=100)
            status = determine_assertion_status(
                confidence=float(row.get("confidence") or 0.0),
                evidence_count=int(row.get("evidence_count") or 0),
                relations=relations,
            )
            if self.repo.update_assertion_status(kb_id=kb.id, assertion_id=aid, status=status):
                updated += 1
        return {"status": "ok", "updated": updated}

    def decay_strengths_for_kb(self, kb_uuid: str, batch_limit: int = 5000) -> dict:
        return self.kb_service.decay_strengths_for_kb(kb_uuid=kb_uuid, batch_limit=batch_limit)

    async def rebuild_qdrant_payloads_for_kb(self, kb_uuid: str) -> dict:
        return await self.kb_service.reindex_kb(kb_uuid=kb_uuid)

    async def rebuild_assertion_relations_for_kb(self, kb_uuid: str) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        logs = self.repo.list_training_log_paginated(kb_uuid=kb_uuid, limit=20000, offset=0, include_raw_content=False)
        rebuilt = 0
        for row in logs:
            point_id = row.get("point_id")
            if not point_id:
                continue
            await self.recompute_local_relations_for_source_point(kb_uuid=kb_uuid, source_point_id=point_id)
            rebuilt += 1
        return {"status": "ok", "rebuilt_source_points": rebuilt}

    def recompute_all_statuses_for_kb(self, kb_uuid: str, batch_limit: int = 5000) -> dict:
        return self.recompute_assertion_statuses_for_kb(kb_uuid=kb_uuid, batch_limit=batch_limit)

    def get_assertion_debug(self, kb_uuid: str, assertion_id: int) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.get_assertion_debug(kb.id, assertion_id)

    def get_entity_debug(self, kb_uuid: str, entity_id: int) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.get_entity_debug(kb.id, entity_id)

    def get_source_point_debug(self, kb_uuid: str, point_id: str) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.get_source_point_debug(kb.id, point_id)

    def get_relation_bundle(self, kb_uuid: str, assertion_id: int) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.get_relation_bundle(kb.id, assertion_id, limit=120)

    def get_metric_snapshot(self, kb_uuid: str) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.get_metric_snapshot(kb.id)
