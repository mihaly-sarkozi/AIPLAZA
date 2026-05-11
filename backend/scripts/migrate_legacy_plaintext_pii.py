from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from apps.knowledge.pii.encryption import PiiEncryptor
from core.kernel.config.config_loader import settings

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ENC_PREFIX = "enc::"


def _resolve_env_path() -> Path:
    candidates = (
        _project_root / ".env",
        _project_root.parent / ".env",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _validate_identifier(value: str, *, kind: str) -> str:
    normalized = (value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"Érvénytelen {kind}: {value!r}")
    return normalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Legacy plaintext PII mezők migrálása enc:: formátumra "
            "egy adott schema.table.column célon."
        )
    )
    parser.add_argument("--schema", required=True, help="DB séma neve (pl. tenant_demo)")
    parser.add_argument("--table", required=True, help="Tábla neve")
    parser.add_argument("--column", required=True, help="Migrálandó szöveges oszlop neve")
    parser.add_argument("--id-column", default="id", help="Azonosító oszlop neve (alapértelmezett: id)")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch méret (alapértelmezett: 500)")
    parser.add_argument("--dry-run", action="store_true", help="Csak számol, nem ír adatot")
    return parser.parse_args()


def main() -> None:
    load_dotenv(_resolve_env_path())
    args = _parse_args()

    if args.batch_size <= 0:
        raise ValueError("--batch-size pozitív kell legyen")

    schema = _validate_identifier(args.schema, kind="schema")
    table = _validate_identifier(args.table, kind="table")
    column = _validate_identifier(args.column, kind="column")
    id_column = _validate_identifier(args.id_column, kind="id-column")

    encryptor = PiiEncryptor()
    target = f'"{schema}"."{table}"'
    q_id = f'"{id_column}"'
    q_col = f'"{column}"'

    scan_sql = text(
        f"""
        SELECT {q_id} AS row_id, {q_col} AS pii_value
        FROM {target}
        WHERE {q_col} IS NOT NULL
          AND {q_col} <> ''
          AND {q_col} NOT LIKE :enc_prefix
        ORDER BY {q_id}
        LIMIT :limit
        """
    )
    count_sql = text(
        f"""
        SELECT COUNT(*) AS cnt
        FROM {target}
        WHERE {q_col} IS NOT NULL
          AND {q_col} <> ''
          AND {q_col} NOT LIKE :enc_prefix
        """
    )
    update_sql = text(
        f"""
        UPDATE {target}
        SET {q_col} = :new_value
        WHERE {q_id} = :row_id
        """
    )

    engine = create_engine(settings.database_url, future=True)
    total_candidates = 0
    total_updated = 0

    with engine.begin() as conn:
        if args.dry_run:
            total_candidates = int(conn.execute(count_sql, {"enc_prefix": f"{_ENC_PREFIX}%"}).scalar() or 0)
            print(
                f"[DRY-RUN] legacy plaintext PII scan kész: "
                f"jelölt sorok={total_candidates}, frissített sorok=0 "
                f"target={schema}.{table}.{column}"
            )
            return
        while True:
            rows = conn.execute(
                scan_sql,
                {"enc_prefix": f"{_ENC_PREFIX}%", "limit": args.batch_size},
            ).mappings().all()
            if not rows:
                break
            total_candidates += len(rows)
            for row in rows:
                value = str(row["pii_value"] or "")
                if not value or value.startswith(_ENC_PREFIX):
                    continue
                encrypted = encryptor.encrypt(value)
                conn.execute(update_sql, {"new_value": encrypted, "row_id": row["row_id"]})
                total_updated += 1

    mode = "DRY-RUN" if args.dry_run else "WRITE"
    print(
        f"[{mode}] legacy plaintext PII scan kész: "
        f"jelölt sorok={total_candidates}, frissített sorok={total_updated} "
        f"target={schema}.{table}.{column}"
    )


if __name__ == "__main__":
    main()
