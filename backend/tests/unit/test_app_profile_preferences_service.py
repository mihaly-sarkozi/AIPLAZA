from __future__ import annotations

import pytest

from apps.profile.domain.preferences import ProfilePreferences
from apps.profile.service.preferences_service import ProfilePreferencesService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _InMemoryPreferencesRepo:
    def __init__(self) -> None:
        self.items: dict[tuple[str, int], ProfilePreferences] = {}

    def get_for_user(self, *, tenant_slug: str, user_id: int) -> ProfilePreferences:
        return self.items.get((tenant_slug, user_id), ProfilePreferences(user_id=user_id))

    def upsert_for_user(
        self,
        *,
        tenant_slug: str,
        user_id: int,
        dashboard_layout: str,
        show_tips: bool,
    ) -> ProfilePreferences:
        prefs = ProfilePreferences(
            user_id=user_id,
            dashboard_layout=dashboard_layout,
            show_tips=show_tips,
        )
        self.items[(tenant_slug, user_id)] = prefs
        return prefs


def test_preferences_service_updates_existing_preferences_with_fake_repo() -> None:
    repo = _InMemoryPreferencesRepo()
    repo.upsert_for_user(
        tenant_slug="demo",
        user_id=5,
        dashboard_layout="comfortable",
        show_tips=True,
    )
    service = ProfilePreferencesService(repository=repo)

    prefs = service.update_for_user(
        tenant_slug="demo",
        user_id=5,
        updates={"dashboard_layout": "compact", "show_tips": False},
    )

    assert prefs.dashboard_layout == "compact"
    assert prefs.show_tips is False
    assert repo.items[("demo", 5)] == prefs


def test_preferences_service_keeps_current_layout_for_invalid_value() -> None:
    repo = _InMemoryPreferencesRepo()
    service = ProfilePreferencesService(repository=repo)

    prefs = service.update_for_user(
        tenant_slug="demo",
        user_id=7,
        updates={"dashboard_layout": "invalid-layout"},
    )

    assert prefs.dashboard_layout == "comfortable"
    assert prefs.show_tips is True
