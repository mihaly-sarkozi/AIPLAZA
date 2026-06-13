from __future__ import annotations

# backend/apps/settings/bootstrap/service_keys.py
# Feladat: A settings modul stabil service kulcsát definiálja, hogy dependency-k és module wiring azonos néven érjék el a szolgáltatást.
# Sárközi Mihály - 2026.05.24

from core.kernel.interface.app_keys import module_service_key

SETTINGS_SERVICE = module_service_key("settings")
TENANT_RESET_SERVICE = module_service_key("settings", "tenant_reset")

__all__ = ["SETTINGS_SERVICE", "TENANT_RESET_SERVICE"]
