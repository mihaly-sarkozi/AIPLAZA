# Ez a fájl a(z) core/extensions/tenant/service csomag exportjait fogja össze.
# Canonical implementáció: ``core.extensions.tenant.schema``, ``.signup``, ``.provisioning``, stb.
# Ez a modul backward-compat lazy exportokat tart fenn.

_EXPORT_MAP = {
    # Schema management → tenant.schema
    "TenantSchemaHook": ("core.extensions.tenant.schema.hooks", "TenantSchemaHook"),
    "PublicSchemaMigration": ("core.extensions.tenant.schema.migrations", "PublicSchemaMigration"),
    "SqlAlchemyTenantSchemaManager": ("core.extensions.tenant.schema.manager", "SqlAlchemyTenantSchemaManager"),
    "create_tenant_schema": ("core.extensions.tenant.schema.service", "create_tenant_schema"),
    "drop_tenant_schema": ("core.extensions.tenant.schema.service", "drop_tenant_schema"),
    "install_schema_tables": ("core.extensions.tenant.schema.ddl", "install_schema_tables"),
    "list_missing_tenant_schema_tables": ("core.extensions.tenant.schema.service", "list_missing_tenant_schema_tables"),
    "list_tenant_schema_hooks": ("core.extensions.tenant.schema.hooks", "list_tenant_schema_hooks"),
    "list_tenant_schema_table_names": ("core.extensions.tenant.schema.hooks", "list_tenant_schema_table_names"),
    "list_tenant_slugs": ("core.extensions.tenant.schema.service", "list_tenant_slugs"),
    "register_manifest_tenant_schema_hooks": ("core.extensions.tenant.schema.hooks", "register_manifest_tenant_schema_hooks"),
    "register_tenant_schema_hooks": ("core.extensions.tenant.schema.hooks", "register_tenant_schema_hooks"),
    "reset_tenant_schema_hooks": ("core.extensions.tenant.schema.hooks", "reset_tenant_schema_hooks"),
    "run_schema_statements": ("core.extensions.tenant.schema.ddl", "run_schema_statements"),
    "sync_existing_tenant_schemas": ("core.extensions.tenant.schema.service", "sync_existing_tenant_schemas"),
    "upgrade_public_schema": ("core.extensions.tenant.schema.public", "upgrade_public_schema"),
    "upgrade_tenant_schema": ("core.extensions.tenant.schema.service", "upgrade_tenant_schema"),
    # Signup / provisioning / slug / tokens
    "DemoLoginTokenService": ("core.extensions.tenant.tokens.demo_jwt", "DemoLoginTokenService"),
    "DemoNewSignupUseCase": ("core.extensions.tenant.signup.new_demo_signup", "DemoNewSignupUseCase"),
    "DemoSignupResendUseCase": ("core.extensions.tenant.signup.resend_demo", "DemoSignupResendUseCase"),
    "DemoSignupResult": ("core.extensions.tenant.signup.orchestrator_result", "DemoSignupResult"),
    "DemoSlugReserver": ("core.extensions.tenant.slug.reservation", "DemoSlugReserver"),
    "DemoUnsubscribeUseCase": ("core.extensions.tenant.signup.unsubscribe", "DemoUnsubscribeUseCase"),
    "ProvisioningCompensationPlan": ("core.extensions.tenant.provisioning.models", "ProvisioningCompensationPlan"),
    "TenantProvisioningRequest": ("core.extensions.tenant.provisioning.models", "TenantProvisioningRequest"),
    "TenantProvisioningService": ("core.extensions.tenant.provisioning.provisioner", "TenantProvisioningService"),
    "TenantProvisioningValidation": ("core.extensions.tenant.provisioning.models", "TenantProvisioningValidation"),
    "TenantProvisioningValidator": ("core.extensions.tenant.provisioning.validator", "TenantProvisioningValidator"),
    "TenantSignupOrchestrator": ("core.extensions.tenant.signup.orchestrator", "TenantSignupOrchestrator"),
    "TenantSignupService": ("core.extensions.tenant.signup.service", "TenantSignupService"),
    # Domain
    "TenantDomainVerificationService": ("core.extensions.tenant.service.tenant_domain_verification_service", "TenantDomainVerificationService"),
}

_ALIASES = {
    "tenant_schema_service": "core.extensions.tenant.schema.service",
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
