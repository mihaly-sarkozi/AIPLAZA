# Ez a fájl a tenant-kezeléshez kapcsolódó egyik backend építőelemet tartalmazza.
from core.modules.settings.tenant_hooks import register_settings_tenant_hooks

__all__ = ["register_settings_tenant_hooks"]
