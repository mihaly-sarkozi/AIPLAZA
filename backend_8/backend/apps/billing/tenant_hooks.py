# backend/apps/billing/tenant_hooks.py
# Feladat: Tenant signup hookot regisztrál a billing app számára. Új tenant létrejöttekor a kiválasztott plan és billing period alapján beállítja a kezdő előfizetést a BillingService-en keresztül. Program-specifikus tenant lifecycle integráció.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.extensions.tenant_hooks import TenantSignupContext, register_tenant_signup_hook


class BillingTenantSignupHook:
    def __init__(self, billing_service) -> None:
        self._billing_service = billing_service

    def handle(self, context: TenantSignupContext) -> None:
        if context.tenant_id is None:
            return
        self._billing_service.set_signup_subscription(
            context.tenant_id,
            context.tenant_slug,
            plan_code=context.plan_code,
            billing_period=context.subscription_period,
        )


def register_billing_tenant_signup_hook(billing_service) -> None:
    register_tenant_signup_hook("billing", BillingTenantSignupHook(billing_service))

