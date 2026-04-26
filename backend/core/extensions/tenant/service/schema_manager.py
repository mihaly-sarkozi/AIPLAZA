# Backward-compat re-export – implementation moved to service/schema/manager.py
from core.extensions.tenant.schema.manager import SqlAlchemyTenantSchemaManager  # noqa: F401

__all__ = ["SqlAlchemyTenantSchemaManager"]
