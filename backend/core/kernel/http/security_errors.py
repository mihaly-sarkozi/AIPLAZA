# backend/core/kernel/http/security_errors.py
# Feladat: Publikus HTTP security error factory app moduloknak. A belső
# security részleteket egységes, nem szivárogtató response payloadra cseréli.

from __future__ import annotations

from core.kernel.security.errors import security_http_exception

__all__ = ["security_http_exception"]
