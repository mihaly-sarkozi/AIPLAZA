from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.orm import KnowledgeBaseORM as KBORM
from apps.kb.kb_crud.orm import KnowledgeBasePermissionORM as KbUserPermissionORM

pytestmark = pytest.mark.unit


def test_domain_exports_minimal_knowledge_base():
    kb = KnowledgeBase(
        id=1,
        uuid="kb-1",
        name="Test KB",
        description="desc",
        qdrant_collection_name="unused-kept-for-compat",
        personal_data_mode="no_personal_data",
        personal_data_sensitivity="weak",
        pii_depersonalization_enabled=True,
        public_enabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert kb.uuid == "kb-1"
    assert kb.personal_data_mode == "no_personal_data"
    assert kb.pii_depersonalization_enabled is True
    assert kb.is_deleted is False


def test_models_include_only_current_kb_storage_columns():
    assert hasattr(KBORM, "uuid")
    assert hasattr(KBORM, "name")
    assert hasattr(KBORM, "pii_depersonalization_enabled")
    assert hasattr(KbUserPermissionORM, "kb_id")
    assert hasattr(KbUserPermissionORM, "permission")
