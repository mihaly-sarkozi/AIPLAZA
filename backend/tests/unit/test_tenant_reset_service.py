from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.settings.service.tenant_reset_service import TenantResetService


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def query(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return SimpleNamespace(
            id=1,
            email="owner@test.local",
            name="Owner",
            password_hash="hash",
            is_active=True,
            role="owner",
            created_at=None,
            created_by=None,
            updated_at=None,
            updated_by=None,
            deleted_at=None,
            deleted_by=None,
            registration_completed_at=None,
            failed_login_attempts=0,
            preferred_locale=None,
            preferred_theme=None,
            security_version=0,
            credentials_password_set=True,
            pending_email=None,
            pending_email_token_hash=None,
            pending_email_expires_at=None,
        )

    def execute(self, *_args, **_kwargs):
        return self

    def add(self, *_args, **_kwargs) -> None:
        return None

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


def _session_factory():
    @contextmanager
    def _sf():
        yield _FakeSession()

    _sf.engine = object()
    return _sf


def test_reset_rejects_mismatched_confirm_slug() -> None:
    service = TenantResetService(_session_factory())
    with pytest.raises(ValueError, match="slug"):
        service.reset_tenant(
            tenant_id=7,
            tenant_slug="acme",
            owner_user_id=1,
            confirm_slug="other",
        )


@patch("apps.settings.service.tenant_reset_service.invalidate_tenant_cache")
@patch("apps.settings.service.tenant_reset_service.upgrade_tenant_schema")
@patch("apps.settings.service.tenant_reset_service.drop_tenant_schema")
@patch.object(TenantResetService, "_purge_object_storage")
@patch.object(TenantResetService, "_purge_public_tenant_data")
@patch.object(TenantResetService, "_reset_billing_and_config")
@patch.object(TenantResetService, "_ensure_default_knowledge_base")
@patch.object(TenantResetService, "_restore_owner")
@patch.object(TenantResetService, "_snapshot_owner_auth")
def test_reset_runs_pipeline_when_slug_confirmed(
    snapshot_mock,
    restore_mock,
    default_kb_mock,
    billing_mock,
    public_mock,
    storage_mock,
    drop_mock,
    upgrade_mock,
    invalidate_mock,
) -> None:
    snapshot_mock.return_value = ({"id": 1, "role": "owner"}, None)
    service = TenantResetService(_session_factory())

    result = service.reset_tenant(
        tenant_id=7,
        tenant_slug="acme",
        owner_user_id=1,
        confirm_slug="acme",
    )

    assert result.status == "reset"
    assert result.tenant_slug == "acme"
    snapshot_mock.assert_called_once()
    drop_mock.assert_called_once()
    upgrade_mock.assert_called_once()
    restore_mock.assert_called_once()
    default_kb_mock.assert_called_once()
    billing_mock.assert_called_once()
    public_mock.assert_called_once_with(7)
    storage_mock.assert_called_once_with("acme")
    invalidate_mock.assert_called_once_with("acme")
