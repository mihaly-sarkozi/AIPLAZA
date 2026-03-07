#!/usr/bin/env python3
"""
Hiányzó teljesítmény indexek hozzáadása a tenant sémákhoz (meglévő DB).
Az ORM már tartalmazza az indexeket; ez a script a korábban létrehozott táblákhoz adja hozzá.
Futtatás: .venv/bin/python scripts/add_performance_indexes.py
Opcionális: TENANT_SLUG=demo – csak az adott tenant, különben minden.
"""
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from sqlalchemy import create_engine, text
from config.settings import settings


def main():
    engine = create_engine(settings.database_url, future=True)
    slug = os.getenv("TENANT_SLUG")
    if slug:
        slugs = [slug]
    else:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
            slugs = [r[0] for r in rows]

    for s in slugs:
        safe = "".join(c for c in s if c.isalnum() or c == "_")
        if safe != s:
            continue
        schema = safe
        with engine.connect() as conn:
            # users: created_at (list_all order_by)
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS ix_users_created_at ON "{schema}".users (created_at)'
            ))
            # refresh_tokens: token_hash (logout invalidate_by_hash)
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS ix_refresh_token_hash ON "{schema}".refresh_tokens (token_hash)'
            ))
            # two_factor_codes: (user_id, code) get_valid_code
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS ix_2fa_user_code ON "{schema}".two_factor_codes (user_id, code)'
            ))
            # pending_2fa_logins: user_id (ORM default name)
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS ix_pending_2fa_logins_user_id ON "{schema}".pending_2fa_logins (user_id)'
            ))
            conn.commit()
        print(f"OK: {schema} indexek létrehozva/ellenőrizve.")

    print("Kész.")


if __name__ == "__main__":
    main()
