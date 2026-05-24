# backend/apps/billing/bootstrap/tenant_hooks.py
# Feladat: Billing tenant signup hookok bootstrap exportja. Új tenant létrejöttekor előfizetés inicializálását regisztrálja.
# Sárközi Mihály - 2026.05.24

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

__all__ = ["BillingTenantSignupHook", "register_billing_tenant_signup_hook"]
