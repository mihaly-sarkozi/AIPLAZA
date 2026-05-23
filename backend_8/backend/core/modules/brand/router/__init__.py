# backend/core/modules/brand/router/__init__.py
# Feladat: A brand router csomag exportfelülete. A FastAPI routert és get_brand_service dependency helper aliasát adja tovább a module assembly számára. Brand HTTP adapter csomagbelépő.
# Sárközi Mihály - 2026.05.21

from core.modules.brand.router.brand_router import get_brand_service, router

__all__ = ["get_brand_service", "router"]
