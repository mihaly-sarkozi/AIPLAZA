from __future__ import annotations

# Kompatibilitási shim: az ORM tényleges helye a brand/persistence réteg.
from core.modules.brand.persistence.brand_settings_orm import BrandSettingsORM

__all__ = ["BrandSettingsORM"]
