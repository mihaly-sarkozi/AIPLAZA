# backend/core/modules/brand/web/responses/__init__.py
# Feladat: A brand HTTP response sémák exportfelülete. A BrandResponse modellt adja tovább a router, service és policy rétegek számára. Brand web response schema csomagbelépő.
# Sárközi Mihály - 2026.05.21

from core.modules.brand.web.responses.brand_response import BrandResponse

__all__ = ["BrandResponse"]
