from __future__ import annotations

from apps.contracts import module_hook_name


def register_template_tenant_hooks() -> None:
    """Reference hook registration point for tenant-scoped app setup."""
    return None


TEMPLATE_TENANT_HOOK = module_hook_name("template", "tenant")

__all__ = ["TEMPLATE_TENANT_HOOK", "register_template_tenant_hooks"]
