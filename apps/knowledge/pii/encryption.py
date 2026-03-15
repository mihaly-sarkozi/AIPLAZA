from __future__ import annotations

import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from config.settings import settings


_ENC_PREFIX = "enc::"


def _derive_key_from_secret(secret: str) -> str:
    digest = hashlib.sha256((secret or "").encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


class PiiEncryptor:
    def __init__(self) -> None:
        cfg_key = (getattr(settings, "pii_encryption_key", "") or "").strip()
        key = cfg_key if cfg_key else _derive_key_from_secret(getattr(settings, "jwt_secret", ""))
        self._fernet = Fernet(key.encode("utf-8"))
        self._allow_legacy_plaintext = bool(
            getattr(settings, "pii_allow_legacy_plaintext_read", True)
        )

    def encrypt(self, value: str) -> str:
        raw = value or ""
        token = self._fernet.encrypt(raw.encode("utf-8")).decode("utf-8")
        return f"{_ENC_PREFIX}{token}"

    def decrypt(self, value: str) -> str:
        raw = value or ""
        if not raw:
            return ""
        if not raw.startswith(_ENC_PREFIX):
            if self._allow_legacy_plaintext:
                return raw
            raise ValueError("Legacy plaintext PII read is disabled.")
        token = raw[len(_ENC_PREFIX):]
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("PII decrypt failed: invalid token or key") from exc

    def is_encrypted(self, value: str) -> bool:
        return bool(value and value.startswith(_ENC_PREFIX))

