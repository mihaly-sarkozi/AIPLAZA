# backend/core/modules/tenant/service/tenant_domain_verification_service.py
# Feladat: Custom tenant domain DNS verification szolgáltatás. TXT challenge tokeneket és CNAME/IP egyezést ellenőriz, majd siker esetén verified állapotba állítja a tenant domain rekordot. Tenant domain verification service.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hmac
import socket
from hashlib import sha256

import dns.resolver

from core.kernel.config.config_loader import settings
from core.kernel.runtime.clock import utc_now
from core.modules.tenant.ports import TenantWriteRepositoryPort
from core.kernel.domain.errors import DomainDnsVerificationFailedError


class TenantDomainVerificationService:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, tenant_repository: TenantWriteRepositoryPort) -> None:
        self.tenant_repo = tenant_repository

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        return (domain or "").strip().lower()

    @staticmethod
    def _challenge_name(domain: str) -> str:
        return f"_aiplaza-challenge.{domain}"

    @staticmethod
    def _resolve_txt_values(record_name: str) -> set[str]:
        try:
            answers = dns.resolver.resolve(record_name, "TXT")
        except dns.resolver.NXDOMAIN as exc:
            raise DomainDnsVerificationFailedError("dns_txt_not_found") from exc
        except dns.resolver.NoAnswer as exc:
            raise DomainDnsVerificationFailedError("dns_txt_no_answer") from exc
        except Exception as exc:
            raise DomainDnsVerificationFailedError("dns_txt_lookup_failed") from exc

        values: set[str] = set()
        for answer in answers:
            for text_part in getattr(answer, "strings", []):
                decoded = text_part.decode("utf-8", errors="ignore").strip()
                if decoded:
                    values.add(decoded)
            if hasattr(answer, "to_text"):
                text_repr = str(answer.to_text()).strip().strip('"')
                if text_repr:
                    values.add(text_repr)
        if not values:
            raise DomainDnsVerificationFailedError("dns_txt_empty")
        return values

    @staticmethod
    def _challenge_token(domain: str, tenant_id: int) -> str:
        secret = (settings.jwt_secret or settings.tenant_base_domain or "aiplaza").encode("utf-8")
        payload = f"{tenant_id}:{domain}".encode("utf-8")
        digest = hmac.new(secret, payload, sha256).hexdigest()
        return digest[:32]

    @staticmethod
    def _resolve_ips(host: str) -> set[str]:
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise DomainDnsVerificationFailedError("dns_lookup_failed") from exc
        ips = {info[4][0] for info in infos if info and len(info) > 4 and info[4]}
        if not ips:
            raise DomainDnsVerificationFailedError("dns_lookup_empty")
        return ips

    def _assert_dns_points_to_platform(self, domain: str) -> None:
        expected_host = self.cname_target()
        if not expected_host:
            raise DomainDnsVerificationFailedError("platform_host_missing")
        domain_ips = self._resolve_ips(domain)
        expected_ips = self._resolve_ips(expected_host)
        if domain_ips.isdisjoint(expected_ips):
            raise DomainDnsVerificationFailedError("dns_target_mismatch")

    def _assert_dns_challenge(self, domain: str, *, tenant_id: int) -> None:
        record_name, token = self.challenge_for_domain(domain, tenant_id=tenant_id)
        txt_values = self._resolve_txt_values(record_name)
        if token not in txt_values:
            raise DomainDnsVerificationFailedError("dns_txt_token_mismatch")

    def challenge_for_domain(self, domain: str, *, tenant_id: int) -> tuple[str, str]:
        normalized_domain = self._normalize_domain(domain)
        return self._challenge_name(normalized_domain), self._challenge_token(normalized_domain, tenant_id)

    def cname_target(self) -> str:
        return (getattr(settings, "install_host", None) or settings.tenant_base_domain or "").strip().lower()

    # Ez a metódus a(z) verify_domain logikáját valósítja meg.
    def verify_domain(self, domain: str, *, tenant_id: int, actor_user_id: int | None = None):
        normalized_domain = self._normalize_domain(domain)
        self._assert_dns_challenge(normalized_domain, tenant_id=tenant_id)
        self._assert_dns_points_to_platform(normalized_domain)
        return self.tenant_repo.verify_domain(
            normalized_domain,
            verified_at=utc_now(),
            updated_by=actor_user_id,
        )


__all__ = ["TenantDomainVerificationService"]
