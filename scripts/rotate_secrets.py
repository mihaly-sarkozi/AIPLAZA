#!/usr/bin/env python3
"""Secret rotációs segéd (JWT/DB URL/SMTP) .env fájlhoz."""

from __future__ import annotations

import argparse
import secrets
import shutil
import string
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit


def _gen_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _backup_env(env_file: Path) -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup = env_file.with_name(f".env.backup.{ts}")
    shutil.copy2(env_file, backup)
    return backup


def _load_env(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            out[key] = value
    return lines, out


def _set_env_value(lines: list[str], key: str, value: str) -> list[str]:
    out: list[str] = []
    found = False
    for raw in lines:
        line = raw.strip()
        if line.startswith("#") or "=" not in raw:
            out.append(raw)
            continue
        current_key = raw.split("=", 1)[0].strip()
        if current_key == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(raw)
    if not found:
        out.append(f"{key}={value}")
    return out


def _write_env(path: Path, lines: list[str]) -> None:
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _rotate_database_url_password(
    env_map: dict[str, str],
    lines: list[str],
    new_password: str | None,
    apply_db_password: bool,
) -> tuple[bool, str, list[str]]:
    key = "DATABASE_URL"
    db_url = (env_map.get(key) or env_map.get("database_url") or "").strip()
    if not db_url:
        return False, "DATABASE_URL nincs megadva, DB rotáció kihagyva.", lines

    parsed = urlsplit(db_url)
    if not parsed.username:
        return False, "DATABASE_URL nem tartalmaz felhasználót, DB rotáció kihagyva.", lines
    if parsed.password is None:
        return False, "DATABASE_URL nem tartalmaz jelszót, DB rotáció kihagyva.", lines

    chosen_password = new_password or _gen_password(32)
    enc_password = quote(chosen_password, safe="")
    username = parsed.username
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:{enc_password}@{host}{port}"
    if parsed.username and parsed.password is not None:
        # Support query params and path retention
        new_url = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    else:
        return False, "DATABASE_URL formátum nem támogatott automatikus rotációhoz.", lines

    if apply_db_password:
        safe_user = unquote(username)
        if not safe_user.replace("_", "").isalnum():
            return False, "DB user név nem biztonságos automatikus ALTER ROLE futtatáshoz.", lines
        escaped_pwd = chosen_password.replace("'", "''")
        sql = f"ALTER ROLE \"{safe_user}\" WITH PASSWORD '{escaped_pwd}';"
        proc = subprocess.run(
            ["psql", db_url, "-v", "ON_ERROR_STOP=1", "-c", sql],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip() or "ismeretlen psql hiba"
            return False, f"DB jelszó ALTER ROLE sikertelen: {msg}", lines

    updated_lines = _set_env_value(lines, key, new_url)
    return True, "DATABASE_URL jelszó rotálva és .env frissítve.", updated_lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Secret rotáció .env fájlban.")
    parser.add_argument("--env-file", default=".env", help=".env fájl útvonala")
    parser.add_argument("--rotate-jwt", action="store_true", help="JWT_SECRET rotáció")
    parser.add_argument("--rotate-db-url-password", action="store_true", help="DATABASE_URL jelszó rotáció")
    parser.add_argument("--db-new-password", default="", help="DB új jelszó (ha üres, generált)")
    parser.add_argument(
        "--apply-db-password",
        action="store_true",
        help="ALTER ROLE futtatása az adatbázison (jogosultság szükséges)",
    )
    parser.add_argument("--set-smtp-password", default="", help="Új SMTP_PASSWORD érték")
    parser.add_argument("--no-backup", action="store_true", help="Ne készítsen .env backupot")
    args = parser.parse_args()

    env_file = Path(args.env_file).resolve()
    if not env_file.exists():
        print(f"[ERROR] .env nem található: {env_file}", file=sys.stderr)
        return 2

    if not args.no_backup:
        backup_path = _backup_env(env_file)
        print(f"[INFO] .env backup készült: {backup_path}")

    lines, env_map = _load_env(env_file)
    changed = False
    new_lines = lines

    if args.rotate_jwt:
        new_jwt = secrets.token_hex(64)
        new_lines = _set_env_value(new_lines, "JWT_SECRET", new_jwt)
        changed = True
        print("[OK] JWT_SECRET rotálva.")

    if args.rotate_db_url_password:
        ok, msg, new_lines = _rotate_database_url_password(
            env_map=env_map,
            lines=new_lines,
            new_password=(args.db_new_password or None),
            apply_db_password=args.apply_db_password,
        )
        print(f"[{'OK' if ok else 'WARN'}] {msg}")
        changed = changed or ok

    if args.set_smtp_password:
        new_lines = _set_env_value(new_lines, "SMTP_PASSWORD", args.set_smtp_password)
        changed = True
        print("[OK] SMTP_PASSWORD frissítve.")

    if not changed:
        print("[WARN] Nem történt módosítás. Add meg legalább az egyik rotációs opciót.")
        return 1

    _write_env(env_file, new_lines)
    print("[DONE] Secret rotáció kész.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

