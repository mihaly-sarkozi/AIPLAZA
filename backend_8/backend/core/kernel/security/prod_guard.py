# backend/core/kernel/security/prod_guard.py
# Feladat: Veszélyes karbantartó scriptek production futtatását tiltó guard helper. APP_ENV=prod esetén hibaüzenettel kilép, így jelszó/reset jellegű műveletek véletlenül nem futhatnak éles környezetben. Core operational security helper script belépési pontokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os
import sys

from core.kernel.config.environment import is_production_env


def reject_if_production(script_name: str, reason: str = "veszélyes (jelszó/reset)") -> None:
    """Ha APP_ENV=production, kilép 1-es kóddal."""
    if is_production_env(os.environ.get("APP_ENV") or "local"):
        print(
            f"[PROD GUARD] {script_name} productionben nem futtatható ({reason}).",
            file=sys.stderr,
        )
        sys.exit(1)


__all__ = ["reject_if_production"]
