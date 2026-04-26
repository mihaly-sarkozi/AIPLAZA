from __future__ import annotations

from core.platform.brand.dto import BrandResponse, BrandUpdateRequest


class BrandPolicy:
    def default_brand(self) -> BrandResponse:
        return BrandResponse(
            display_name="",
            logo_url="",
            primary_color="#2563eb",
            support_email="",
            public_enabled=True,
        )

    def normalize_update(self, body: BrandUpdateRequest) -> dict[str, object]:
        return {
            "display_name": (body.display_name or "").strip(),
            "logo_url": (body.logo_url or "").strip(),
            "primary_color": (body.primary_color or "").strip() or "#2563eb",
            "support_email": (body.support_email or "").strip(),
            "public_enabled": body.public_enabled,
        }

    def to_response(self, row) -> BrandResponse:
        if row is None:
            return self.default_brand()
        return BrandResponse(
            display_name=row.display_name or "",
            logo_url=row.logo_url or "",
            primary_color=row.primary_color or "#2563eb",
            support_email=row.support_email or "",
            public_enabled=bool(row.public_enabled),
        )
