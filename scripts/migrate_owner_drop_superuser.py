#!/usr/bin/env python3
"""
Migráció: is_superuser oszlop eltávolítása, role = user | admin | owner.
Tenantenként: az első user (created_at min) lesz owner; a többi is_superuser=True marad admin.
Futtatás: python scripts/migrate_owner_drop_superuser.py
"""
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from sqlalchemy import create_engine, text
from config.settings import settings

def main():
    engine = create_engine(settings.database_url, future=True)
    with engine.connect() as conn:
        slugs = [row[0] for row in conn.execute(text("SELECT slug FROM public.tenants")).fetchall()]
        for slug in slugs:
            safe = "".join(c for c in slug if c.isalnum() or c == "_")
            if safe != slug:
                continue
            try:
                # Van-e users tábla ebben a sémában?
                r = conn.execute(text(f"""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = :s AND table_name = 'users'
                """), {"s": safe})
                if r.scalar() is None:
                    continue
                # Van-e is_superuser oszlop?
                col = conn.execute(text("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = :s AND table_name = 'users' AND column_name = 'is_superuser'
                """), {"s": safe})
                if col.scalar() is None:
                    print(f"  [{safe}] users.is_superuser már nincs, kihagyjuk.")
                    continue
                # Első user (created_at min) → owner
                first_id = conn.execute(text(f"""
                    SELECT id FROM "{safe}".users ORDER BY created_at ASC NULLS LAST, id ASC LIMIT 1
                """)).scalar()
                if first_id is not None:
                    conn.execute(text(f'UPDATE "{safe}".users SET role = :role WHERE id = :id'), {"role": "owner", "id": first_id})
                    print(f"  [{safe}] user id={first_id} → role=owner")
                # is_superuser oszlop törlése
                conn.execute(text(f'ALTER TABLE "{safe}".users DROP COLUMN IF EXISTS is_superuser'))
                print(f"  [{safe}] is_superuser oszlop törölve.")
            except Exception as e:
                print(f"  [{safe}] Hiba: {e}")
                raise
        conn.commit()
    print("Kész.")

if __name__ == "__main__":
    main()
