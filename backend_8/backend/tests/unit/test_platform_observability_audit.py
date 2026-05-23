from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.brand.service.brand_service import BrandService
from core.modules.brand.web.requests.brand_update_request import BrandUpdateRequest
from core.modules.settings.service.settings_service import SettingsService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _AuditStub:
    def __init__(self) -> None:
        self.calls = []

    def log(self, action, **kwargs):
        self.calls.append((action, kwargs))


class _SettingsRepoStub:
    def __init__(self, initial: str | None = "false") -> None:
        self.value = initial

    def get_by_key(self, key: str) -> str | None:
        return self.value

    def set_value(self, key: str, value: str, *, updated_by: int | None = None) -> None:
        self.value = value


class _BrandRepoStub:
    def __init__(self) -> None:
        self.updated = None

    def get_settings(self):
        return None

    def upsert_settings(self, **kwargs):
        self.updated = kwargs
        return SimpleNamespace(**kwargs)


def test_settings_service_audits_security_sensitive_change():
    repo = _SettingsRepoStub(initial="false")
    audit = _AuditStub()
    service = SettingsService(repo, audit_service=audit)

    service.set_two_factor_enabled(True, updated_by=9)

    assert audit.calls[0][0] == AuditLogAction.SETTINGS_SECURITY_UPDATED
    assert audit.calls[0][1]["user_id"] == 9
    assert audit.calls[0][1]["target_id"] == "two_factor_enabled"


def test_brand_service_audits_platform_admin_write():
    repo = _BrandRepoStub()
    audit = _AuditStub()
    service = BrandService(repo, audit_service=audit)

    service.update_brand(
        BrandUpdateRequest(
            display_name="AIPLAZA",
            logo_url="https://cdn.example.com/logo.png",
            primary_color="#2563eb",
            support_email="support@example.com",
            public_enabled=True,
        ),
        updated_by=12,
    )

    assert audit.calls[0][0] == AuditLogAction.BRAND_UPDATED
    assert audit.calls[0][1]["user_id"] == 12
