# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError

from core.di import get_tenant_repository
from core.extensions.tenant.dependencies import get_tenant_signup_service
from core.kernel.config.config_loader import settings
from core.kernel.security.rate_limit import limiter
from core.extensions.tenant.repositories import TenantRepository
from shared.utils.slug import slug_is_valid
from core.extensions.tenant.router.requests import TenantSignupRequest
from core.extensions.tenant.service import TenantSignupService
from core.extensions.tenant.signup.errors import (
    DemoAlreadyExistsError,
    DemoEmailBlockedError,
    DemoSessionRequiredError,
    InvalidSlugError,
    NameRequiredError,
)
from lang.messages import lang_from_request

router = APIRouter()
_log = logging.getLogger(__name__)
_PRIVACY_POLICY_DIR = Path(__file__).resolve().parents[4] / "storage" / "legal"
_PRIVACY_POLICY_FILES = {
    "hu": ("adatkezelesi-tajekoztato.pdf", _PRIVACY_POLICY_DIR / "adatkezelesi-tajekoztato.hu.pdf"),
    "en": ("privacy-policy.pdf", _PRIVACY_POLICY_DIR / "privacy-policy.en.pdf"),
    "es": ("politica-de-privacidad.pdf", _PRIVACY_POLICY_DIR / "politica-de-privacidad.es.pdf"),
}


# Ez a függvény ellenőrzi a(z) slug logikáját.
@router.get("/installer/check-slug")
@limiter.limit("30/minute")
def check_slug(
    request: Request,
    slug: str = "",
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
):
    slug = (slug or "").strip().lower()
    if not slug:
        return {"available": False, "slug": ""}
    if not slug_is_valid(slug):
        return {"available": False, "slug": slug}
    try:
        available = tenant_repo.get_by_slug(slug) is None
    except SQLAlchemyError as exc:
        _log.exception("installer check-slug DB error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Az ellenőrzés ideiglenesen nem elérhető. Próbáld később.",
        )
    return {
        "available": available,
        "slug": slug,
        "tenant_base_domain": settings.tenant_base_domain,
    }


# Ez a függvény a(z) tenant_signup logikáját valósítja meg.
@router.post("/installer/tenant-signup")
@limiter.limit("5/minute")
def tenant_signup(
    request: Request,
    body: TenantSignupRequest,
    service: TenantSignupService = Depends(get_tenant_signup_service),
):
    email = (body.email or "").strip()
    name = (body.name or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Érvényes email szükséges.")
    if not name:
        raise HTTPException(status_code=400, detail="A név kötelező.")
    _DEMO_EXISTS_DETAIL = {
        "reason": "demo_exists",
        "message": (
            "Ezzel az email címmel már hoztál létre demo oldalt. "
            "Az elérést elküldtük emailben, de ha szeretnél másik elérést, elküldjük újra."
        ),
    }
    try:
        result = service.signup(
            email=email,
            kb_name=(body.kb_name or "").strip() or None,
            name=name,
            locale=(body.locale or "").strip().lower() or None,
            resend_existing_access=body.resend_existing_access,
            company_name=(body.company_name or "").strip() or None,
            address=(body.address or "").strip() or None,
            phone=(body.phone or "").strip() or None,
            plan_code=(body.plan_code or "free").strip().lower() or "free",
            subscription_period=(body.billing_period or "monthly").strip().lower() or "monthly",
            demo_session_id=(body.demo_session_id or "").strip() or None,
        )
    except DemoSessionRequiredError:
        raise HTTPException(status_code=400, detail="Hiányzik a demo session azonosító.")
    except InvalidSlugError:
        raise HTTPException(status_code=400, detail="Nem sikerült érvényes tenant nevet generálni.")
    except NameRequiredError:
        raise HTTPException(status_code=400, detail="A név kötelező.")
    except DemoAlreadyExistsError:
        raise HTTPException(status_code=409, detail=_DEMO_EXISTS_DETAIL)
    except DemoEmailBlockedError:
        raise HTTPException(
            status_code=403,
            detail=(
                "Figyelem! Ezzel az email címmel nem hozható létre új demo regisztráció. "
                "A korábbi leiratkozás miatt a demo hozzáférés tiltva van."
            ),
        )

    return {
        "slug": result.slug,
        "message": (
            "A demo környezet elkészült. Emailben küldtünk egy jelszóbeállító linket."
            if result.created_new
            else "A jelszóbeállító linket újra elküldtük emailben."
        ),
        "host_hint": result.host_hint,
        "demo_login_token": result.demo_login_token,
        "created_new": result.created_new,
        "resent_existing": result.resent_existing,
    }


@router.get("/installer/demo-login/resolve")
@limiter.limit("20/minute")
def resolve_demo_login(
    request: Request,
    token: str = "",
    service: TenantSignupService = Depends(get_tenant_signup_service),
):
    if not token:
        raise HTTPException(status_code=400, detail={"reason": "missing", "message": "Hiányzik a demo token."})
    try:
        redirect_to = service.resolve_demo_login_redirect(token)
    except ValueError as exc:
        if str(exc) == "demo_token_expired":
            raise HTTPException(status_code=410, detail={"reason": "expired", "message": "A demo link lejárt."})
        raise HTTPException(status_code=400, detail={"reason": "invalid", "message": "A demo link érvénytelen."})
    return {"redirect_to": redirect_to}


@router.get("/installer/privacy-policy.pdf")
def installer_privacy_policy(request: Request, lang: str | None = None):
    lang = (lang or "").strip().lower()[:2] or lang_from_request(request)
    if lang not in _PRIVACY_POLICY_FILES:
        lang = "hu"
    filename, path = _PRIVACY_POLICY_FILES[lang]
    if not path.exists():
        raise HTTPException(status_code=404, detail="A PDF nem található.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
    )
