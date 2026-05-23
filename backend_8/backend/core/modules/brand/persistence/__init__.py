# backend/core/modules/brand/persistence/__init__.py
# Feladat: Brand perzisztencia adapterek exportfelülete. Itt élnek az ORM és
# repository implementációk; domain/service importok ne támaszkodjanak erre a
# csomagra közvetlenül.

from __future__ import annotations

from core.modules.brand.persistence.brand_settings_orm import BrandSettingsORM

__all__ = ["BrandSettingsORM"]
