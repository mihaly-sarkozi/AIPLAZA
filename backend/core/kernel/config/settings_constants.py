# backend/core/kernel/config/settings_constants.py
# Feladat: A settings validátorok közös konstansait és megengedett értékeit tartalmazza. Ide kerülnek azok a regexek, fallback értékek és enum-szerű készletek, amelyeket több config validátor is használ, hogy a base.py ne tartalmazzon technikai helper részleteket. Csak a config réteg importálja, ezért belső kernel helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re

DEFAULT_SMTP_HOST = ""
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_USER = ""
DEFAULT_SMTP_FROM_EMAIL = ""
DEFAULT_SMTP_FROM_NAME = ""

ALLOWED_COOKIE_SAMESITE_VALUES = {"lax", "strict", "none"}
ALLOWED_DEMO_CAPTCHA_PROVIDERS = {"none", "turnstile", "recaptcha"}
ALLOWED_EMBEDDING_PROVIDERS = {"local", "openai", "dummy"}
ALLOWED_MALWARE_SCAN_PROVIDERS = {"none", "clamav"}
ALLOWED_PASSWORD_SECURITY_LEVELS = {"basic", "standard", "high"}

DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

__all__ = [
    "ALLOWED_COOKIE_SAMESITE_VALUES",
    "ALLOWED_DEMO_CAPTCHA_PROVIDERS",
    "ALLOWED_EMBEDDING_PROVIDERS",
    "ALLOWED_MALWARE_SCAN_PROVIDERS",
    "ALLOWED_PASSWORD_SECURITY_LEVELS",
    "DEFAULT_SMTP_FROM_EMAIL",
    "DEFAULT_SMTP_FROM_NAME",
    "DEFAULT_SMTP_HOST",
    "DEFAULT_SMTP_PORT",
    "DEFAULT_SMTP_USER",
    "DOMAIN_LABEL_RE",
]
