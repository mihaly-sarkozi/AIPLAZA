# backend/core/modules/tenant/slug/policy.py
# Feladat: Demo tenant slug és locale policy helper függvények. Normalizálja és validálja a slugot, locale-t és domain formátumot a demo signup folyamat előtt. Tenant slug policy réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

SUPPORTED_DEMO_LOCALES = {"hu", "en", "es"}


def demo_slug_base(raw_name: str) -> str:
    normalized = unicodedata.normalize("NFKD", raw_name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    letters_only = re.sub(r"[^a-z]", "", ascii_name)
    return (letters_only or "demo")[:48]


def candidate_demo_slug(base: str, suffix: int) -> str:
    if suffix <= 1:
        return base[:64]
    suffix_text = str(suffix)
    return f"{base[:64 - len(suffix_text)]}{suffix_text}"


def normalize_demo_locale(locale: str | None) -> str:
    normalized = (locale or "").strip().lower()
    return normalized if normalized in SUPPORTED_DEMO_LOCALES else "hu"


def initial_demo_knowledge_base_name(locale: str) -> str:
    names = {
        "hu": "Teszt tudástár",
        "en": "Test knowledge base",
        "es": "Base de conocimiento de prueba",
    }
    return names.get(locale, names["hu"])


def demo_trial_expires_at(now: datetime, *, days: int) -> datetime:
    return now + timedelta(days=days)


def demo_host_hint(slug: str, tenant_base_domain: str) -> str:
    return f"{slug}.{tenant_base_domain}"
