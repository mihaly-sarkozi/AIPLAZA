# backend/core/modules/tenant/signup/unsubscribe.py
# Feladat: Demo signup unsubscribe use case. Demo onboarding emailről való leiratkozást és kapcsolódó session/blocklist állapotot kezeli. Tenant onboarding opt-out service.
# Sárközi Mihály - 2026.05.21

"""Demo unsubscribe use case.

Responsibility: mark a demo tenant for deletion (deactivate, set feature
flags, block the email).  Pure domain logic – no HTTP, no email sending.

Can be unit-tested with mock repos without a database.
"""
from __future__ import annotations

from datetime import timedelta


class DemoUnsubscribeUseCase:
    """Request demo tenant deletion and block the owner email."""

    def __init__(
        self,
        *,
        tenant_repo,
        demo_signup_repository,
        clock,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._demo_signup_repo = demo_signup_repository
        self._clock = clock

    def execute(
        self,
        *,
        tenant_slug: str,
        email: str,
        requested_by_user_id: int | None = None,
        current_user_email: str | None = None,
    ) -> dict[str, str | int]:
        """Demo leiratkozás kérelem.

        Args:
            tenant_slug:        A tenant azonosítója.
            email:              A megerősítő email (a felhasználó begépelte).
            requested_by_user_id: A bejelentkezett felhasználó id-ja.
            current_user_email: Ha megadott, ellenőrzi, hogy az ``email``
                                egyezik-e a bejelentkezett felhasználó emailjével.
                                Ha nem egyezik → ValueError("email_mismatch").
        """
        normalized_email = (email or "").strip().lower()
        normalized_slug = (tenant_slug or "").strip().lower()
        if not normalized_slug:
            raise ValueError("tenant_missing")
        if not normalized_email:
            raise ValueError("email_required")
        if current_user_email is not None:
            if normalized_email != (current_user_email or "").strip().lower():
                raise ValueError("email_mismatch")

        tenant = self._tenant_repo.get_by_slug(normalized_slug)
        if tenant is None:
            raise ValueError("tenant_not_found")

        now = self._clock.now()
        due_at = now + timedelta(days=7)
        snapshot = self._tenant_repo.get_snapshot_by_slug(normalized_slug)
        feature_flags = dict(getattr(getattr(snapshot, "config", None), "feature_flags", {}) or {})
        feature_flags["deletion_requested"] = True
        feature_flags["deletion_requested_at"] = now.isoformat()
        feature_flags["deletion_due_at"] = due_at.isoformat()
        feature_flags["deletion_requested_email"] = normalized_email

        limits = dict(getattr(getattr(snapshot, "config", None), "limits", {}) or {})
        package = getattr(getattr(snapshot, "config", None), "package", "free") or "free"

        self._tenant_repo.create_config(
            tenant.id,
            slug=normalized_slug,
            package=package,
            feature_flags=feature_flags,
            limits=limits,
            created_by=requested_by_user_id,
        )
        self._tenant_repo.deactivate(tenant.id, updated_by=requested_by_user_id)
        self._demo_signup_repo.block_email(
            normalized_email,
            source_tenant_slug=normalized_slug,
            reason="demo_unsubscribe",
        )
        return {
            "tenant_slug": normalized_slug,
            "deletion_due_at": due_at.isoformat(),
            "deletion_due_days": 7,
        }


__all__ = ["DemoUnsubscribeUseCase"]
