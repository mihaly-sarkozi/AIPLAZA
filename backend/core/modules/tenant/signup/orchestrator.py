# backend/core/modules/tenant/signup/orchestrator.py
# Feladat: A demo signup orchestration központi use case-e. Abuse controlt, slug foglalást, új demo signupot, resend és unsubscribe folyamatokat, hookokat és email/token döntéseket fog össze. Összetett tenant onboarding koordinátor.
# Sárközi Mihály - 2026.05.21

"""Tenant signup orchestrator.

Responsibility: validate incoming signup parameters and dispatch to the
appropriate focused use case:
- ``DemoSlugReserver``        – slug generation and reservation
- ``DemoSignupResendUseCase`` – resend existing demo access
- ``DemoNewSignupUseCase``    – brand-new demo tenant creation
- ``DemoUnsubscribeUseCase``  – deletion request and email block

This class is intentionally thin: all business logic lives in the use cases.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

import dns.exception
import dns.resolver

from core.modules.tenant.signup.abuse_controls import bump_daily_counter, is_demo_signup_enabled
from core.modules.tenant.ports import TenantRepositoryPort
from core.modules.tenant.slug.policy import normalize_demo_locale
from core.modules.tenant.repositories.demo_signup_repository import DemoSignupRepository
from core.modules.tenant.signup.new_demo_signup import DemoNewSignupUseCase
from core.modules.tenant.signup.orchestrator_result import DemoSignupResult
from core.modules.tenant.signup.resend_demo import DemoSignupResendUseCase
from core.modules.tenant.slug.reservation import DemoSlugReserver
from core.modules.tenant.tokens.demo_jwt import DemoLoginTokenService
from core.modules.tenant.signup.unsubscribe import DemoUnsubscribeUseCase
from core.modules.tenant.signup.errors import (
    DemoAlreadyExistsError,
    DemoSignupCapacityReachedError,
    DemoSignupDisabledError,
    DemoSignupDisposableEmailError,
    DemoSessionRequiredError,
    DemoEmailBlockedError,
    DemoSignupInvalidEmailDomainError,
    DemoSignupRateLimitedError,
    InvalidSlugError,
    NameRequiredError,
)
from core.kernel.config.config_loader import settings
from core.kernel.logging.observability import increment_metric
from core.modules.tenant.extensions.tenant_hooks import get_tenant_signup_hooks
from shared.utils.slug import slug_is_valid

_DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "yopmail.com",
    "dispostable.com",
    "trashmail.com",
    "sharklasers.com",
    "getnada.com",
}
_EXTERNAL_DOMAINS_CACHE_LOCK = threading.RLock()
_EXTERNAL_DOMAINS_CACHE_PATH: str = ""
_EXTERNAL_DOMAINS_CACHE_MTIME: float | None = None
_EXTERNAL_DOMAINS_CACHE_VALUES: set[str] = set()


def _external_disposable_domains() -> set[str]:
    path_raw = str(getattr(settings, "demo_signup_external_disposable_domains_path", "") or "").strip()
    if not path_raw:
        return set()
    path = Path(path_raw)
    try:
        stat = path.stat()
    except Exception:
        return set()
    with _EXTERNAL_DOMAINS_CACHE_LOCK:
        global _EXTERNAL_DOMAINS_CACHE_PATH, _EXTERNAL_DOMAINS_CACHE_MTIME, _EXTERNAL_DOMAINS_CACHE_VALUES
        if (
            _EXTERNAL_DOMAINS_CACHE_PATH == str(path)
            and _EXTERNAL_DOMAINS_CACHE_MTIME == float(stat.st_mtime)
        ):
            return set(_EXTERNAL_DOMAINS_CACHE_VALUES)
        values: set[str] = set()
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                normalized = raw.strip().lower()
                if not normalized or normalized.startswith("#"):
                    continue
                values.add(normalized)
        except Exception:
            values = set()
        _EXTERNAL_DOMAINS_CACHE_PATH = str(path)
        _EXTERNAL_DOMAINS_CACHE_MTIME = float(stat.st_mtime)
        _EXTERNAL_DOMAINS_CACHE_VALUES = values
        return set(values)


class TenantSignupOrchestrator:
    def __init__(
        self,
        *,
        tenant_repository: TenantRepositoryPort,
        user_service,
        provisioning_service,
        demo_signup_repository: DemoSignupRepository,
        demo_login_token_service: DemoLoginTokenService,
        tenant_base_domain: str,
        clock,
        tenant_signup_hooks_provider=None,
        audit_service=None,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._demo_signup_repo = demo_signup_repository
        self._clock = clock

        self._slug_reserver = DemoSlugReserver(
            tenant_repo=tenant_repository,
            demo_signup_repository=demo_signup_repository,
        )
        self._resend_use_case = DemoSignupResendUseCase(
            tenant_repo=tenant_repository,
            user_service=user_service,
            demo_signup_repository=demo_signup_repository,
            demo_login_token_service=demo_login_token_service,
            tenant_base_domain=tenant_base_domain,
            clock=clock,
        )
        self._new_signup_use_case = DemoNewSignupUseCase(
            tenant_repo=tenant_repository,
            user_service=user_service,
            provisioning_service=provisioning_service,
            demo_signup_repository=demo_signup_repository,
            demo_login_token_service=demo_login_token_service,
            tenant_base_domain=tenant_base_domain,
            clock=clock,
        )
        self._unsubscribe_use_case = DemoUnsubscribeUseCase(
            tenant_repo=tenant_repository,
            demo_signup_repository=demo_signup_repository,
            clock=clock,
        )
        self._demo_login_tokens = demo_login_token_service
        self._cleanup_lock = threading.RLock()
        self._last_cleanup_at = 0.0
        self._cleanup_interval_sec = 300.0

    def is_slug_available(self, slug: str) -> bool:
        if not slug_is_valid(slug):
            return False
        return self._tenant_repo.get_by_slug(slug) is None

    def resolve_demo_login_redirect(self, token: str) -> str:
        return self._demo_login_tokens.resolve_demo_login_redirect(token)

    def _find_demo_tenant_by_email(self, email: str):
        slug = self._demo_signup_repo.find_latest_completed_tenant_slug_by_email(email)
        if not slug:
            return None
        return self._tenant_repo.get_by_slug(slug)

    @staticmethod
    def _ensure_demo_session_id(demo_session_id: str | None) -> str:
        normalized = (demo_session_id or "").strip()
        if not normalized:
            raise DemoSessionRequiredError()
        return normalized

    def _validate_email_domain(self, email: str) -> None:
        domain = (email or "").split("@")[-1].strip().lower()
        if not domain:
            raise DemoSignupInvalidEmailDomainError()
        if bool(getattr(settings, "demo_signup_block_disposable_emails", True)) and (
            domain in _DISPOSABLE_EMAIL_DOMAINS or domain in _external_disposable_domains()
        ):
            raise DemoSignupDisposableEmailError()
        if not bool(getattr(settings, "demo_signup_require_mx", True)):
            return
        try:
            dns.resolver.resolve(domain, "MX")
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            raise DemoSignupInvalidEmailDomainError()
        except dns.exception.DNSException:
            # DNS infrastruktúra-hiba esetén ne álljon le teljesen a signup.
            return

    def _maybe_cleanup_expired_demos(self) -> None:
        now_ts = time.monotonic()
        with self._cleanup_lock:
            if (now_ts - self._last_cleanup_at) < self._cleanup_interval_sec:
                return
            self._last_cleanup_at = now_ts
        try:
            self._demo_signup_repo.cleanup_expired_demo_tenants()
        except Exception:
            return

    def _enforce_signup_limits(self, *, email: str, demo_session_id: str, remote_ip: str | None) -> None:
        try:
            if not is_demo_signup_enabled(default_enabled=bool(getattr(settings, "demo_signups_enabled", True))):
                raise DemoSignupDisabledError()
        except RuntimeError:
            raise DemoSignupDisabledError()

        max_global = max(1, int(getattr(settings, "demo_signup_max_per_day", 30) or 30))
        max_ip = max(5, int(getattr(settings, "demo_signup_max_per_ip_per_day", 5) or 5))
        max_ip_email = max(5, int(getattr(settings, "demo_signup_max_per_ip_email_per_day", 5) or 5))
        max_session = max(5, int(getattr(settings, "demo_signup_max_per_session_per_day", 5) or 5))
        max_per_email = max(5, int(getattr(settings, "demo_signup_max_per_email", 5) or 5))

        if self._demo_signup_repo.count_completed_signups_for_email(email) >= max_per_email:
            raise DemoSignupRateLimitedError()

        try:
            if bump_daily_counter(scope="global", key="all", now=self._clock.now()) > max_global:
                raise DemoSignupCapacityReachedError()
            if bump_daily_counter(scope="session", key=demo_session_id, now=self._clock.now()) > max_session:
                raise DemoSignupRateLimitedError()

            normalized_ip = (remote_ip or "").strip().lower() or "unknown"
            if bump_daily_counter(scope="ip", key=normalized_ip, now=self._clock.now()) > max_ip:
                raise DemoSignupRateLimitedError()
            ip_email_key = f"{normalized_ip}:{email}"
            if bump_daily_counter(scope="ip_email", key=ip_email_key, now=self._clock.now()) > max_ip_email:
                raise DemoSignupRateLimitedError()
        except RuntimeError:
            raise DemoSignupDisabledError()

    def signup(
        self,
        *,
        email: str,
        kb_name: str | None,
        name: str,
        locale: str | None = None,
        resend_existing_access: bool = False,
        company_name: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        plan_code: str | None = "free",
        subscription_period: str | None = "monthly",
        demo_session_id: str | None = None,
        remote_ip: str | None = None,
    ) -> DemoSignupResult:
        del address, phone  # reserved for future use
        counters_counted = False

        normalized_email = (email or "").strip().lower()
        owner_name = (name or "").strip()
        self._maybe_cleanup_expired_demos()
        if self._demo_signup_repo.is_email_blocked(normalized_email):
            raise DemoEmailBlockedError()
        self._validate_email_domain(normalized_email)
        if not owner_name:
            raise NameRequiredError()
        demo_session_id = self._ensure_demo_session_id(demo_session_id)

        preferred_locale = normalize_demo_locale(locale)
        existing_tenant = self._find_demo_tenant_by_email(normalized_email)
        if existing_tenant is None and self._demo_signup_repo.has_active_demo_for_email(normalized_email):
            raise DemoAlreadyExistsError()

        if existing_tenant is not None:
            if not resend_existing_access:
                raise DemoAlreadyExistsError()
            return self._resend_use_case.execute(
                existing_tenant=existing_tenant,
                email=normalized_email,
                preferred_locale=preferred_locale,
                owner_name=owner_name,
                demo_session_id=demo_session_id,
            )

        self._enforce_signup_limits(
            email=normalized_email,
            demo_session_id=demo_session_id,
            remote_ip=remote_ip,
        )
        counters_counted = True
        increment_metric("demo.signup.attempt_counted_total", 1.0)

        try:
            slug = self._slug_reserver.reserve(demo_session_id, owner_name, normalized_email)
            if not slug_is_valid(slug):
                raise InvalidSlugError()

            normalized_plan = (plan_code or "free").strip().lower() or "free"
            normalized_period = (subscription_period or "monthly").strip().lower() or "monthly"
            tenant_name = (company_name or owner_name or kb_name or slug).strip() or slug

            result = self._new_signup_use_case.execute(
                slug=slug,
                email=normalized_email,
                owner_name=owner_name,
                tenant_name=tenant_name,
                preferred_locale=preferred_locale,
                plan_code=normalized_plan,
                subscription_period=normalized_period,
                demo_session_id=demo_session_id,
            )
            increment_metric("demo.signup.success_total", 1.0)
            return result
        except Exception as exc:
            if counters_counted:
                increment_metric(
                    "demo.signup.failed_after_counted_total",
                    1.0,
                    tags={"error_type": exc.__class__.__name__},
                )
            raise

    def request_demo_unsubscribe(
        self,
        *,
        tenant_slug: str,
        email: str,
        requested_by_user_id: int | None = None,
        current_user_email: str | None = None,
    ) -> dict[str, str | int]:
        return self._unsubscribe_use_case.execute(
            tenant_slug=tenant_slug,
            email=email,
            requested_by_user_id=requested_by_user_id,
            current_user_email=current_user_email,
        )


__all__ = ["DemoSignupResult", "TenantSignupOrchestrator"]
