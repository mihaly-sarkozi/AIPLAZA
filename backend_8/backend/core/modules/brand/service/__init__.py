# backend/core/modules/brand/service/__init__.py
# Feladat: A brand service csomag exportfelülete. A BrandService-t adja tovább, amely brand beállítások olvasását, frissítését és auditálását végzi. Brand service csomagbelépő router és module assembly számára.
# Sárközi Mihály - 2026.05.21

from core.modules.brand.service.brand_service import BrandService

__all__ = ["BrandService"]
