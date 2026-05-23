# backend/core/modules/brand/web/requests/__init__.py
# Feladat: A brand HTTP request sémák exportfelülete. A BrandUpdateRequest modellt adja tovább a router és service réteg számára. Brand web request schema csomagbelépő.
# Sárközi Mihály - 2026.05.21

from core.modules.brand.web.requests.brand_update_request import BrandUpdateRequest

__all__ = ["BrandUpdateRequest"]
