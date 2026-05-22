# backend/core/modules/tenant/service/__init__.py
# Feladat: Kompatibilitási lazy exportfelület a régi core.modules.tenant.service importútvonalhoz. Canonical implementációk már a schema, signup, provisioning, tokens és slug csomagok alatt élnek, ez a fájl régi importokat tart életben. Backward-compat service façade.
# Sárközi Mihály - 2026.05.21

_EXPORT_MAP = {
    # Schema management → tenant.schema
    "TenantSchemaHook": ("core.modules.tenant.schema.hooks", "TenantSchemaHook"),
    "PublicSchemaMigration": ("core.modules.tenant.schema.migrations", "PublicSchemaMigration"),
    "SqlAlchemyTenantSchemaManager": ("core.modules.tenant.schema.manager", "SqlAlchemyTenantSchemaManager"),
    "create_tenant_schema": ("core.modules.tenant.schema.service", "create_tenant_schema"),
    "drop_tenant_schema": ("core.modules.tenant.schema.service", "drop_tenant_schema"),
    "install_schema_tables": ("core.modules.tenant.schema.ddl", "install_schema_tables"),
    "list_missing_tenant_schema_tables": ("core.modules.tenant.schema.service", "list_missing_tenant_schema_tables"),
    "list_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "list_tenant_schema_hooks"),
    "list_tenant_schema_table_names": ("core.modules.tenant.schema.hooks", "list_tenant_schema_table_names"),
    "list_tenant_slugs": ("core.modules.tenant.schema.service", "list_tenant_slugs"),
    "register_manifest_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "register_manifest_tenant_schema_hooks"),
    "register_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "register_tenant_schema_hooks"),
    "reset_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "reset_tenant_schema_hooks"),
    "run_schema_statements": ("core.modules.tenant.schema.ddl", "run_schema_statements"),
    "sync_existing_tenant_schemas": ("core.modules.tenant.schema.service", "sync_existing_tenant_schemas"),
    "upgrade_public_schema": ("core.modules.tenant.schema.public", "upgrade_public_schema"),
    "upgrade_tenant_schema": ("core.modules.tenant.schema.service", "upgrade_tenant_schema"),
    # Signup / provisioning / slug / tokens
    "DemoLoginTokenService": ("core.modules.tenant.tokens.demo_jwt", "DemoLoginTokenService"),
    "DemoNewSignupUseCase": ("core.modules.tenant.signup.new_demo_signup", "DemoNewSignupUseCase"),
    "DemoSignupResendUseCase": ("core.modules.tenant.signup.resend_demo", "DemoSignupResendUseCase"),
    "DemoSignupResult": ("core.modules.tenant.signup.orchestrator_result", "DemoSignupResult"),
    "DemoSlugReserver": ("core.modules.tenant.slug.reservation", "DemoSlugReserver"),
    "DemoUnsubscribeUseCase": ("core.modules.tenant.signup.unsubscribe", "DemoUnsubscribeUseCase"),
    "ProvisioningCompensationPlan": ("core.modules.tenant.provisioning.models", "ProvisioningCompensationPlan"),
    "TenantProvisioningRequest": ("core.modules.tenant.provisioning.models", "TenantProvisioningRequest"),
    "TenantProvisioningService": ("core.modules.tenant.provisioning.provisioner", "TenantProvisioningService"),
    "TenantProvisioningValidation": ("core.modules.tenant.provisioning.models", "TenantProvisioningValidation"),
    "TenantProvisioningValidator": ("core.modules.tenant.provisioning.validator", "TenantProvisioningValidator"),
    "TenantSignupOrchestrator": ("core.modules.tenant.signup.orchestrator", "TenantSignupOrchestrator"),
    "TenantSignupService": ("core.modules.tenant.signup.service", "TenantSignupService"),
    # Domain
    "TenantDomainVerificationService": ("core.modules.tenant.service.tenant_domain_verification_service", "TenantDomainVerificationService"),
}

_ALIASES = {
    "tenant_schema_service": "core.modules.tenant.schema.service",
}


def __getattr__(name: str):
    if name in _EXPORT_MAP:
        module_name, attr_name = _EXPORT_MAP[name]
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)
    if name in _ALIASES:
        import importlib

        return importlib.import_module(_ALIASES[name])
    raise AttributeError(name)


__all__ = list(_EXPORT_MAP.keys()) + list(_ALIASES.keys())
