# backend/core/modules/tenant/service/demo_login_token_service.py
# Feladat: Kompatibilitási importútvonal a DemoLoginTokenService felé. A canonical token service a tokens/demo_jwt.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.tokens.demo_jwt import DemoLoginTokenService  # noqa: F401

__all__ = ["DemoLoginTokenService"]
