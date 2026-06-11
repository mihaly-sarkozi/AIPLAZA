from __future__ import annotations

# backend/apps/kb/kb_understanding/validation/ValidateEntities.py
# Feladat: Entitások szűrése — az érvénytelen elemek kiesnek, nem buktatják a lépést.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto


class ValidateEntities:
    def __call__(self, entities: list[KnowledgeEntityDto]) -> list[KnowledgeEntityDto]:
        valid: list[KnowledgeEntityDto] = []
        for entity in entities:
            if not (entity.name or "").strip():
                continue
            if not (entity.normalized_name or "").strip():
                continue
            if not 0.0 <= entity.confidence <= 1.0:
                continue
            valid.append(entity)
        return valid


__all__ = ["ValidateEntities"]
