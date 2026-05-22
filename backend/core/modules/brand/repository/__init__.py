# backend/core/modules/brand/repository/__init__.py
# Feladat: A brand repository csomag exportfelülete. A BrandRepository-t adja tovább, amely tenant-séma brand_settings sor olvasását és upsertelését végzi. Brand perzisztencia csomagbelépő a service és module assembly számára.
# Sárközi Mihály - 2026.05.21

from core.modules.brand.repository.brand_repository import BrandRepository

__all__ = ["BrandRepository"]
