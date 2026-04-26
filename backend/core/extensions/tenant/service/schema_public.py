# Backward-compat re-export – implementation moved to service/schema/public.py
from core.extensions.tenant.schema.public import upgrade_public_schema  # noqa: F401

__all__ = ["upgrade_public_schema"]
