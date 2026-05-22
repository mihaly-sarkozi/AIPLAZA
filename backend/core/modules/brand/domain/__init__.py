# backend/core/modules/brand/domain/__init__.py
# Feladat: A brand domain csomag tiszta exportfelülete. Csak ORM-mentes domain
# elemeket tesz elérhetővé, hogy service importkor ne töltődjön be SQLAlchemy.
# Sárközi Mihály - 2026.05.21

from core.modules.brand.domain.brand_policy import BrandPolicy

__all__ = ["BrandPolicy"]
