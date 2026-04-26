# Tenant regisztráció request model
# 2026.04.03 - Sárközi Mihály
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
