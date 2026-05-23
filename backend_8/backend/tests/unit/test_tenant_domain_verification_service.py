from __future__ import annotations

import pytest

from core.modules.tenant.service.tenant_domain_verification_service import TenantDomainVerificationService
from core.kernel.domain.errors import DomainDnsVerificationFailedError

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _Repo:
    def __init__(self) -> None:
        self.called_with: str | None = None

    def verify_domain(self, domain: str, *, verified_at=None, updated_by=None):  # type: ignore[no-untyped-def]
        self.called_with = domain
        return {"domain": domain, "verified_at": verified_at, "updated_by": updated_by}


def test_verify_domain_marks_verified_when_dns_target_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _Repo()
    svc = TenantDomainVerificationService(repo)  # type: ignore[arg-type]

    monkeypatch.setattr(
        svc,
        "_resolve_ips",
        lambda host: {"10.0.0.1"} if host in {"example.com", "lvh.me"} else {"10.0.0.2"},
    )
    monkeypatch.setattr(
        svc,
        "_resolve_txt_values",
        lambda _record_name: {svc.challenge_for_domain("example.com", tenant_id=11)[1]},
    )
    monkeypatch.setattr("core.modules.tenant.service.tenant_domain_verification_service.settings.install_host", "lvh.me")
    monkeypatch.setattr("core.modules.tenant.service.tenant_domain_verification_service.settings.tenant_base_domain", "lvh.me")

    result = svc.verify_domain("example.com", tenant_id=11, actor_user_id=7)

    assert repo.called_with == "example.com"
    assert result["updated_by"] == 7


def test_verify_domain_rejects_when_dns_target_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _Repo()
    svc = TenantDomainVerificationService(repo)  # type: ignore[arg-type]

    monkeypatch.setattr(
        svc,
        "_resolve_ips",
        lambda host: {"10.0.0.1"} if host == "lvh.me" else {"10.0.0.2"},
    )
    monkeypatch.setattr(
        svc,
        "_resolve_txt_values",
        lambda _record_name: {svc.challenge_for_domain("wrong.example.com", tenant_id=11)[1]},
    )
    monkeypatch.setattr("core.modules.tenant.service.tenant_domain_verification_service.settings.install_host", "lvh.me")
    monkeypatch.setattr("core.modules.tenant.service.tenant_domain_verification_service.settings.tenant_base_domain", "lvh.me")

    with pytest.raises(DomainDnsVerificationFailedError) as exc:
        svc.verify_domain("wrong.example.com", tenant_id=11, actor_user_id=7)

    assert exc.value.reason == "dns_target_mismatch"
    assert repo.called_with is None


def test_verify_domain_rejects_when_txt_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _Repo()
    svc = TenantDomainVerificationService(repo)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_resolve_txt_values", lambda _record_name: {"wrong-token"})
    monkeypatch.setattr(svc, "_resolve_ips", lambda _host: {"10.0.0.1"})
    monkeypatch.setattr("core.modules.tenant.service.tenant_domain_verification_service.settings.install_host", "lvh.me")
    monkeypatch.setattr("core.modules.tenant.service.tenant_domain_verification_service.settings.tenant_base_domain", "lvh.me")

    with pytest.raises(DomainDnsVerificationFailedError) as exc:
        svc.verify_domain("example.com", tenant_id=11, actor_user_id=7)

    assert exc.value.reason == "dns_txt_token_mismatch"
    assert repo.called_with is None
