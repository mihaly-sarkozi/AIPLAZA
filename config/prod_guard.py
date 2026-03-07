# config/prod_guard.py
# Production guard: veszélyes scriptek (jelszó reset, default password) ne fussanak prod környezetben.
# Használat: from config.prod_guard import reject_if_production
#           reject_if_production("reset_passwords")
# Biztonság: véletlen prod futtatás megakadályozása.

import os
import sys


def reject_if_production(script_name: str, reason: str = "veszélyes (jelszó/reset)") -> None:
    """Ha APP_ENV=prod, kilép 1-es kóddal."""
    env = (os.environ.get("APP_ENV") or "").strip().lower()
    if env == "prod":
        print(
            f"[PROD GUARD] {script_name} productionben nem futtatható ({reason}).",
            file=sys.stderr,
        )
        sys.exit(1)
