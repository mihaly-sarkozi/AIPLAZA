from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable

from sqlalchemy import func, select

from apps.knowledge.models import KnowledgePiiMappingORM
from apps.knowledge.pii.encryption import PiiEncryptor


_TOKEN_ENTITY_RE = re.compile(r"[^a-z0-9]+")
_ENTITY_TYPE_ALIASES: dict[str, str] = {
    "person_name": "szemely",
    "person": "szemely",
    "name": "szemely",
    "nev": "szemely",
    "email_address": "email",
    "phone_number": "telefon",
    "phone": "telefon",
    "postal_address": "cim",
    "address": "cim",
    "customer_id": "ugyfel_azonosito",
    "personal_id": "szemelyi_azonosito",
    "passport_number": "utlevel_azonosito",
    "driver_license_number": "jogositvany_azonosito",
    "tax_id": "adoazonosito",
    "date_of_birth": "szuletesi_datum",
    "date": "datum",
    "iban": "bankszamla_azonosito",
    "bank_account_number": "bankszamla_azonosito",
}


def _normalize_entity_type(entity_type: str) -> str:
    raw = str(entity_type or "").strip().lower()
    if not raw:
        return "pii"
    ascii_raw = "".join(ch for ch in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(ch))
    value = _TOKEN_ENTITY_RE.sub("_", ascii_raw).strip("_")
    if not value:
        return "pii"
    aliased = _ENTITY_TYPE_ALIASES.get(value)
    if aliased:
        return aliased
    if "name" in value or "nev" in value:
        return "szemely"
    if "address" in value or "cim" in value:
        return "cim"
    if "phone" in value or "telefon" in value:
        return "telefon"
    if "szemelyi_azonosito" in value:
        return "szemelyi_azonosito"
    if "utlevel_azonosito" in value:
        return "utlevel_azonosito"
    if "jogositvany_azonosito" in value:
        return "jogositvany_azonosito"
    if "ugyfel_azonosito" in value:
        return "ugyfel_azonosito"
    if "bankszamla_azonosito" in value:
        return "bankszamla_azonosito"
    if "id" in value or "number" in value or "azonosito" in value:
        return "azonosito"
    return value


def _entity_hash(entity_type: str, original_value: str) -> str:
    normalized = f"{_normalize_entity_type(entity_type)}::{(original_value or '').strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class KnowledgePiiMappingRepository:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory
        self._encryptor = PiiEncryptor()

    def resolve_or_create_token(self, *, corpus_uuid: str, entity_type: str, original_value: str) -> str:
        normalized_type = _normalize_entity_type(entity_type)
        value = str(original_value or "")
        if not value.strip():
            return ""
        item_hash = _entity_hash(normalized_type, value)
        with self._sf() as session:
            existing = session.execute(
                select(KnowledgePiiMappingORM).where(
                    KnowledgePiiMappingORM.corpus_uuid == corpus_uuid,
                    KnowledgePiiMappingORM.entity_type == normalized_type,
                    KnowledgePiiMappingORM.entity_hash == item_hash,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return str(existing.token or "")

            max_idx = session.execute(
                select(func.max(KnowledgePiiMappingORM.token_index)).where(
                    KnowledgePiiMappingORM.corpus_uuid == corpus_uuid,
                    KnowledgePiiMappingORM.entity_type == normalized_type,
                )
            ).scalar_one_or_none()
            next_idx = int(max_idx or 0) + 1
            token = f"[{normalized_type}_{next_idx}]"
            row = KnowledgePiiMappingORM(
                corpus_uuid=corpus_uuid,
                entity_type=normalized_type,
                entity_hash=item_hash,
                token=token,
                token_index=next_idx,
                encrypted_value=self._encryptor.encrypt(value),
            )
            session.add(row)
            session.commit()
            return token

    def resolve_tokens(self, *, corpus_uuid: str, tokens: Iterable[str]) -> dict[str, str]:
        unique_tokens = sorted({str(token or "").strip() for token in tokens if str(token or "").strip()})
        if not unique_tokens:
            return {}
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgePiiMappingORM).where(
                    KnowledgePiiMappingORM.corpus_uuid == corpus_uuid,
                    KnowledgePiiMappingORM.token.in_(unique_tokens),
                )
            ).scalars().all()
        out: dict[str, str] = {}
        for row in rows:
            token = str(row.token or "").strip()
            if not token:
                continue
            try:
                out[token] = self._encryptor.decrypt(str(row.encrypted_value or ""))
            except Exception:
                continue
        return out


__all__ = ["KnowledgePiiMappingRepository"]
