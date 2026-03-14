#!/usr/bin/env python3
"""
Alter kb_training_log.review_decision from VARCHAR(64) to TEXT.
A soronkénti PII döntések JSON formátumban tárolódnak, ami meghaladja a 64 karaktert.

Usage:
  python scripts/alter_review_decision_to_text.py
"""
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
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
        slugs = [r[0] for r in rows if r[0]]
    if not slugs:
        print("No tenant schemas found.")
        return
    for slug in slugs:
        safe = "".join(c for c in slug if c.isalnum() or c in "_-")
        if safe != slug:
            continue
        with engine.connect() as conn:
            conn.execute(text(f'''
                ALTER TABLE "{safe}".kb_training_log
                ALTER COLUMN review_decision TYPE TEXT USING review_decision::TEXT
            '''))
            conn.commit()
        print(f"  {safe}.kb_training_log.review_decision → TEXT")
    print("Done.")


if __name__ == "__main__":
    main()
