# backend/core/modules/brand/models/__init__.py
# Feladat: Brand perzisztencia ORM modellek exportfelulete.

from __future__ import annotations

from core.modules.brand.persistence.brand_settings_orm import BrandSettingsORM

__all__ = ["BrandSettingsORM"]
