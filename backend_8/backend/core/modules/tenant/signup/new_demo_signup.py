# backend/core/modules/tenant/signup/new_demo_signup.py
# Feladat: Új demo tenant signup use case. Validálja és létrehozza a demo tenantot, usert és kapcsolódó onboarding adatokat, majd email/token folyamatokat indít. Tenant onboarding application service.
# Sárközi Mihály - 2026.05.21

"""New-demo-tenant creation use case.

Responsibility: provision a brand-new demo tenant, apply optional tenant
signup hooks, send the login email and mark the session completed.
Pure orchestration – no HTTP, no framework.

Can be unit-tested with mock collaborators.
"""
from __future__ import annotations

from typing import Callable

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.users.service._user_service_helpers import build_set_password_link, new_invite_token_payload
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.slug.policy import demo_host_hint, demo_trial_expires_at
from core.modules.tenant.provisioning.models import TenantProvisioningRequest
from core.modules.tenant.signup.orchestrator_result import DemoSignupResult
from core.kernel.config.config_loader import settings
from core.modules.tenant.extensions.tenant_hooks import TenantSignupContext, TenantSignupHook, get_tenant_signup_hooks

class DemoNewSignupUseCase:
    """Create a brand-new demo tenant end-to-end."""

    def __init__(
        self,
        *,
        tenant_repo,
        user_service,
        provisioning_service,
        demo_signup_repository,
        demo_login_token_service,
        tenant_base_domain: str,
        clock,
        tenant_signup_hooks_provider: Callable[[], tuple[TenantSignupHook, ...]] = get_tenant_signup_hooks,
        audit_service=None,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_service = user_service
        self._provisioning_service = provisioning_service
        self._demo_signup_repo = demo_signup_repository
        self._demo_login_tokens = demo_login_token_service
        self._tenant_base_domain = tenant_base_domain
        self._clock = clock
        self._tenant_signup_hooks_provider = tenant_signup_hooks_provider
        self._audit = audit_service

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

    def _load_tenant_owner(self, *, tenant_slug: str, email: str, preferred_locale: str):
        tenant_ctx = current_tenant_schema.set(tenant_slug)
        try:
            tenant_owner = self._user_service.user_repository.get_by_email(email)
            if tenant_owner is not None and tenant_owner.id is not None:
                if getattr(tenant_owner, "preferred_locale", None) != preferred_locale:
                    self._user_service.user_repository.update(
                        tenant_owner.with_updates(preferred_locale=preferred_locale),
                        updated_by=tenant_owner.id,
                    )
                tenant_owner = self._user_service.user_repository.get_by_id(tenant_owner.id)
            return tenant_owner
        finally:
            current_tenant_schema.reset(tenant_ctx)

    def execute(
        self,
        *,
        slug: str,
        email: str,
        owner_name: str,
        tenant_name: str,
        preferred_locale: str,
        plan_code: str,
        subscription_period: str,
        demo_session_id: str,
    ) -> DemoSignupResult:
        trial_days = max(1, int(getattr(settings, "demo_trial_days", 7) or 7))
        demo_expires_at = demo_trial_expires_at(self._clock.now(), days=trial_days)
        primary_domain = demo_host_hint(slug, self._tenant_base_domain)

        try:
            if self._tenant_repo.get_by_slug(slug) is None:
                self._provisioning_service.provision(
                    TenantProvisioningRequest(
                        slug=slug,
                        tenant_name=tenant_name,
                        owner_email=email,
                        owner_name=owner_name or None,
                        primary_domain=primary_domain,
                        package=plan_code,
                        feature_flags={
                            "demo_mode": True,
                            "demo_expires_at": demo_expires_at.isoformat(),
                        },
                        limits={},
                        owner_send_invite_email=False,
                        owner_activate_immediately=True,
                    )
                )

            tenant = self._tenant_repo.get_by_slug(slug)

            tenant_owner = self._load_tenant_owner(
                tenant_slug=slug,
                email=email,
                preferred_locale=preferred_locale,
            )
            if tenant_owner is None or tenant_owner.id is None:
                raise RuntimeError("demo_owner_missing_after_signup")

            signup_context = TenantSignupContext(
                tenant_slug=slug,
                tenant_name=tenant_name,
                tenant_id=getattr(tenant, "id", None),
                owner_id=tenant_owner.id,
                owner_email=email,
                locale=preferred_locale,
                plan_code=plan_code,
                subscription_period=subscription_period,
                demo_session_id=demo_session_id,
                is_new_tenant=tenant is None,
            )
            tenant_ctx = current_tenant_schema.set(slug)
            try:
                for hook in self._tenant_signup_hooks_provider():
                    hook.handle(signup_context)
            finally:
                current_tenant_schema.reset(tenant_ctx)

            self._send_demo_set_password_email(
                tenant_slug=slug,
                user_id=tenant_owner.id,
                email=email,
                demo_expires_at=demo_expires_at,
                preferred_locale=preferred_locale,
            )
            self._demo_signup_repo.mark_session_completed(demo_session_id)
            if self._audit:
                self._audit.log(
                    AuditLogAction.TENANT_PROVISIONED,
                    user_id=tenant_owner.id,
                    details={
                        "tenant_slug": slug,
                        "tenant_name": tenant_name,
                        "plan_code": plan_code,
                        "subscription_period": subscription_period,
                    },
                    target_type="tenant",
                    target_id=slug,
                )
            return DemoSignupResult(
                slug=slug,
                host_hint=primary_domain,
                demo_login_token="",
                created_new=True,
                resent_existing=False,
            )
        except Exception:
            if self._tenant_repo.get_by_slug(slug) is None:
                self._demo_signup_repo.delete_session(demo_session_id)
            raise


__all__ = ["DemoNewSignupUseCase"]
