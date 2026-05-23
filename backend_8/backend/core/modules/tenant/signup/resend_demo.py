# backend/core/modules/tenant/signup/resend_demo.py
# Feladat: Demo signup resend use case. Meglévő demo session alapján újraküldi vagy frissíti a belépési/onboarding információkat, rate limit és token szabályokkal. Tenant onboarding resend service.
# Sárközi Mihály - 2026.05.21

"""Resend-demo-access use case.

Responsibility: when an email address already has an existing demo tenant,
re-send the demo login link to that email.  Handles expiry resolution and
owner locale update.

Can be unit-tested with mocks – no FastAPI or SQLAlchemy at call time.
"""
from __future__ import annotations

from core.modules.users.service._user_service_helpers import build_set_password_link, new_invite_token_payload
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.slug.policy import demo_host_hint, demo_trial_expires_at
from core.modules.tenant.signup.orchestrator_result import DemoSignupResult
from core.kernel.config.config_loader import settings


_DEMO_TRIAL_DAYS = 30


class DemoSignupResendUseCase:
    """Re-send demo login email for an existing tenant."""

    def __init__(
        self,
        *,
        tenant_repo,
        user_service,
        demo_signup_repository,
        demo_login_token_service,
        tenant_base_domain: str,
        clock,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_service = user_service
        self._demo_signup_repo = demo_signup_repository
        self._demo_login_tokens = demo_login_token_service
        self._tenant_base_domain = tenant_base_domain
        self._clock = clock

    def _tenant_frontend_base_url(self, tenant_slug: str) -> str:
        scheme = "https" if getattr(settings, "cookie_secure", False) else "http"
        base = f"{scheme}://{tenant_slug}.{self._tenant_base_domain}"
        port = getattr(settings, "frontend_set_password_port", None)
        if port is not None:
            base = f"{base}:{port}"
        return base

    def _send_demo_set_password_email(
        self,
        *,
        tenant_slug: str,
        user_id: int,
        email: str,
        demo_expires_at,
        preferred_locale: str,
    ) -> None:
        invite_repo = self._user_service.invite_token_repo
        if invite_repo is None:
            raise RuntimeError("InviteTokenRepository is not configured")
        invite_payload = new_invite_token_payload()
        tenant_ctx = current_tenant_schema.set(tenant_slug)
        try:
            invite_repo.invalidate_all_for_user(user_id, updated_by=user_id)
            invite_repo.create(
                user_id,
                invite_payload.token_hash,
                invite_payload.expires_at,
                created_by=user_id,
                updated_by=user_id,
            )
        finally:
            current_tenant_schema.reset(tenant_ctx)

        set_password_link = build_set_password_link(self._tenant_frontend_base_url(tenant_slug), invite_payload.raw_token)
        if self._user_service.email_service and set_password_link:
            self._user_service.email_service.send_demo_set_password_invite(
                email,
                set_password_link,
                demo_expires_at=demo_expires_at,
                lang=preferred_locale,
            )

    def _resolve_existing_demo_expiry(self, tenant_slug: str):
        from datetime import datetime

        snapshot = self._tenant_repo.get_snapshot_by_slug(tenant_slug)
        demo_expires_at_raw = getattr(getattr(snapshot, "config", None), "feature_flags", {}).get("demo_expires_at")
        try:
            if demo_expires_at_raw:
                return datetime.fromisoformat(str(demo_expires_at_raw).replace("Z", "+00:00"))
        except ValueError:
            pass
        return demo_trial_expires_at(self._clock.now(), days=_DEMO_TRIAL_DAYS)

    def _ensure_demo_owner_locale(self, user, locale: str) -> None:
        if getattr(user, "preferred_locale", None) == locale:
            return
        self._user_service.user_repository.update(
            user.with_updates(preferred_locale=locale),
            updated_by=user.id,
        )

    def _load_tenant_owner(self, *, tenant_slug: str, email: str, preferred_locale: str):
        tenant_ctx = current_tenant_schema.set(tenant_slug)
        try:
            tenant_owner = self._user_service.user_repository.get_by_email(email)
            if tenant_owner is not None and tenant_owner.id is not None:
                self._ensure_demo_owner_locale(tenant_owner, preferred_locale)
                tenant_owner = self._user_service.user_repository.get_by_id(tenant_owner.id)
            return tenant_owner
        finally:
            current_tenant_schema.reset(tenant_ctx)

    def execute(
        self,
        *,
        existing_tenant,
        email: str,
        preferred_locale: str,
        owner_name: str,
        demo_session_id: str,
    ) -> DemoSignupResult:
        reserved_slug = existing_tenant.slug
        demo_expires_at = self._resolve_existing_demo_expiry(reserved_slug)
        tenant_owner = self._load_tenant_owner(
            tenant_slug=reserved_slug,
            email=email,
            preferred_locale=preferred_locale,
        )
        if tenant_owner is None or tenant_owner.id is None:
            raise RuntimeError("demo_owner_missing_after_signup")

        self._send_demo_set_password_email(
            tenant_slug=reserved_slug,
            user_id=tenant_owner.id,
            email=email,
            demo_expires_at=demo_expires_at,
            preferred_locale=preferred_locale,
        )
        self._demo_signup_repo.delete_session(demo_session_id)
        return DemoSignupResult(
            slug=reserved_slug,
            host_hint=demo_host_hint(reserved_slug, self._tenant_base_domain),
            demo_login_token="",
            created_new=False,
            resent_existing=True,
        )


__all__ = ["DemoSignupResendUseCase"]
