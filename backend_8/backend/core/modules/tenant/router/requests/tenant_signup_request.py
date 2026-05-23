# backend/core/modules/tenant/router/requests/tenant_signup_request.py
# Feladat: A tenant signup HTTP request DTO-ja. Demo tenant létrehozáshoz szükséges slug, user, locale, captcha és consent adatokat validálható Pydantic modellben hordozza. Tenant web request contract.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel


class TenantSignupRequest(BaseModel):
    email: str
    kb_name: str | None = None
    name: str
    locale: str | None = None
    resend_existing_access: bool = False
    company_name: str | None = None
    address: str | None = None
    phone: str | None = None
    plan_code: str | None = "free"
    billing_period: str | None = "monthly"
    demo_session_id: str | None = None
    captcha_token: str | None = None
