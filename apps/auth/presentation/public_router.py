# apps/auth/presentation/public_router.py
# Nyilvános végpontok: landing/demo regisztráció (slug ellenőrzés, demo-signup). Auth nem kell.
# 2026.02 - Sárközi Mihály

import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from apps.core.middleware.rate_limit_middleware import limiter

_log = logging.getLogger(__name__)

from config.settings import settings
from apps.core.container.app_container import container
from apps.auth.application.services.demo_signup_service import (
    DemoSignupService,
    slug_is_valid,
)

router = APIRouter()


class DemoSignupBody(BaseModel):
    email: str
    kb_name: str
    name: str
    company_name: str | None = None
    address: str | None = None
    phone: str | None = None


def _tenant_set_password_base_url(request: Request, slug: str) -> str:
    """Set-password link alap URL a tenant subdomainjára (emailben küldött link)."""
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = f"{slug}.{settings.tenant_base_domain}"
    port = getattr(settings, "frontend_set_password_port", None)
    base = f"{scheme}://{host}"
    if port is not None:
        base = f"{base}:{port}"
    return base


@router.get("/public/check-slug")
@limiter.limit("30/minute")
def check_slug(request: Request, slug: str = ""):
    """
    Tudástár slug foglaltság ellenőrzés. Nyilvános.
    Válasz: { "available": true|false, "slug": "..." }. Ha invalid a slug, available: false.
    """
    slug = (slug or "").strip().lower()
    if not slug:
        return {"available": False, "slug": ""}
    if not slug_is_valid(slug):
        return {"available": False, "slug": slug}
    try:
        available = container.tenant_repo.get_by_slug(slug) is None
    except Exception as e:
        _log.exception("check-slug DB error: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Az ellenőrzés ideiglenesen nem elérhető. Próbáld később.",
        )
    return {
        "available": available,
        "slug": slug,
        "tenant_base_domain": settings.tenant_base_domain,
    }


@router.post("/public/demo-signup")
@limiter.limit("5/minute")
def demo_signup(request: Request, body: DemoSignupBody):
    """
    Demo regisztráció: tenant + séma + első user (meghívás). Emailben set-password link a tenant hostra.
    """
    email = (body.email or "").strip()
    kb_name = (body.kb_name or "").strip()
    name = (body.name or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Érvényes email szükséges.")
    if not kb_name:
        raise HTTPException(status_code=400, detail="A tudástár neve kötelező.")

    def base_url_builder(slug: str) -> str:
        return _tenant_set_password_base_url(request, slug)

    service = DemoSignupService(
        container.tenant_repo,
        container.user_service,
        base_url_builder,
    )
    try:
        slug = service.signup(
            email=email,
            kb_name=kb_name,
            name=name,
            company_name=(body.company_name or "").strip() or None,
            address=(body.address or "").strip() or None,
            phone=(body.phone or "").strip() or None,
        )
    except ValueError as e:
        if str(e) == "slug_taken":
            raise HTTPException(status_code=409, detail="A név foglalt, válassz egy másikat.")
        if str(e) == "invalid_slug":
            raise HTTPException(status_code=400, detail="Érvénytelen tudástár név.")
        if "already exists" in str(e).lower() or "email" in str(e).lower():
            raise HTTPException(status_code=409, detail="Ez az email már használatban van.")
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "slug": slug,
        "message": "Megkezdjük a telepítést (2–3 perc). Emailt kapsz egy megerősítő linkkel; a linken beállíthatod a jelszavad.",
        "host_hint": f"{slug}.{settings.tenant_base_domain}",
    }
