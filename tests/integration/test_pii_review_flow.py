# tests/integration/test_pii_review_flow.py
"""PII review flow: 409 when PII found, confirmation continues processing, without confirm document not indexed."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.application.pii_filter import filter_pii, apply_pii_replacements
from apps.knowledge.application.pii_filter import PiiConfirmationRequiredError
from apps.knowledge.infrastructure.db.models import PERSONAL_DATA_MODE_CONFIRM

pytestmark = pytest.mark.integration

# Legacy PiiMatch = (start, end, data_type, value)
SAMPLE_MATCHES = [(0, 14, "email", "test@example.com")]


@pytest.fixture
def kb_with_confirm_mode():
    """KB that requires PII confirmation."""
    kb = MagicMock()
    kb.id = 1
    kb.uuid = "kb-123"
    kb.personal_data_mode = PERSONAL_DATA_MODE_CONFIRM
    kb.personal_data_sensitivity = "medium"
    return kb


@pytest.fixture
def mock_repo(kb_with_confirm_mode):
    r = MagicMock()
    r.get_by_uuid.return_value = kb_with_confirm_mode
    r.add_personal_data.return_value = "ref-1"
    return r


@pytest.fixture
def service_with_mock_repo(mock_repo):
    return KnowledgeBaseService(repo=mock_repo, qdrant_service=MagicMock(), user_repo=None)


@pytest.mark.release_acceptance
def test_409_returned_when_pii_found(service_with_mock_repo, mock_repo):
    """When PII is detected and confirm_pii is False, add_block raises PiiConfirmationRequiredError (router returns 409)."""
    with patch("apps.knowledge.application.knowledge_service.filter_pii", return_value=SAMPLE_MATCHES):
        async def run():
            with pytest.raises(PiiConfirmationRequiredError) as exc_info:
                await service_with_mock_repo.add_block(
                    "kb-123",
                    "Title",
                    "Contact: test@example.com for info.",
                    current_user_id=None,
                    confirm_pii=False,
                )
            e = exc_info.value
            assert "email" in e.detected_types
            assert getattr(e, "counts", None) is None or e.counts.get("email", 0) >= 1
            assert getattr(e, "snippets", None) is None or len(e.snippets) >= 0
        asyncio.run(run())
    mock_repo.add_training_log.assert_not_called()


@pytest.mark.release_acceptance
def test_confirmation_continues_processing(service_with_mock_repo, mock_repo):
    """With confirm_pii=True, add_block stores sanitized content (standard placeholder) and calls add_training_log."""
    with patch("apps.knowledge.application.knowledge_service.filter_pii", return_value=SAMPLE_MATCHES):
        async def run():
            out = await service_with_mock_repo.add_block(
                "kb-123",
                "Title",
                "Contact: test@example.com for info.",
                current_user_id=None,
                confirm_pii=True,
                pii_review_decision="continue_sanitized",
            )
            assert out["status"] == "ok"
        asyncio.run(run())
    mock_repo.add_training_log.assert_called_once()
    call_kw = mock_repo.add_training_log.call_args
    # ref_id-val: [EMAIL_ADDRESS_ref-1]; ref nélkül: [EMAIL_ADDRESS]
    assert "EMAIL_ADDRESS" in call_kw[1]["content"]
    # Security default: raw_content tárolás alapból tiltott (kb_store_raw_content=False).
    assert call_kw[1]["raw_content"] is None
    assert call_kw[1]["review_decision"] == "continue_sanitized"


@pytest.mark.release_acceptance
def test_without_confirmation_document_not_indexed(service_with_mock_repo, mock_repo):
    """Without confirm_pii, add_block raises before add_training_log; document is not indexed."""
    with patch("apps.knowledge.application.knowledge_service.filter_pii", return_value=SAMPLE_MATCHES):
        async def run():
            with pytest.raises(PiiConfirmationRequiredError):
                await service_with_mock_repo.add_block(
                    "kb-123",
                    "Title",
                    "Contact: test@example.com for info.",
                    current_user_id=None,
                    confirm_pii=False,
                )
        asyncio.run(run())
    mock_repo.add_training_log.assert_not_called()


@pytest.mark.release_acceptance
def test_reject_upload_does_not_store(service_with_mock_repo, mock_repo):
    """With confirm_pii=True and pii_review_decision=reject_upload, returns rejected and does not call add_training_log."""
    with patch("apps.knowledge.application.knowledge_service.filter_pii", return_value=SAMPLE_MATCHES):
        async def run():
            out = await service_with_mock_repo.add_block(
                "kb-123",
                "Title",
                "Contact: test@example.com for info.",
                current_user_id=None,
                confirm_pii=True,
                pii_review_decision="reject_upload",
            )
            assert out["status"] == "rejected"
        asyncio.run(run())
    mock_repo.add_training_log.assert_not_called()


@pytest.mark.release_acceptance
def test_409_payload_has_entity_types_counts_snippets(service_with_mock_repo):
    """PiiConfirmationRequiredError carries detected_types, counts and snippets for rich 409 response."""
    with patch("apps.knowledge.application.knowledge_service.filter_pii", return_value=SAMPLE_MATCHES):
        async def run():
            with pytest.raises(PiiConfirmationRequiredError) as exc_info:
                await service_with_mock_repo.add_block(
                    "kb-123",
                    "T",
                    "Email: test@example.com",
                    current_user_id=None,
                    confirm_pii=False,
                )
            e = exc_info.value
            assert e.detected_types == ["email"]
            assert e.counts == {"email": 1}
            assert len(e.snippets) >= 1
            assert e.snippets[0]["type"] == "email"
            assert "preview" in e.snippets[0]
        asyncio.run(run())
