from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from admin.repository.schema_migrations import apply_platform_security_alerts_legacy_compat


def _resolve_env_path() -> Path:
    candidates = (
        _project_root / ".env",
        _project_root.parent / ".env",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def main() -> None:
    load_dotenv(_resolve_env_path())
    from core.kernel.config.config_loader import settings

    engine = create_engine(settings.database_url, future=True)
    apply_platform_security_alerts_legacy_compat(engine)
    print("platform_security_alerts legacy kompatibilitasi migracio lefutott.")


if __name__ == "__main__":
    main()

