# backend/apps/settings/api/router.py
# Feladat: A settings modul FastAPI routere. Beállítások olvasását, módosítását és settings szekciók listázását delegálja a SettingsFacade felé.
# Sárközi Mihály - 2026.05.24

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from apps.settings.api.schemas import (
    BillingSettingsUpdateRequest,
    LocaleSettingsUpdateRequest,
    SettingsSectionResponse,
    SettingsUpdateRequest,
    TenantResetRequest,
    TenantResetResponse,
    TwoFactorSettingsUpdateRequest,
)
from apps.settings.bootstrap.dependencies import (
    SettingsFacadeDep,
    SettingsReadUserDep,
    SettingsWriteUserDep,
    TenantResetServiceDep,
)
from core.kernel.http.tenant_dependencies import RequestTenantContext, require_tenant_context
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import require_role
from core.modules.users.domain.dto import User
from apps.settings.domain.settings_state import (
    BillingSettingsState,
    LocaleSettingsState,
    SettingsState,
    TwoFactorSettingsState,
)

router = APIRouter()


@router.get("/settings", response_model=SettingsState)
def get_settings(
    facade: SettingsFacadeDep,
    _current_user: SettingsReadUserDep,
):
    return facade.get_settings()


@router.get("/settings/billing", response_model=BillingSettingsState)
def get_billing_settings(
    facade: SettingsFacadeDep,
    _current_user: SettingsReadUserDep,
):
    return facade.get_billing_settings()


@router.patch("/settings/billing", response_model=BillingSettingsState)
def update_billing_settings(
    facade: SettingsFacadeDep,
    current_user: SettingsWriteUserDep,
    body: BillingSettingsUpdateRequest = Body(default=BillingSettingsUpdateRequest()),
):
    if getattr(current_user, "role", None) not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner or admin can update billing settings.")
    return facade.update_billing_settings(
        billing_customer_type=body.billing_customer_type,
        billing_full_name=body.billing_full_name,
        billing_company_name=body.billing_company_name,
        billing_tax_id=body.billing_tax_id,
        billing_address_line=body.billing_address_line,
        billing_postal_code=body.billing_postal_code,
        billing_city=body.billing_city,
        billing_region=body.billing_region,
        billing_country=body.billing_country,
        updated_by=current_user.id,
    )


@router.get("/settings/locale", response_model=LocaleSettingsState)
def get_locale_settings(
    facade: SettingsFacadeDep,
    _current_user: SettingsReadUserDep,
):
    return facade.get_locale_settings()


@router.patch("/settings/locale", response_model=LocaleSettingsState)
def update_locale_settings(
    facade: SettingsFacadeDep,
    current_user: SettingsWriteUserDep,
    body: LocaleSettingsUpdateRequest = Body(default=LocaleSettingsUpdateRequest()),
):
    return facade.update_locale_settings(
        timezone=body.timezone,
        date_format=body.date_format,
        time_format=body.time_format,
        updated_by=current_user.id,
    )


@router.get("/settings/security/2fa", response_model=TwoFactorSettingsState)
def get_two_factor_settings(
    facade: SettingsFacadeDep,
    _current_user: SettingsReadUserDep,
):
    # Legacy/global 2FA settings endpoint. Authenticator MFA flow remains in /auth/authenticator/*.
    return facade.get_two_factor_settings()


@router.patch("/settings/security/2fa", response_model=TwoFactorSettingsState)
def update_two_factor_settings(
    facade: SettingsFacadeDep,
    current_user: SettingsWriteUserDep,
    body: TwoFactorSettingsUpdateRequest = Body(default=TwoFactorSettingsUpdateRequest()),
):
    # Legacy/global 2FA settings endpoint. Authenticator MFA flow remains in /auth/authenticator/*.
    return facade.update_two_factor_settings(
        two_factor_enabled=body.two_factor_enabled,
        updated_by=current_user.id,
    )


@router.patch("/settings", response_model=SettingsState)
def update_settings(
    facade: SettingsFacadeDep,
    current_user: SettingsWriteUserDep,
    body: SettingsUpdateRequest = Body(default=SettingsUpdateRequest()),
):
    billing_fields = (
        body.billing_customer_type,
        body.billing_full_name,
        body.billing_company_name,
        body.billing_tax_id,
        body.billing_address_line,
        body.billing_postal_code,
        body.billing_city,
        body.billing_region,
        body.billing_country,
    )
    if any(value is not None for value in billing_fields) and getattr(current_user, "role", None) not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner or admin can update billing settings.")
    return facade.update_settings(
        two_factor_enabled=body.two_factor_enabled,
        timezone=body.timezone,
        date_format=body.date_format,
        time_format=body.time_format,
        billing_customer_type=body.billing_customer_type,
        billing_full_name=body.billing_full_name,
        billing_company_name=body.billing_company_name,
        billing_tax_id=body.billing_tax_id,
        billing_address_line=body.billing_address_line,
        billing_postal_code=body.billing_postal_code,
        billing_city=body.billing_city,
        billing_region=body.billing_region,
        billing_country=body.billing_country,
        updated_by=current_user.id,
    )


@router.get("/settings/sections", response_model=list[SettingsSectionResponse])
def get_settings_sections(
    facade: SettingsFacadeDep,
    _current_user: SettingsReadUserDep,
):
    return facade.get_sections()


@router.post("/settings/reset", response_model=TenantResetResponse)
@limiter.limit("2/minute")
def reset_tenant_data(
    body: TenantResetRequest,
    request: Request,
    reset_service: TenantResetServiceDep,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    current_user: User = Depends(require_role("owner")),
):
    del request
    if tenant.tenant_id is None or not tenant.slug:
        raise HTTPException(status_code=400, detail="Tenant required.")
    try:
        result = reset_service.reset_tenant(
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.slug,
            owner_user_id=current_user.id,
            confirm_slug=body.confirm_slug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TenantResetResponse(
        status=result.status,
        message=result.message,
        tenant_slug=result.tenant_slug,
        owner_user_id=result.owner_user_id,
        default_knowledge_base_uuid=result.default_knowledge_base_uuid,
    )


__all__ = ["router"]
