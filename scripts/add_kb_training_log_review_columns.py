#!/usr/bin/env python3
"""
Add raw_content and review_decision columns to kb_training_log (PII review flow).
PostgreSQL: ADD COLUMN IF NOT EXISTS.

Usage:
  python scripts/add_kb_training_log_review_columns.py
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
                ADD COLUMN IF NOT EXISTS raw_content TEXT NULL
            '''))
            conn.execute(text(f'''
                ALTER TABLE "{safe}".kb_training_log
                ADD COLUMN IF NOT EXISTS review_decision VARCHAR(64) NULL
            '''))
            conn.commit()
        print(f"  {safe}.kb_training_log: raw_content, review_decision")
    print("Done.")


if __name__ == "__main__":
    main()
