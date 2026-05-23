# backend/core/modules/tenant/slug/reservation.py
# Feladat: Demo tenant slug foglalási service. Repository és policy alapján egyedi tenant slugot választ vagy foglal a demo signup/provisioning folyamat számára. Tenant slug reservation use case.
# Sárközi Mihály - 2026.05.21

"""Demo slug reservation use case.

Responsibility: find or create a unique, idempotent tenant slug for a demo
signup session.  Pure coordination logic – no provisioning, no email, no
business rules beyond slug uniqueness.

Can be unit-tested with mock repos without any database or framework.
"""
from __future__ import annotations

from core.modules.tenant.slug.policy import candidate_demo_slug, demo_slug_base


class DemoSlugReserver:
    """Reserve a unique demo slug for a session, idempotently.

    If the session already has a reserved slug it is returned immediately
    (idempotent re-entry).  Otherwise a new unique slug is found and locked
    in the session table.
    """

    def __init__(self, *, tenant_repo, demo_signup_repository) -> None:
        self._tenant_repo = tenant_repo
        self._demo_signup_repo = demo_signup_repository

    def reserve(self, session_id: str, requested_name: str, email: str) -> str:
        """Return an available slug for *session_id*, reserving it if needed."""
        existing = self._demo_signup_repo.get_reserved_slug(session_id)
        if existing:
            return existing

        base = demo_slug_base(requested_name)
        for suffix in range(1, 10_000):
            candidate = candidate_demo_slug(base, suffix)
            if self._tenant_repo.get_by_slug(candidate) is not None:
                continue
            if self._demo_signup_repo.reserve_slug(
                session_id=session_id,
                requested_name=requested_name,
                email=email,
                tenant_slug=candidate,
            ):
                return candidate
            # Race condition: someone else reserved this slug; try from DB.
            existing = self._demo_signup_repo.get_reserved_slug(session_id)
            if existing:
                return existing
        raise ValueError("slug_generation_failed")


__all__ = ["DemoSlugReserver"]
