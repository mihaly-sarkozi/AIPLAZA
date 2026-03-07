#!/usr/bin/env python3
# scripts/add_security_version_columns.py
# users.security_version és tenants.security_version oszlopok (token force revoke).
# Futtatás: python scripts/add_security_version_columns.py (vagy python -m scripts.add_security_version_columns)
# 2026.03 - Sárközi Mihály

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from config.settings import settings
from apps.core.db.session import make_session_factory


def main():
    sf = make_session_factory(settings.database_url, pool_pre_ping=True)
    with sf() as db:
        # tenants (public schema)
        try:
            db.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS security_version INTEGER NOT NULL DEFAULT 0"))
            db.commit()
            print("public.tenants.security_version OK")
        except Exception as e:
            db.rollback()
            print("tenants:", e)

        # users: tenantonkénti sémában van; tipikus eset: demo, acme, stb.
        # A séma listát a public.tenants-ból vesszük
        try:
            rows = db.execute(text("SELECT slug FROM public.tenants")).fetchall()
            for (slug,) in rows:
                if not slug or not str(slug).replace("_", "").isalnum():
                    continue
                try:
                    db.execute(text(f'ALTER TABLE "{slug}".users ADD COLUMN IF NOT EXISTS security_version INTEGER NOT NULL DEFAULT 0'))
                    db.commit()
                    print(f"{slug}.users.security_version OK")
                except Exception as e:
                    db.rollback()
                    print(f"{slug}.users:", e)
        except Exception as e:
            db.rollback()
            print("tenants list:", e)


if __name__ == "__main__":
    main()
