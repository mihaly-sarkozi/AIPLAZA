#!/usr/bin/env python3
"""
Lejárt PII rekordok purge tenant sémákból.

Használat:
  python scripts/purge_expired_pii.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from sqlalchemy import create_engine, text


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def _safe_slug(slug: str) -> str:
    return "".join(c for c in slug if c.isalnum() or c in "_-")


def main() -> None:
    _load_env_file(_project_root / ".env")
    db_url = (os.environ.get("DATABASE_URL") or os.environ.get("database_url") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL hiányzik.")
    engine = create_engine(db_url, future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
        slugs = [r[0] for r in rows if r and r[0]]
    if not slugs:
        print("Nincs tenant séma (public.tenants üres).")
        return

    total = 0
    for slug in slugs:
        safe = _safe_slug(slug)
        if safe != slug:
            print(f"Kihagyva (érvénytelen slug): {slug}")
            continue
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                DELETE FROM "{safe}".kb_personal_data
                WHERE expires_at IS NOT NULL AND expires_at <= NOW()
            """))
            conn.commit()
            deleted = int(result.rowcount or 0)
            total += deleted
            print(f"  {safe}: törölt lejárt PII sorok: {deleted}")
    print(f"Kész. Összes törölt sor: {total}")


if __name__ == "__main__":
    main()

