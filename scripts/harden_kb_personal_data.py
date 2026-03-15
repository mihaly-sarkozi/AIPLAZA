#!/usr/bin/env python3
"""
P1 adatvédelmi keményítés kb_personal_data táblára:
- created_at / expires_at oszlopok hozzáadása
- expires_at index
- meglévő plaintext extracted_value mezők titkosítása (enc:: prefix)

Használat:
  python scripts/harden_kb_personal_data.py
"""
from __future__ import annotations

import sys
import os
import base64
import hashlib
from datetime import datetime, timedelta, UTC
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from sqlalchemy import create_engine, text
from cryptography.fernet import Fernet


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


def _fernet_from_env() -> Fernet:
    pii_key = (os.environ.get("PII_ENCRYPTION_KEY") or "").strip()
    if pii_key:
        return Fernet(pii_key.encode("utf-8"))
    jwt_secret = (os.environ.get("JWT_SECRET") or "").encode("utf-8")
    digest = hashlib.sha256(jwt_secret).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _safe_slug(slug: str) -> str:
    return "".join(c for c in slug if c.isalnum() or c in "_-")


def main() -> None:
    _load_env_file(_project_root / ".env")
    db_url = (os.environ.get("DATABASE_URL") or os.environ.get("database_url") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL hiányzik.")
    retention_days = int((os.environ.get("PII_RETENTION_DAYS") or "90").strip() or "90")
    fernet = _fernet_from_env()

    engine = create_engine(db_url, future=True)
    default_exp = (datetime.now(UTC) + timedelta(days=retention_days)).replace(tzinfo=None)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
        slugs = [r[0] for r in rows if r and r[0]]

    if not slugs:
        print("Nincs tenant séma (public.tenants üres).")
        return

    for slug in slugs:
        safe = _safe_slug(slug)
        if safe != slug:
            print(f"Kihagyva (érvénytelen slug): {slug}")
            continue
        with engine.connect() as conn:
            conn.execute(text(f"""
                ALTER TABLE "{safe}".kb_personal_data
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NULL
            """))
            conn.execute(text(f"""
                ALTER TABLE "{safe}".kb_personal_data
                ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP NULL
            """))
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_kb_personal_data_expires_at
                ON "{safe}".kb_personal_data (expires_at)
            """))
            conn.execute(text(f"""
                UPDATE "{safe}".kb_personal_data
                SET created_at = NOW()
                WHERE created_at IS NULL
            """))
            if retention_days > 0:
                conn.execute(text(f"""
                    UPDATE "{safe}".kb_personal_data
                    SET expires_at = :exp
                    WHERE expires_at IS NULL
                """), {"exp": default_exp})

            legacy_rows = conn.execute(text(f"""
                SELECT id, extracted_value
                FROM "{safe}".kb_personal_data
                WHERE extracted_value IS NOT NULL
            """)).fetchall()
            updated = 0
            for row_id, value in legacy_rows:
                if (value or "").startswith("enc::"):
                    continue
                token = fernet.encrypt((value or "").encode("utf-8")).decode("utf-8")
                enc = f"enc::{token}"
                conn.execute(
                    text(f'UPDATE "{safe}".kb_personal_data SET extracted_value = :enc WHERE id = :id'),
                    {"enc": enc, "id": row_id},
                )
                updated += 1
            conn.commit()
            print(f"  {safe}.kb_personal_data: schema ok, titkosított sorok: {updated}")

    print("Kész.")


if __name__ == "__main__":
    main()

