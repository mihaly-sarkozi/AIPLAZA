# Backward-compat re-export – implementation moved to service/signup/token.py
from core.extensions.tenant.tokens.demo_jwt import DemoLoginTokenService  # noqa: F401

__all__ = ["DemoLoginTokenService"]
