#!/usr/bin/env python3
"""Deploy előtti biztonsági ellenőrzés (P0 gate)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


KNOWN_WEAK_JWT_SECRETS = {
    "",
    "changeme",
    "secret",
    "jwt_secret",
    "dev-secret",
}


def _as_list(raw: str) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f".env nem található: {path}")
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            out[key.upper()] = value
    return out


def _check_proxy_config(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"Proxy config nem található: {path}"]
    text = path.read_text(encoding="utf-8", errors="replace")
    if "Strict-Transport-Security" not in text:
        errors.append("Hiányzik a Strict-Transport-Security fejléc a proxy configból.")
    has_https_redirect = (
        "return 301 https://" in text
        or "return 308 https://" in text
        or re.search(r"rewrite\s+\^.*https://", text) is not None
    )
    if not has_https_redirect:
        errors.append("Hiányzik a HTTP -> HTTPS redirect a proxy configból.")
    return errors


def run_checks(env_path: Path, proxy_config_path: Path | None, require_prod: bool) -> list[str]:
    env = _read_env(env_path)
    errors: list[str] = []

    app_env = env.get("APP_ENV", "dev").lower()
    if require_prod and app_env != "prod":
        errors.append("APP_ENV=prod kötelező deploy előtti ellenőrzéshez.")

    required = [
        "DATABASE_URL",
        "JWT_SECRET",
        "SMTP_PASSWORD",
        "FRONTEND_BASE_URL",
        "TRUSTED_HOSTS",
        "CORS_ORIGINS",
    ]
    for key in required:
        if not env.get(key):
            errors.append(f"Hiányzó kötelező env változó: {key}")

    jwt_secret = env.get("JWT_SECRET", "")
    if jwt_secret.lower() in KNOWN_WEAK_JWT_SECRETS:
        errors.append("JWT_SECRET túl gyenge vagy default érték.")
    if len(jwt_secret) < 64:
        errors.append("JWT_SECRET túl rövid (minimum 64 karakter ajánlott).")

    db_url = env.get("DATABASE_URL", "")
    if db_url:
        parsed = urlsplit(db_url)
        if not parsed.scheme or not parsed.hostname:
            errors.append("DATABASE_URL nem tűnik érvényes URL-nek.")
        if parsed.password in (None, ""):
            errors.append("DATABASE_URL nem tartalmaz jelszót.")
        if app_env == "prod" and parsed.hostname in {"localhost", "127.0.0.1"}:
            errors.append("Productionben a DATABASE_URL nem mutathat localhostra.")

    cors_origins = _as_list(env.get("CORS_ORIGINS", ""))
    if "*" in cors_origins:
        errors.append("CORS_ORIGINS nem tartalmazhat wildcard '*' értéket.")
    for origin in cors_origins:
        if app_env == "prod" and not origin.startswith("https://"):
            errors.append(f"Production CORS origin csak HTTPS lehet: {origin}")

    trusted_hosts = _as_list(env.get("TRUSTED_HOSTS", ""))
    if not trusted_hosts:
        errors.append("TRUSTED_HOSTS üres.")
    if "*" in trusted_hosts:
        errors.append("TRUSTED_HOSTS nem lehet '*'.")

    if proxy_config_path is None:
        errors.append("Proxy config ellenőrzéshez add meg: --proxy-config <path>")
    else:
        errors.extend(_check_proxy_config(proxy_config_path))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy előtti biztonsági env/proxy ellenőrző.")
    parser.add_argument("--env-file", default=".env", help="Ellenőrzendő env fájl")
    parser.add_argument("--proxy-config", default="", help="Reverse proxy config fájl (nginx/caddy)")
    parser.add_argument(
        "--allow-non-prod",
        action="store_true",
        help="Ne követelje meg az APP_ENV=prod értéket",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file).resolve()
    proxy_path = Path(args.proxy_config).resolve() if args.proxy_config else None

    try:
        errors = run_checks(env_path, proxy_path, require_prod=not args.allow_non_prod)
    except Exception as exc:  # pragma: no cover - guard path
        print(f"[ERROR] security predeploy check futási hiba: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("[FAIL] Deploy előtti security gate megbukott:", file=sys.stderr)
        for err in errors:
            print(f" - {err}", file=sys.stderr)
        return 1

    print("[OK] Deploy előtti security gate rendben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

