# backend/apps/settings/bootstrap/tenant_hooks.py
# Feladat: A settings modul tenant hook export adaptere. A core settings tenant hook regisztrációját teszi elérhetővé az app modul boundaryn.
# Sárközi Mihály - 2026.05.24

from core.modules.settings.tenant_hooks import register_settings_tenant_hooks

__all__ = ["register_settings_tenant_hooks"]
